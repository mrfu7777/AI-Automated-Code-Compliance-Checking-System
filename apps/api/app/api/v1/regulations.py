from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Actor, get_current_actor, get_request_id
from app.core.errors import ApplicationError
from app.db.models import (
    Clause,
    ClauseRevision,
    DocumentPage,
    Evidence,
    FileVersion,
    Job,
    Project,
    ProjectFile,
    Standard,
    StandardVersion,
)
from app.db.session import get_database_session
from app.domain.enums import JobStatus
from app.domain.m1_schemas import JobResponse
from app.domain.m2_schemas import (
    ClauseMerge,
    ClauseResponse,
    ClauseSplit,
    ClauseUpdate,
    PageResponse,
    RegulationIngest,
    RegulationIngestResponse,
    StandardResponse,
    StandardVersionResponse,
)
from app.services.audit import record_audit_event
from app.services.dispatch import JobDispatcher, dispatch_persisted_job, get_job_dispatcher
from app.services.storage import ObjectStorage, get_object_storage

router = APIRouter(prefix="/regulations", tags=["regulations"])


async def _owned_version(session: AsyncSession, version_id: UUID, actor: Actor) -> StandardVersion:
    version = await session.scalar(
        select(StandardVersion)
        .join(Standard)
        .where(
            StandardVersion.id == version_id,
            Standard.organization_id == actor.organization_id,
        )
    )
    if version is None:
        raise ApplicationError(
            "standard_version_not_found", "Standard version was not found", status_code=404
        )
    return version


async def _owned_clause(session: AsyncSession, clause_id: UUID, actor: Actor) -> Clause:
    clause = await session.scalar(
        select(Clause)
        .join(StandardVersion)
        .join(Standard)
        .where(
            Clause.id == clause_id,
            Standard.organization_id == actor.organization_id,
        )
    )
    if clause is None:
        raise ApplicationError("clause_not_found", "Clause was not found", status_code=404)
    return clause


async def _version_response(session: AsyncSession, standard: Standard) -> StandardResponse:
    versions = list(
        await session.scalars(
            select(StandardVersion)
            .where(StandardVersion.standard_id == standard.id)
            .order_by(StandardVersion.created_at.desc())
        )
    )
    return StandardResponse(
        id=standard.id,
        code=standard.code,
        title=standard.title,
        jurisdiction=standard.jurisdiction,
        versions=[StandardVersionResponse.model_validate(item) for item in versions],
    )


@router.post(
    "/ingestions", response_model=RegulationIngestResponse, status_code=status.HTTP_201_CREATED
)
async def ingest_regulation(
    payload: RegulationIngest,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
) -> RegulationIngestResponse:
    row = (
        await session.execute(
            select(FileVersion, Project)
            .join(ProjectFile, ProjectFile.id == FileVersion.project_file_id)
            .join(Project, Project.id == ProjectFile.project_id)
            .where(
                FileVersion.id == payload.file_version_id,
                Project.organization_id == actor.organization_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise ApplicationError(
            "file_version_not_found", "File version was not found", status_code=404
        )
    file_version, project = row
    standard = await session.scalar(
        select(Standard).where(
            Standard.organization_id == actor.organization_id,
            Standard.code == payload.code,
        )
    )
    if standard is None:
        standard = Standard(
            organization_id=actor.organization_id,
            code=payload.code,
            title=payload.title,
            jurisdiction=payload.jurisdiction,
        )
        session.add(standard)
        await session.flush()
    duplicate = await session.scalar(
        select(StandardVersion.id).where(
            StandardVersion.standard_id == standard.id,
            StandardVersion.edition == payload.edition,
        )
    )
    if duplicate:
        raise ApplicationError(
            "edition_already_exists", "This edition already exists", status_code=409
        )
    version = StandardVersion(
        standard_id=standard.id,
        edition=payload.edition,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        lifecycle_status="draft",
        source_file_version_id=file_version.id,
        document_hash=file_version.sha256,
    )
    session.add(version)
    await session.flush()
    job = Job(
        organization_id=actor.organization_id,
        project_id=project.id,
        file_version_id=file_version.id,
        job_type="regulation.parse",
        status=JobStatus.QUEUED,
        progress=0,
        input_data={"standard_version_id": str(version.id)},
        request_id=get_request_id(request),
    )
    session.add(job)
    await session.flush()
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="standard_version.ingestion_requested",
        entity_type="standard_version",
        entity_id=version.id,
        request_id=get_request_id(request),
        payload={"job_id": str(job.id)},
    )
    await session.commit()
    await dispatch_persisted_job(session, dispatcher, job)
    return RegulationIngestResponse(
        standard=await _version_response(session, standard),
        version=StandardVersionResponse.model_validate(version),
        job=JobResponse.model_validate(job),
    )


@router.get("", response_model=list[StandardResponse])
async def list_regulations(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> list[StandardResponse]:
    standards = list(
        await session.scalars(
            select(Standard)
            .where(Standard.organization_id == actor.organization_id)
            .order_by(Standard.code)
        )
    )
    return [await _version_response(session, item) for item in standards]


@router.get("/versions/{version_id}/pages", response_model=list[PageResponse])
async def list_pages(
    version_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> list[PageResponse]:
    version = await _owned_version(session, version_id, actor)
    pages = list(
        await session.scalars(
            select(DocumentPage)
            .where(DocumentPage.file_version_id == version.source_file_version_id)
            .order_by(DocumentPage.page_number)
        )
    )
    result = []
    for page in pages:
        image_url = None
        if page.image_object_key:
            image_url = await run_in_threadpool(
                storage.presigned_download, page.image_object_key, f"page-{page.page_number}.png"
            )
        result.append(PageResponse.model_validate(page).model_copy(update={"image_url": image_url}))
    return result


@router.get("/versions/{version_id}/clauses", response_model=list[ClauseResponse])
async def list_clauses(
    version_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    query: Annotated[str | None, Query(max_length=255)] = None,
) -> list[Clause]:
    await _owned_version(session, version_id, actor)
    statement = select(Clause).where(Clause.standard_version_id == version_id)
    if query:
        term = f"%{query}%"
        statement = statement.where(
            or_(Clause.clause_number.ilike(term), Clause.original_text.ilike(term))
        )
    return list(await session.scalars(statement.order_by(Clause.order_index)))


async def _save_revision(session: AsyncSession, clause: Clause, actor: Actor, reason: str) -> None:
    number = (
        await session.scalar(
            select(func.count())
            .select_from(ClauseRevision)
            .where(ClauseRevision.clause_id == clause.id)
        )
        or 0
    )
    session.add(
        ClauseRevision(
            clause_id=clause.id,
            revision_number=number + 1,
            clause_number=clause.clause_number,
            heading=clause.heading,
            original_text=clause.original_text,
            parent_id=clause.parent_id,
            bounding_box=clause.bounding_box,
            changed_by_id=actor.user_id,
            change_reason=reason,
        )
    )


def _ensure_draft(version: StandardVersion) -> None:
    if version.lifecycle_status == "published":
        raise ApplicationError(
            "published_version_immutable",
            "Published versions are immutable",
            status_code=409,
        )


@router.patch("/clauses/{clause_id}", response_model=ClauseResponse)
async def update_clause(
    clause_id: UUID,
    payload: ClauseUpdate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> Clause:
    clause = await _owned_clause(session, clause_id, actor)
    version = await session.get_one(StandardVersion, clause.standard_version_id)
    _ensure_draft(version)
    await _save_revision(session, clause, actor, payload.change_reason)
    changes = payload.model_dump(exclude={"change_reason"}, exclude_unset=True)
    for key, value in changes.items():
        setattr(clause, key, value)
    clause.lifecycle_status = "reviewed"
    clause.reviewed_by_id, clause.reviewed_at = actor.user_id, datetime.now(UTC)
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="clause.corrected",
        entity_type="clause",
        entity_id=clause.id,
        request_id=get_request_id(request),
        payload={"fields": sorted(changes)},
    )
    await session.commit()
    await session.refresh(clause)
    return clause


@router.post("/clauses/{clause_id}/split", response_model=list[ClauseResponse])
async def split_clause(
    clause_id: UUID,
    payload: ClauseSplit,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> list[Clause]:
    clause = await _owned_clause(session, clause_id, actor)
    version = await session.get_one(StandardVersion, clause.standard_version_id)
    _ensure_draft(version)
    await _save_revision(session, clause, actor, payload.change_reason)
    clause.original_text = payload.first_text
    clause.lifecycle_status = "reviewed"
    clause.reviewed_by_id, clause.reviewed_at = actor.user_id, datetime.now(UTC)
    second = Clause(
        standard_version_id=clause.standard_version_id,
        parent_id=clause.parent_id,
        source_page_id=clause.source_page_id,
        clause_number=payload.second_number,
        level=clause.level,
        original_text=payload.second_text,
        page_number=clause.page_number,
        bounding_box=clause.bounding_box,
        confidence=clause.confidence,
        order_index=clause.order_index + 1,
        lifecycle_status="reviewed",
        reviewed_by_id=actor.user_id,
        reviewed_at=datetime.now(UTC),
    )
    session.add(second)
    await session.commit()
    await session.refresh(clause)
    await session.refresh(second)
    return [clause, second]


@router.post("/clauses/merge", response_model=ClauseResponse)
async def merge_clauses(
    payload: ClauseMerge,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> Clause:
    clauses = list(
        await session.scalars(
            select(Clause).where(Clause.id.in_(payload.clause_ids)).order_by(Clause.order_index)
        )
    )
    if len(clauses) != len(set(payload.clause_ids)):
        raise ApplicationError(
            "clause_not_found", "One or more clauses were not found", status_code=404
        )
    owned = await _owned_clause(session, clauses[0].id, actor)
    if any(item.standard_version_id != owned.standard_version_id for item in clauses):
        raise ApplicationError(
            "cross_version_merge", "Clauses must belong to one version", status_code=409
        )
    version = await session.get_one(StandardVersion, owned.standard_version_id)
    _ensure_draft(version)
    for clause in clauses:
        await _save_revision(session, clause, actor, payload.change_reason)
    target = clauses[0]
    target.clause_number, target.original_text = payload.target_number, payload.merged_text
    target.lifecycle_status = "reviewed"
    target.reviewed_by_id, target.reviewed_at = actor.user_id, datetime.now(UTC)
    for clause in clauses[1:]:
        clause.clause_number = f"{clause.clause_number}#merged#{str(clause.id)[:8]}"
        clause.lifecycle_status = "archived"
    await session.commit()
    await session.refresh(target)
    return target


@router.post("/versions/{version_id}/publish", response_model=StandardVersionResponse)
async def publish_version(
    version_id: UUID,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> StandardVersion:
    version = await _owned_version(session, version_id, actor)
    clauses = list(
        await session.scalars(
            select(Clause).where(
                Clause.standard_version_id == version.id,
                Clause.lifecycle_status != "archived",
            )
        )
    )
    if not clauses or any(item.lifecycle_status != "reviewed" for item in clauses):
        raise ApplicationError(
            "clauses_require_review",
            "Every clause must be reviewed before publishing",
            status_code=409,
        )
    version.lifecycle_status = "published"
    for clause in clauses:
        clause.lifecycle_status = "published"
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="standard_version.published",
        entity_type="standard_version",
        entity_id=version.id,
        request_id=get_request_id(request),
        payload={"clause_count": len(clauses)},
    )
    await session.commit()
    await session.refresh(version)
    return version


@router.post("/versions/{version_id}/reparse", response_model=JobResponse)
async def reparse_version(
    version_id: UUID,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
) -> Job:
    version = await _owned_version(session, version_id, actor)
    _ensure_draft(version)
    clause_ids = select(Clause.id).where(Clause.standard_version_id == version.id)
    await session.execute(delete(Evidence).where(Evidence.clause_id.in_(clause_ids)))
    await session.execute(delete(ClauseRevision).where(ClauseRevision.clause_id.in_(clause_ids)))
    await session.execute(delete(Clause).where(Clause.standard_version_id == version.id))
    await session.execute(
        delete(DocumentPage).where(DocumentPage.file_version_id == version.source_file_version_id)
    )
    project_id = await session.scalar(
        select(Project.id)
        .join(ProjectFile, ProjectFile.project_id == Project.id)
        .join(FileVersion, FileVersion.project_file_id == ProjectFile.id)
        .where(FileVersion.id == version.source_file_version_id)
    )
    job = Job(
        organization_id=actor.organization_id,
        project_id=project_id,
        file_version_id=version.source_file_version_id,
        job_type="regulation.parse",
        status=JobStatus.QUEUED,
        progress=0,
        input_data={"standard_version_id": str(version.id)},
        request_id=get_request_id(request),
    )
    session.add(job)
    await session.commit()
    await dispatch_persisted_job(session, dispatcher, job)
    return job
