from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Job
from app.domain.enums import JobStatus
from app.services.audit import record_audit_event

JobProcessor = Callable[[AsyncSession, Job], Awaitable[dict[str, Any]]]


async def run_persisted_job(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: UUID,
    processor: JobProcessor,
    *,
    error_code: str,
) -> None:
    """Apply one lifecycle implementation to every durable background job."""
    async with session_factory() as session:
        job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None:
            raise ValueError(f"Job {job_id} does not exist")
        if job.status != JobStatus.QUEUED:
            return
        job.status = JobStatus.RUNNING
        job.progress = 0.05
        job.attempts += 1
        job.started_at = datetime.now(UTC)
        job.completed_at = None
        await session.commit()
        try:
            job.output_data = await processor(session, job)
            job.status = JobStatus.SUCCEEDED
            job.progress = 1
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
                payload={"attempt": job.attempts, "job_type": job.job_type},
            )
            await session.commit()
        except Exception as exception:
            await session.rollback()
            job = await session.get(Job, job_id)
            if job is not None:
                job.status = JobStatus.FAILED
                job.error_data = {"code": error_code, "message": str(exception)}
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
