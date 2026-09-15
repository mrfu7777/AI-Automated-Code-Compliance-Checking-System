from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FileVersion, Job
from app.db.session import async_session_factory, engine
from app.services.fact_candidates import CandidateWrite, persist_fact_candidates
from app.services.job_runtime import run_persisted_job
from app.services.project_extraction import EXTRACTOR_VERSION, ProjectDocumentExtractor
from app.services.storage import get_object_storage
from app.tasks.celery_app import celery_app


async def extract_project_facts(session: AsyncSession, job: Job) -> dict[str, Any]:
    if job.file_version_id is None or job.project_id is None:
        raise ValueError("Project extraction requires a project and file version")
    file_version = await session.get(FileVersion, job.file_version_id)
    if file_version is None:
        raise ValueError(f"File version {job.file_version_id} does not exist")
    document_kind, candidates = ProjectDocumentExtractor(get_object_storage()).extract(
        file_version.object_key, file_version.original_filename
    )
    source = (
        "ifc"
        if document_kind == "ifc"
        else "spreadsheet"
        if document_kind == "xlsx"
        else "document"
    )
    evidence_kind = {
        "pdf": "document_region",
        "docx": "document_region",
        "xlsx": "spreadsheet_range",
        "ifc": "ifc_object",
    }[document_kind]
    created_ids, conflicts = await persist_fact_candidates(
        session,
        organization_id=job.organization_id,
        project_id=job.project_id,
        file_version_id=file_version.id,
        candidates=(CandidateWrite(**candidate.__dict__) for candidate in candidates),
        source=source,
        evidence_kind=evidence_kind,
        extractor_version=EXTRACTOR_VERSION,
    )
    job.progress = 0.95
    await session.flush()
    return {
        "processor": EXTRACTOR_VERSION,
        "document_kind": document_kind,
        "file_version_id": str(file_version.id),
        "candidate_count": len(created_ids),
        "conflict_count": conflicts,
        "fact_candidate_ids": created_ids,
    }


async def run_project_extraction_job(job_id: UUID) -> None:
    await run_persisted_job(
        async_session_factory,
        job_id,
        extract_project_facts,
        error_code="project_extraction_failed",
    )


async def _run_and_dispose(job_id: UUID) -> None:
    try:
        await run_project_extraction_job(job_id)
    finally:
        await engine.dispose()


@celery_app.task(name="projects.extract")  # type: ignore[untyped-decorator]
def process_project_extraction(job_id: str) -> None:
    asyncio.run(_run_and_dispose(UUID(job_id)))
