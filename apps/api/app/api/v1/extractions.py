from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Actor, get_current_actor, get_request_id
from app.core.errors import ApplicationError
from app.db.models import Evidence, FileVersion, Job, Project, ProjectFact, ProjectFile
from app.db.session import get_database_session
from app.domain.enums import JobStatus
from app.domain.m4_schemas import (
    FactCandidateResponse,
    FactDecision,
    FactEvidenceResponse,
    FactTypeResponse,
    ProjectExtractionCreate,
    ProjectExtractionResponse,
)
from app.services.audit import record_audit_event
from app.services.dispatch import JobDispatcher, dispatch_persisted_job, get_job_dispatcher
from app.services.project_extraction import FACT_DEFINITIONS, classify_document

router = APIRouter(tags=["project extraction"])


async def _owned_candidate(session: AsyncSession, fact_id: UUID, actor: Actor) -> ProjectFact:
    fact = await session.scalar(
        select(ProjectFact)
        .join(Project)
        .where(
            ProjectFact.id == fact_id,
            Project.organization_id == actor.organization_id,
            ProjectFact.source != "manual",
        )
    )
    if fact is None:
        raise ApplicationError(
            "fact_candidate_not_found", "Fact candidate was not found", status_code=404
        )
    return fact


async def _candidate_response(session: AsyncSession, fact: ProjectFact) -> FactCandidateResponse:
    evidence = list(
        await session.scalars(select(Evidence).where(Evidence.project_fact_id == fact.id))
    )
    return FactCandidateResponse.model_validate(fact).model_copy(
        update={"evidence": [FactEvidenceResponse.model_validate(item) for item in evidence]}
    )


@router.get("/fact-types", response_model=list[FactTypeResponse])
async def list_fact_types() -> list[FactTypeResponse]:
    return [
        FactTypeResponse(key=item.key, label=item.label, unit=item.unit)
        for item in FACT_DEFINITIONS
    ]


@router.post(
    "/projects/{project_id}/extractions",
    response_model=ProjectExtractionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_extraction(
    project_id: UUID,
    payload: ProjectExtractionCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
) -> ProjectExtractionResponse:
    row = (
        await session.execute(
            select(FileVersion, Project)
            .join(ProjectFile, ProjectFile.id == FileVersion.project_file_id)
            .join(Project, Project.id == ProjectFile.project_id)
            .where(
                FileVersion.id == payload.file_version_id,
                Project.id == project_id,
                Project.organization_id == actor.organization_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise ApplicationError(
            "file_version_not_found", "File version was not found", status_code=404
        )
    file_version, project = row
    try:
        document_kind = classify_document(file_version.original_filename)
    except ValueError as exception:
        raise ApplicationError(
            "unsupported_project_document", str(exception), status_code=415
        ) from exception
    job = Job(
        organization_id=actor.organization_id,
        project_id=project.id,
        file_version_id=file_version.id,
        job_type="project.extract",
        status=JobStatus.QUEUED,
        progress=0,
        input_data={"file_version_id": str(file_version.id), "document_kind": document_kind},
        request_id=get_request_id(request),
    )
    session.add(job)
    await session.flush()
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="project_extraction.queued",
        entity_type="job",
        entity_id=job.id,
        request_id=get_request_id(request),
        payload={"file_version_id": str(file_version.id), "document_kind": document_kind},
    )
    await session.commit()
    await dispatch_persisted_job(session, dispatcher, job)
    return ProjectExtractionResponse(document_kind=document_kind, job=job)


@router.get("/projects/{project_id}/fact-candidates", response_model=list[FactCandidateResponse])
async def list_fact_candidates(
    project_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    verification_status: Annotated[str | None, Query()] = None,
) -> list[FactCandidateResponse]:
    owned = await session.scalar(
        select(Project.id).where(
            Project.id == project_id, Project.organization_id == actor.organization_id
        )
    )
    if owned is None:
        raise ApplicationError("project_not_found", "Project was not found", status_code=404)
    statement = select(ProjectFact).where(
        ProjectFact.project_id == project_id, ProjectFact.source != "manual"
    )
    if verification_status:
        statement = statement.where(ProjectFact.verification_status == verification_status)
    facts = list(await session.scalars(statement.order_by(ProjectFact.created_at.desc())))
    return [await _candidate_response(session, fact) for fact in facts]


@router.post("/fact-candidates/{fact_id}/verify", response_model=FactCandidateResponse)
async def verify_fact_candidate(
    fact_id: UUID,
    payload: FactDecision,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> FactCandidateResponse:
    fact = await _owned_candidate(session, fact_id, actor)
    if fact.verification_status not in {"candidate", "conflicting"}:
        raise ApplicationError(
            "fact_candidate_already_decided", "Fact candidate was already decided", status_code=409
        )
    scope = json.dumps(fact.scope_data, sort_keys=True, separators=(",", ":"))
    verified = list(
        await session.scalars(
            select(ProjectFact)
            .where(
                ProjectFact.project_id == fact.project_id,
                ProjectFact.key == fact.key,
                ProjectFact.verification_status == "verified",
                ProjectFact.id != fact.id,
            )
            .order_by(ProjectFact.created_at.desc())
        )
    )
    previous = next(
        (
            item
            for item in verified
            if json.dumps(item.scope_data, sort_keys=True, separators=(",", ":")) == scope
        ),
        None,
    )
    fact.verification_status = "verified"
    fact.supersedes_id = previous.id if previous else None
    fact.verified_by_id, fact.verified_at = actor.user_id, datetime.now(UTC)
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="fact_candidate.verified",
        entity_type="project_fact",
        entity_id=fact.id,
        request_id=get_request_id(request),
        payload={"reason": payload.reason, "supersedes_id": str(fact.supersedes_id or "")},
    )
    await session.commit()
    await session.refresh(fact)
    return await _candidate_response(session, fact)


@router.post("/fact-candidates/{fact_id}/reject", response_model=FactCandidateResponse)
async def reject_fact_candidate(
    fact_id: UUID,
    payload: FactDecision,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> FactCandidateResponse:
    fact = await _owned_candidate(session, fact_id, actor)
    if fact.verification_status not in {"candidate", "conflicting"}:
        raise ApplicationError(
            "fact_candidate_already_decided", "Fact candidate was already decided", status_code=409
        )
    fact.verification_status = "rejected"
    fact.verified_by_id, fact.verified_at = actor.user_id, datetime.now(UTC)
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="fact_candidate.rejected",
        entity_type="project_fact",
        entity_id=fact.id,
        request_id=get_request_id(request),
        payload={"reason": payload.reason},
    )
    await session.commit()
    await session.refresh(fact)
    return await _candidate_response(session, fact)
