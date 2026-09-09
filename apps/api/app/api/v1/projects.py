from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import IO, Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Actor, get_current_actor, get_request_id
from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.db.models import FileVersion, Job, Project, ProjectFile
from app.db.session import get_database_session
from app.domain.enums import JobStatus
from app.domain.m1_schemas import (
    DownloadResponse,
    FileVersionResponse,
    JobResponse,
    ProjectCreate,
    ProjectFileResponse,
    ProjectResponse,
    UploadResponse,
)
from app.services.audit import record_audit_event
from app.services.dispatch import JobDispatcher, dispatch_persisted_job, get_job_dispatcher
from app.services.storage import ObjectStorage, get_object_storage

router = APIRouter(prefix="/projects", tags=["projects"])
file_versions_router = APIRouter(prefix="/file-versions", tags=["files"])

PDF_MEDIA_TYPES = {"application/pdf", "application/x-pdf"}
CHUNK_SIZE = 1024 * 1024


async def _owned_project(session: AsyncSession, project_id: UUID, actor: Actor) -> Project:
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == actor.organization_id,
        )
    )
    if project is None:
        raise ApplicationError("project_not_found", "Project was not found", status_code=404)
    return project


async def _read_pdf(upload: UploadFile) -> tuple[IO[bytes], int, str]:
    settings = get_settings()
    filename = upload.filename or "upload.pdf"
    if Path(filename).suffix.lower() != ".pdf" or upload.content_type not in PDF_MEDIA_TYPES:
        raise ApplicationError(
            "unsupported_file_type", "M1 accepts PDF files only", status_code=415
        )

    stream: IO[bytes] = SpooledTemporaryFile(  # noqa: SIM115
        max_size=16 * 1024 * 1024, mode="w+b"
    )
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        while chunk := await upload.read(CHUNK_SIZE):
            size_bytes += len(chunk)
            if size_bytes > settings.max_upload_size_bytes:
                raise ApplicationError(
                    "file_too_large",
                    f"File exceeds the {settings.max_upload_size_bytes} byte limit",
                    status_code=413,
                )
            digest.update(chunk)
            stream.write(chunk)
        stream.seek(0)
        if size_bytes == 0 or stream.read(5) != b"%PDF-":
            raise ApplicationError(
                "invalid_pdf", "File does not contain a PDF header", status_code=422
            )
        stream.seek(0)
        return stream, size_bytes, digest.hexdigest()
    except Exception:
        stream.close()
        raise
    finally:
        await upload.close()


def _file_response(project_file: ProjectFile, versions: list[FileVersion]) -> ProjectFileResponse:
    return ProjectFileResponse(
        id=project_file.id,
        project_id=project_file.project_id,
        logical_name=project_file.logical_name,
        purpose=project_file.purpose,
        created_at=project_file.created_at,
        versions=[FileVersionResponse.model_validate(version) for version in versions],
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> Project:
    project = Project(organization_id=actor.organization_id, **payload.model_dump())
    session.add(project)
    await session.flush()
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="project.created",
        entity_type="project",
        entity_id=project.id,
        request_id=get_request_id(request),
        payload={"name": project.name},
    )
    await session.commit()
    await session.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> list[Project]:
    projects = await session.scalars(
        select(Project)
        .where(Project.organization_id == actor.organization_id)
        .order_by(Project.created_at.desc())
    )
    return list(projects)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> Project:
    return await _owned_project(session, project_id, actor)


@router.get("/{project_id}/files", response_model=list[ProjectFileResponse])
async def list_project_files(
    project_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> list[ProjectFileResponse]:
    await _owned_project(session, project_id, actor)
    files = list(
        await session.scalars(
            select(ProjectFile)
            .where(ProjectFile.project_id == project_id)
            .order_by(ProjectFile.created_at.desc())
        )
    )
    if not files:
        return []
    versions = list(
        await session.scalars(
            select(FileVersion)
            .where(FileVersion.project_file_id.in_([item.id for item in files]))
            .order_by(FileVersion.version_number.desc())
        )
    )
    versions_by_file: dict[UUID, list[FileVersion]] = {item.id: [] for item in files}
    for version in versions:
        if version.project_file_id is not None:
            versions_by_file[version.project_file_id].append(version)
    return [_file_response(item, versions_by_file[item.id]) for item in files]


@router.get("/{project_id}/jobs", response_model=list[JobResponse])
async def list_project_jobs(
    project_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> list[Job]:
    await _owned_project(session, project_id, actor)
    jobs = await session.scalars(
        select(Job)
        .where(
            Job.project_id == project_id,
            Job.organization_id == actor.organization_id,
        )
        .order_by(Job.created_at.desc())
    )
    return list(jobs)


@router.post(
    "/{project_id}/files",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_project_file(
    project_id: UUID,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    upload: Annotated[UploadFile, File()],
    logical_name: Annotated[str | None, Form(max_length=512)] = None,
    purpose: Annotated[str, Form(max_length=64)] = "project_document",
) -> UploadResponse:
    await _owned_project(session, project_id, actor)
    stream, size_bytes, sha256 = await _read_pdf(upload)
    filename = upload.filename or "upload.pdf"
    normalized_name = (logical_name or filename).strip()
    if not normalized_name:
        stream.close()
        raise ApplicationError("invalid_logical_name", "Logical name is required")

    object_key: str | None = None
    try:
        project_file = await session.scalar(
            select(ProjectFile)
            .where(
                ProjectFile.project_id == project_id,
                ProjectFile.logical_name == normalized_name,
            )
            .with_for_update()
        )
        if project_file is None:
            project_file = ProjectFile(
                project_id=project_id,
                logical_name=normalized_name,
                purpose=purpose,
            )
            session.add(project_file)
            await session.flush()

        latest_version = await session.scalar(
            select(func.max(FileVersion.version_number)).where(
                FileVersion.project_file_id == project_file.id
            )
        )
        version_number = (latest_version or 0) + 1
        version_id = uuid4()
        object_key = (
            f"organizations/{actor.organization_id}/projects/{project_id}/"
            f"files/{project_file.id}/versions/{version_number}/{version_id}.pdf"
        )
        await run_in_threadpool(
            storage.upload,
            object_key,
            stream,
            size_bytes,
            upload.content_type or "application/pdf",
        )
        file_version = FileVersion(
            id=version_id,
            project_file_id=project_file.id,
            version_number=version_number,
            original_filename=filename,
            media_type=upload.content_type or "application/pdf",
            size_bytes=size_bytes,
            sha256=sha256,
            object_key=object_key,
            uploaded_by_id=actor.user_id,
        )
        session.add(file_version)
        job = Job(
            organization_id=actor.organization_id,
            project_id=project_id,
            file_version_id=file_version.id,
            job_type="file.metadata",
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
            action="file_version.uploaded",
            entity_type="file_version",
            entity_id=file_version.id,
            request_id=get_request_id(request),
            payload={"job_id": str(job.id), "sha256": sha256, "size_bytes": size_bytes},
        )
        await session.commit()
        await session.refresh(project_file)
        await session.refresh(file_version)
        await session.refresh(job)
    except Exception:
        await session.rollback()
        if object_key is not None:
            await run_in_threadpool(storage.remove, object_key)
        raise
    finally:
        stream.close()

    await dispatch_persisted_job(session, dispatcher, job)
    await session.refresh(job)

    return UploadResponse(
        project_file=_file_response(project_file, [file_version]),
        file_version=FileVersionResponse.model_validate(file_version),
        job=JobResponse.model_validate(job),
    )


@file_versions_router.get("/{file_version_id}/download", response_model=DownloadResponse)
async def get_download_url(
    file_version_id: UUID,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> DownloadResponse:
    result = await session.execute(
        select(FileVersion, Project)
        .join(ProjectFile, ProjectFile.id == FileVersion.project_file_id)
        .join(Project, Project.id == ProjectFile.project_id)
        .where(
            FileVersion.id == file_version_id,
            Project.organization_id == actor.organization_id,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise ApplicationError(
            "file_version_not_found", "File version was not found", status_code=404
        )
    file_version, _project = row
    url = await run_in_threadpool(
        storage.presigned_download, file_version.object_key, file_version.original_filename
    )
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="file_version.download_url_created",
        entity_type="file_version",
        entity_id=file_version.id,
        request_id=get_request_id(request),
    )
    await session.commit()
    return DownloadResponse(url=url)
