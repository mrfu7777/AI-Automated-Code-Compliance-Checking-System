import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db.models import FileVersion, Job
from app.db.session import async_session_factory, engine
from app.domain.enums import JobStatus
from app.services.audit import record_audit_event
from app.services.storage import get_object_storage
from app.tasks.celery_app import celery_app


async def run_file_processing_job(job_id: UUID) -> None:
    async with async_session_factory() as session:
        job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None:
            raise ValueError(f"Job {job_id} does not exist")
        if job.status != JobStatus.QUEUED:
            return
        if job.file_version_id is None:
            raise ValueError(f"Job {job_id} has no file version")

        job.status = JobStatus.RUNNING
        job.progress = 0.25
        job.attempts += 1
        job.started_at = datetime.now(UTC)
        job.completed_at = None
        await session.commit()

        try:
            file_version = await session.get(FileVersion, job.file_version_id)
            if file_version is None:
                raise ValueError(f"File version {job.file_version_id} does not exist")
            stored = get_object_storage().stat(file_version.object_key)
            if stored.size_bytes != file_version.size_bytes:
                raise ValueError("Stored object size does not match file metadata")

            job.status = JobStatus.SUCCEEDED
            job.progress = 1
            job.output_data = {
                "processor": "m1.file-metadata.v1",
                "file_version_id": str(file_version.id),
                "object_key": file_version.object_key,
                "size_bytes": stored.size_bytes,
                "sha256": file_version.sha256,
                "etag": stored.etag,
            }
            job.error_data = None
            job.completed_at = datetime.now(UTC)
            record_audit_event(
                session,
                organization_id=job.organization_id,
                actor_id=None,
                action="job.succeeded",
                entity_type="job",
                entity_id=job.id,
                request_id=job.request_id,
                payload={"attempt": job.attempts},
            )
            await session.commit()
        except Exception as exception:
            job.status = JobStatus.FAILED
            job.error_data = {
                "code": "file_processing_failed",
                "message": str(exception),
            }
            job.completed_at = datetime.now(UTC)
            record_audit_event(
                session,
                organization_id=job.organization_id,
                actor_id=None,
                action="job.failed",
                entity_type="job",
                entity_id=job.id,
                request_id=job.request_id,
                payload={"attempt": job.attempts, "error": str(exception)},
            )
            await session.commit()
            raise


async def _run_and_dispose(job_id: UUID) -> None:
    try:
        await run_file_processing_job(job_id)
    finally:
        await engine.dispose()


@celery_app.task(name="files.process_metadata")  # type: ignore[untyped-decorator]
def process_file_version(job_id: str) -> None:
    asyncio.run(_run_and_dispose(UUID(job_id)))
