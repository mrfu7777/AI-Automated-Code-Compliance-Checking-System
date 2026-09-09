from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job
from app.domain.enums import JobStatus


class JobDispatcher(Protocol):
    def dispatch(self, job_id: UUID, job_type: str) -> None: ...


class CeleryJobDispatcher:
    def dispatch(self, job_id: UUID, job_type: str) -> None:
        if job_type == "file.metadata":
            from app.tasks.file_processing import process_file_version

            process_file_version.delay(str(job_id))
            return
        if job_type == "regulation.parse":
            from app.tasks.regulation_processing import process_regulation

            process_regulation.delay(str(job_id))
            return
        raise ValueError(f"Unsupported job type: {job_type}")


async def dispatch_persisted_job(
    session: AsyncSession, dispatcher: JobDispatcher, job: Job
) -> None:
    """Dispatch a committed job and expose broker failures through the same Job record."""
    try:
        dispatcher.dispatch(job.id, job.job_type)
    except Exception as exception:
        job.status = JobStatus.FAILED
        job.error_data = {"code": "dispatch_failed", "message": str(exception)}
        job.completed_at = datetime.now(UTC)
        await session.commit()


def get_job_dispatcher() -> JobDispatcher:
    return CeleryJobDispatcher()
