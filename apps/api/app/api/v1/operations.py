from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Actor, get_current_actor, get_request_id, require_admin
from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.db.models import (
    ApiKey,
    AuditEvent,
    CheckResult,
    CheckRun,
    FileVersion,
    Job,
    PilotFeedback,
    Project,
    ProjectFile,
    ReviewPackage,
)
from app.db.session import get_database_session
from app.domain.m7_schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeySummary,
    AuditEventResponse,
    OperationsOverview,
    PilotFeedbackCreate,
    PilotFeedbackResponse,
    PilotFeedbackUpdate,
)
from app.services.audit import record_audit_event

router = APIRouter(tags=["release-candidate"])


def _api_key_hash(token: str) -> str:
    pepper = get_settings().api_key_pepper
    return hashlib.sha256(f"{pepper}:{token}".encode()).hexdigest()


@router.post("/access/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ApiKeyCreated:
    if payload.expires_at is not None and payload.expires_at <= datetime.now(UTC):
        raise ApplicationError(
            "invalid_expiry", "API key expiry must be in the future", status_code=422
        )
    token = f"cc_{secrets.token_urlsafe(32)}"
    credential = ApiKey(
        user_id=actor.user_id,
        name=payload.name,
        prefix=token[:12],
        key_hash=_api_key_hash(token),
        expires_at=payload.expires_at,
    )
    session.add(credential)
    await session.flush()
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="api_key.created",
        entity_type="api_key",
        entity_id=credential.id,
        request_id=get_request_id(request),
        payload={"name": credential.name, "prefix": credential.prefix},
    )
    await session.commit()
    return ApiKeyCreated(
        id=credential.id,
        name=credential.name,
        prefix=credential.prefix,
        token=token,
        expires_at=credential.expires_at,
        created_at=credential.created_at,
    )


@router.get("/access/api-keys", response_model=list[ApiKeySummary])
async def list_api_keys(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> list[ApiKey]:
    return list(
        await session.scalars(
            select(ApiKey).where(ApiKey.user_id == actor.user_id).order_by(ApiKey.created_at.desc())
        )
    )


@router.delete("/access/api-keys/{key_id}", response_model=ApiKeySummary)
async def revoke_api_key(
    key_id: UUID,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ApiKey:
    credential = await session.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == actor.user_id)
    )
    if credential is None:
        raise ApplicationError("api_key_not_found", "API key was not found", status_code=404)
    credential.revoked_at = datetime.now(UTC)
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="api_key.revoked",
        entity_type="api_key",
        entity_id=credential.id,
        request_id=get_request_id(request),
    )
    await session.commit()
    await session.refresh(credential)
    return credential


@router.post(
    "/projects/{project_id}/pilot-feedback",
    response_model=PilotFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pilot_feedback(
    project_id: UUID,
    payload: PilotFeedbackCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> PilotFeedback:
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id, Project.organization_id == actor.organization_id
        )
    )
    if project is None:
        raise ApplicationError("project_not_found", "Project was not found", status_code=404)
    feedback = PilotFeedback(
        organization_id=actor.organization_id,
        project_id=project.id,
        submitted_by_id=actor.user_id,
        status="open",
        **payload.model_dump(),
    )
    session.add(feedback)
    await session.flush()
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="pilot_feedback.created",
        entity_type="pilot_feedback",
        entity_id=feedback.id,
        request_id=get_request_id(request),
        payload={"category": feedback.category, "severity": feedback.severity},
    )
    await session.commit()
    await session.refresh(feedback)
    return feedback


@router.get("/projects/{project_id}/pilot-feedback", response_model=list[PilotFeedbackResponse])
async def list_pilot_feedback(
    project_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> list[PilotFeedback]:
    return list(
        await session.scalars(
            select(PilotFeedback)
            .where(
                PilotFeedback.project_id == project_id,
                PilotFeedback.organization_id == actor.organization_id,
            )
            .order_by(PilotFeedback.created_at.desc())
        )
    )


@router.patch("/pilot-feedback/{feedback_id}", response_model=PilotFeedbackResponse)
async def update_pilot_feedback(
    feedback_id: UUID,
    payload: PilotFeedbackUpdate,
    request: Request,
    actor: Annotated[Actor, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> PilotFeedback:
    feedback = await session.scalar(
        select(PilotFeedback).where(
            PilotFeedback.id == feedback_id,
            PilotFeedback.organization_id == actor.organization_id,
        )
    )
    if feedback is None:
        raise ApplicationError(
            "feedback_not_found", "Pilot feedback was not found", status_code=404
        )
    feedback.status = payload.status
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="pilot_feedback.updated",
        entity_type="pilot_feedback",
        entity_id=feedback.id,
        request_id=get_request_id(request),
        payload={"status": feedback.status},
    )
    await session.commit()
    await session.refresh(feedback)
    return feedback


async def _group_counts(
    session: AsyncSession, statement: Any
) -> dict[str, int]:
    rows = (await session.execute(statement)).all()
    return {str(key): int(count) for key, count in rows}


@router.get("/operations/overview", response_model=OperationsOverview)
async def operations_overview(
    actor: Annotated[Actor, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> OperationsOverview:
    organization_id = actor.organization_id
    jobs_by_status = await _group_counts(
        session,
        select(Job.status, func.count())
        .where(Job.organization_id == organization_id)
        .group_by(Job.status),
    )
    jobs_by_type = await _group_counts(
        session,
        select(Job.job_type, func.count())
        .where(Job.organization_id == organization_id)
        .group_by(Job.job_type),
    )
    check_runs = int(
        await session.scalar(
            select(func.count())
            .select_from(CheckRun)
            .join(ReviewPackage)
            .join(Project)
            .where(Project.organization_id == organization_id)
        )
        or 0
    )
    open_findings = int(
        await session.scalar(
            select(func.count())
            .select_from(CheckResult)
            .join(CheckRun)
            .join(ReviewPackage)
            .join(Project)
            .where(
                Project.organization_id == organization_id,
                CheckResult.workflow_status != "resolved",
            )
        )
        or 0
    )
    stored_file_bytes = int(
        await session.scalar(
            select(func.coalesce(func.sum(FileVersion.size_bytes), 0))
            .select_from(FileVersion)
            .join(ProjectFile, ProjectFile.id == FileVersion.project_file_id)
            .join(Project, Project.id == ProjectFile.project_id)
            .where(Project.organization_id == organization_id)
        )
        or 0
    )
    feedback_by_status = await _group_counts(
        session,
        select(PilotFeedback.status, func.count())
        .where(PilotFeedback.organization_id == organization_id)
        .group_by(PilotFeedback.status),
    )
    settings = get_settings()
    return OperationsOverview(
        organization_id=organization_id,
        jobs_by_status=jobs_by_status,
        jobs_by_type=jobs_by_type,
        check_runs=check_runs,
        open_findings=open_findings,
        stored_file_bytes=stored_file_bytes,
        pilot_feedback_by_status=feedback_by_status,
        external_model_enabled=settings.external_model_enabled,
        external_model_calls=0,
        estimated_model_cost=0,
        deterministic_checks_available=True,
    )


@router.get("/operations/audit-events", response_model=list[AuditEventResponse])
async def list_audit_events(
    actor: Annotated[Actor, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> list[AuditEvent]:
    return list(
        await session.scalars(
            select(AuditEvent)
            .where(AuditEvent.organization_id == actor.organization_id)
            .order_by(AuditEvent.occurred_at.desc())
            .limit(500)
        )
    )
