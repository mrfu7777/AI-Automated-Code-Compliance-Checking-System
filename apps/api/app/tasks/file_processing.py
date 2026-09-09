import asyncio
from uuid import UUID

from app.db.models import FileVersion, Job
from app.db.session import async_session_factory, engine
from app.services.job_runtime import run_persisted_job
from app.services.storage import get_object_storage
from app.tasks.celery_app import celery_app


async def run_file_processing_job(job_id: UUID) -> None:
    async def process(session, job: Job):  # type: ignore[no-untyped-def]
        if job.file_version_id is None:
            raise ValueError(f"Job {job_id} has no file version")
        file_version = await session.get(FileVersion, job.file_version_id)
        if file_version is None:
            raise ValueError(f"File version {job.file_version_id} does not exist")
        stored = get_object_storage().stat(file_version.object_key)
        if stored.size_bytes != file_version.size_bytes:
            raise ValueError("Stored object size does not match file metadata")
        return {
            "processor": "m1.file-metadata.v1",
            "file_version_id": str(file_version.id),
            "object_key": file_version.object_key,
            "size_bytes": stored.size_bytes,
            "sha256": file_version.sha256,
            "etag": stored.etag,
        }

    await run_persisted_job(
        async_session_factory, job_id, process, error_code="file_processing_failed"
    )


async def _run_and_dispose(job_id: UUID) -> None:
    try:
        await run_file_processing_job(job_id)
    finally:
        await engine.dispose()


@celery_app.task(name="files.process_metadata")  # type: ignore[untyped-decorator]
def process_file_version(job_id: str) -> None:
    asyncio.run(_run_and_dispose(UUID(job_id)))
