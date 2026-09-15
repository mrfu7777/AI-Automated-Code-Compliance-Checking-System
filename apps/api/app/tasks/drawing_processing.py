from __future__ import annotations

import asyncio
import io
from typing import Any
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DocumentPage, FileVersion, Job
from app.db.session import async_session_factory, engine
from app.services.drawing_pipeline import DRAWING_EXTRACTOR_VERSION, DrawingPipeline
from app.services.fact_candidates import persist_fact_candidates
from app.services.job_runtime import run_persisted_job
from app.services.storage import get_object_storage
from app.tasks.celery_app import celery_app


async def extract_drawing(session: AsyncSession, job: Job) -> dict[str, Any]:
    if job.file_version_id is None or job.project_id is None:
        raise ValueError("Drawing extraction requires a project and file version")
    file_version = await session.get(FileVersion, job.file_version_id)
    if file_version is None:
        raise ValueError(f"File version {job.file_version_id} does not exist")
    storage = get_object_storage()
    extraction = DrawingPipeline(storage).extract(
        file_version.object_key, file_version.original_filename
    )
    await session.execute(
        delete(DocumentPage).where(DocumentPage.file_version_id == file_version.id)
    )
    for page in extraction.pages:
        image_key = f"{file_version.object_key}.drawing-pages/{page.page_number}.png"
        stream = io.BytesIO(page.image_png)
        storage.upload(image_key, stream, len(page.image_png), "image/png")
        confidence = (
            sum(line.confidence for line in page.lines) / len(page.lines) if page.lines else None
        )
        session.add(
            DocumentPage(
                file_version_id=file_version.id,
                page_number=page.page_number,
                width=page.width,
                height=page.height,
                extraction_method=page.method,
                text="\n".join(line.text for line in page.lines),
                char_count=sum(len(line.text) for line in page.lines),
                average_confidence=confidence,
                image_object_key=image_key,
            )
        )
    created_ids, conflicts = await persist_fact_candidates(
        session,
        organization_id=job.organization_id,
        project_id=job.project_id,
        file_version_id=file_version.id,
        candidates=extraction.candidates,
        source="drawing",
        evidence_kind="image_region",
        extractor_version=DRAWING_EXTRACTOR_VERSION,
    )
    job.progress = 0.95
    await session.flush()
    return {
        "processor": DRAWING_EXTRACTOR_VERSION,
        "file_version_id": str(file_version.id),
        "page_count": len(extraction.pages),
        "candidate_count": len(created_ids),
        "conflict_count": conflicts,
        "fact_candidate_ids": created_ids,
    }


async def run_drawing_job(job_id: UUID) -> None:
    await run_persisted_job(
        async_session_factory, job_id, extract_drawing, error_code="drawing_extraction_failed"
    )


async def _run_and_dispose(job_id: UUID) -> None:
    try:
        await run_drawing_job(job_id)
    finally:
        await engine.dispose()


@celery_app.task(name="drawings.extract")  # type: ignore[untyped-decorator]
def process_drawing(job_id: str) -> None:
    asyncio.run(_run_and_dispose(UUID(job_id)))
