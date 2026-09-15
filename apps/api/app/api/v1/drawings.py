from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Actor, get_current_actor, get_request_id
from app.core.errors import ApplicationError
from app.db.models import (
    DocumentPage,
    Evidence,
    FileVersion,
    Job,
    Project,
    ProjectFact,
    ProjectFile,
)
from app.db.session import get_database_session
from app.domain.enums import JobStatus
from app.domain.m4_schemas import FactCandidateResponse, FactEvidenceResponse
from app.domain.m5_schemas import (
    DrawingAnnotationCreate,
    DrawingAnnotationResponse,
    DrawingExtractionCreate,
    DrawingExtractionResponse,
    DrawingPageResponse,
)
from app.services.audit import record_audit_event
from app.services.dispatch import JobDispatcher, dispatch_persisted_job, get_job_dispatcher
from app.services.drawing_pipeline import DRAWING_EXTRACTOR_VERSION, polyline_length
from app.services.fact_candidates import CandidateWrite, persist_fact_candidates
from app.services.storage import ObjectStorage, get_object_storage

router = APIRouter(tags=["drawings"])


async def _owned_file(
    session: AsyncSession, project_id: UUID, file_version_id: UUID, actor: Actor
) -> FileVersion:
    file_version = await session.scalar(
        select(FileVersion)
        .join(ProjectFile, ProjectFile.id == FileVersion.project_file_id)
        .join(Project, Project.id == ProjectFile.project_id)
        .where(
            FileVersion.id == file_version_id,
            Project.id == project_id,
            Project.organization_id == actor.organization_id,
        )
    )
    if file_version is None:
        raise ApplicationError(
            "file_version_not_found", "File version was not found", status_code=404
        )
    return file_version


async def _candidate_response(session: AsyncSession, fact: ProjectFact) -> FactCandidateResponse:
    evidence = list(
        await session.scalars(select(Evidence).where(Evidence.project_fact_id == fact.id))
    )
    return FactCandidateResponse.model_validate(fact).model_copy(
        update={"evidence": [FactEvidenceResponse.model_validate(item) for item in evidence]}
    )


@router.post(
    "/projects/{project_id}/drawing-extractions",
    response_model=DrawingExtractionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_drawing_extraction(
    project_id: UUID,
    payload: DrawingExtractionCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
) -> DrawingExtractionResponse:
    file_version = await _owned_file(session, project_id, payload.file_version_id, actor)
    if not file_version.original_filename.lower().endswith(".pdf"):
        raise ApplicationError(
            "unsupported_drawing",
            "The drawing pipeline currently accepts PDF drawings",
            status_code=415,
        )
    job = Job(
        organization_id=actor.organization_id,
        project_id=project_id,
        file_version_id=file_version.id,
        job_type="drawing.extract",
        status=JobStatus.QUEUED,
        progress=0,
        input_data={"file_version_id": str(file_version.id)},
        request_id=get_request_id(request),
    )
    session.add(job)
    await session.flush()
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="drawing_extraction.queued",
        entity_type="job",
        entity_id=job.id,
        request_id=get_request_id(request),
        payload={"file_version_id": str(file_version.id)},
    )
    await session.commit()
    await dispatch_persisted_job(session, dispatcher, job)
    return DrawingExtractionResponse(job=job)


@router.get(
    "/projects/{project_id}/drawings/{file_version_id}/pages",
    response_model=list[DrawingPageResponse],
)
async def list_drawing_pages(
    project_id: UUID,
    file_version_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> list[DrawingPageResponse]:
    await _owned_file(session, project_id, file_version_id, actor)
    pages = list(
        await session.scalars(
            select(DocumentPage)
            .where(DocumentPage.file_version_id == file_version_id)
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
        result.append(
            DrawingPageResponse(
                id=page.id,
                file_version_id=page.file_version_id,
                page_number=page.page_number,
                width=page.width,
                height=page.height,
                extraction_method=page.extraction_method,
                average_confidence=page.average_confidence,
                image_url=image_url,
            )
        )
    return result


@router.post(
    "/projects/{project_id}/drawing-annotations",
    response_model=DrawingAnnotationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_drawing_annotation(
    project_id: UUID,
    payload: DrawingAnnotationCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> DrawingAnnotationResponse:
    await _owned_file(session, project_id, payload.file_version_id, actor)
    value = payload.value
    unit = payload.unit
    if payload.annotation_kind == "path":
        value = polyline_length(
            [(point.x, point.y) for point in payload.points], payload.pixels_per_meter or 0
        )
        unit = "m"
    if payload.corrects_fact_id:
        corrected = await session.scalar(
            select(ProjectFact).where(
                ProjectFact.id == payload.corrects_fact_id, ProjectFact.project_id == project_id
            )
        )
        if corrected is None:
            raise ApplicationError(
                "fact_candidate_not_found",
                "Corrected fact candidate was not found",
                status_code=404,
            )
    location = {
        "page": payload.page_number,
        "annotation_kind": payload.annotation_kind,
        "bbox": payload.bbox,
        "points": [point.model_dump() for point in payload.points],
        "pixels_per_meter": payload.pixels_per_meter,
        "corrects_fact_id": str(payload.corrects_fact_id) if payload.corrects_fact_id else None,
        "method": "architect_annotation",
    }
    created_ids, _ = await persist_fact_candidates(
        session,
        organization_id=actor.organization_id,
        project_id=project_id,
        file_version_id=payload.file_version_id,
        candidates=[
            CandidateWrite(
                key=payload.fact_key,
                value=value,
                unit=unit,
                scope_data={
                    "page": payload.page_number,
                    "annotation_kind": payload.annotation_kind,
                },
                location=location,
                excerpt=payload.label,
                confidence=1.0,
            )
        ],
        source="drawing",
        evidence_kind="image_region",
        extractor_version=f"{DRAWING_EXTRACTOR_VERSION}.manual",
    )
    fact = await session.get_one(ProjectFact, UUID(created_ids[0]))
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="drawing_annotation.created",
        entity_type="project_fact",
        entity_id=fact.id,
        request_id=get_request_id(request),
        payload={"annotation_kind": payload.annotation_kind, "page": payload.page_number},
    )
    await session.commit()
    await session.refresh(fact)
    return DrawingAnnotationResponse(candidate=await _candidate_response(session, fact))
