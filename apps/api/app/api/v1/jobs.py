from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Actor, get_current_actor, get_request_id
from app.core.errors import ApplicationError
from app.db.models import Job
from app.db.session import get_database_session
from app.domain.enums import JobStatus
from app.domain.m1_schemas import JobResponse
from app.services.audit import record_audit_event
from app.services.dispatch import JobDispatcher, get_job_dispatcher

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _owned_job(session: AsyncSession, job_id: UUID, actor: Actor) -> Job:
    job = await session.scalar(
        select(Job).where(
            Job.id == job_id,
            Job.organization_id == actor.organization_id,
        )
    )
    if job is None:
        raise ApplicationError("job_not_found", "Job was not found", status_code=404)
    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> Job:
    return await _owned_job(session, job_id, actor)


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: UUID,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
) -> Job:
    job = await _owned_job(session, job_id, actor)
    if job.status != JobStatus.FAILED:
        raise ApplicationError(
            "job_not_retryable", "Only failed jobs can be retried", status_code=409
        )
    if job.attempts >= job.max_attempts:
        raise ApplicationError(
            "job_attempts_exhausted", "Job has reached its retry limit", status_code=409
        )

    job.status = JobStatus.QUEUED
    job.progress = 0
    job.error_data = None
    job.started_at = None
    job.completed_at = None
    job.request_id = get_request_id(request)
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="job.retry_requested",
        entity_type="job",
        entity_id=job.id,
        request_id=job.request_id,
        payload={"next_attempt": job.attempts + 1},
    )
    await session.commit()
    try:
        dispatcher.dispatch_file_processing(job.id)
    except Exception as exception:
        job.status = JobStatus.FAILED
        job.error_data = {"code": "dispatch_failed", "message": str(exception)}
        job.completed_at = datetime.now(UTC)
        await session.commit()
    await session.refresh(job)
    return job
