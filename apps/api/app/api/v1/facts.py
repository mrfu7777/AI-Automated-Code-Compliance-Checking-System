from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Actor, get_current_actor, get_request_id
from app.core.errors import ApplicationError
from app.db.models import Evidence, Project, ProjectFact
from app.db.session import get_database_session
from app.domain.m3_schemas import ProjectFactCreate, ProjectFactResponse
from app.services.audit import record_audit_event

router = APIRouter(prefix="/projects", tags=["project facts"])


async def _owned_project(session: AsyncSession, project_id: UUID, actor: Actor) -> Project:
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id, Project.organization_id == actor.organization_id
        )
    )
    if project is None:
        raise ApplicationError("project_not_found", "Project was not found", status_code=404)
    return project


async def _fact_response(session: AsyncSession, fact: ProjectFact) -> ProjectFactResponse:
    evidence_ids = list(
        await session.scalars(select(Evidence.id).where(Evidence.project_fact_id == fact.id))
    )
    return ProjectFactResponse.model_validate(fact).model_copy(
        update={"evidence_ids": evidence_ids}
    )


@router.post(
    "/{project_id}/facts", response_model=ProjectFactResponse, status_code=status.HTTP_201_CREATED
)
async def create_manual_fact(
    project_id: UUID,
    payload: ProjectFactCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ProjectFactResponse:
    await _owned_project(session, project_id, actor)
    scope_text = json.dumps(payload.scope_data, sort_keys=True, separators=(",", ":"))
    candidates = list(
        await session.scalars(
            select(ProjectFact)
            .where(ProjectFact.project_id == project_id, ProjectFact.key == payload.key)
            .order_by(ProjectFact.created_at.desc())
        )
    )
    previous = next(
        (
            item
            for item in candidates
            if json.dumps(item.scope_data, sort_keys=True, separators=(",", ":")) == scope_text
        ),
        None,
    )
    fact = ProjectFact(
        project_id=project_id,
        key=payload.key,
        value=payload.value,
        unit=payload.unit,
        scope_data=payload.scope_data,
        source="manual",
        verification_status="verified",
        confidence=1.0,
        supersedes_id=previous.id if previous else None,
        verified_by_id=actor.user_id,
        verified_at=datetime.now(UTC),
    )
    session.add(fact)
    await session.flush()
    evidence = Evidence(
        organization_id=actor.organization_id,
        project_fact_id=fact.id,
        kind="manual_assertion",
        location={"scope": payload.scope_data},
        excerpt=payload.justification,
        created_by_id=actor.user_id,
    )
    session.add(evidence)
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="project_fact.verified",
        entity_type="project_fact",
        entity_id=fact.id,
        request_id=get_request_id(request),
        payload={"key": fact.key, "supersedes_id": str(fact.supersedes_id or "")},
    )
    await session.commit()
    await session.refresh(fact)
    return await _fact_response(session, fact)


@router.get("/{project_id}/facts", response_model=list[ProjectFactResponse])
async def list_project_facts(
    project_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    include_history: bool = False,
) -> list[ProjectFactResponse]:
    await _owned_project(session, project_id, actor)
    facts = list(
        await session.scalars(
            select(ProjectFact)
            .where(ProjectFact.project_id == project_id)
            .order_by(ProjectFact.created_at.desc())
        )
    )
    if not include_history:
        superseded_ids = {fact.supersedes_id for fact in facts if fact.supersedes_id is not None}
        current: dict[tuple[str, str], ProjectFact] = {}
        for fact in facts:
            if fact.id in superseded_ids:
                continue
            scope = json.dumps(fact.scope_data, sort_keys=True, separators=(",", ":"))
            current.setdefault((fact.key, scope), fact)
        facts = list(current.values())
    return [await _fact_response(session, item) for item in facts]
