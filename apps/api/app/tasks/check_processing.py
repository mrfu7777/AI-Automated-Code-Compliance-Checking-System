from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery.utils.log import get_task_logger
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CheckResult, CheckRun, Job
from app.db.session import async_session_factory, engine
from app.services.job_runtime import run_persisted_job
from app.services.rule_engine import evaluate_rule
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


async def execute_check(session: AsyncSession, job: Job) -> dict[str, Any]:
    run_id = UUID(str(job.input_data["check_run_id"]))
    run = await session.get(CheckRun, run_id)
    if run is None:
        raise ValueError(f"Check run {run_id} does not exist")
    run.status = "running"
    run.started_at = datetime.now(UTC)
    await session.execute(delete(CheckResult).where(CheckResult.check_run_id == run.id))

    facts = {
        item["key"]: {"value": item["value"], "unit": item.get("unit")}
        for item in run.project_snapshot["facts"]
    }
    fact_snapshots = {item["key"]: item for item in run.project_snapshot["facts"]}
    counts: dict[str, int] = {}
    for pack in run.rule_pack_snapshot:
        for rule in pack["rules"]:
            evaluation = evaluate_rule(
                title=rule["title"],
                applicability=rule["applicability"],
                expression=rule["expression"],
                inputs=rule["inputs"],
                missing_data_status=rule["missing_data_status"],
                facts=facts,
            )
            status = str(evaluation.status)
            counts[status] = counts.get(status, 0) + 1
            used = [fact_snapshots[key] for key in evaluation.fact_keys if key in fact_snapshots]
            session.add(
                CheckResult(
                    check_run_id=run.id,
                    rule_id=UUID(rule["id"]),
                    status=status,
                    severity=rule["severity"],
                    message=evaluation.message,
                    fact_ids=[item["id"] for item in used],
                    regulation_evidence_ids=rule["clause"]["evidence_ids"],
                    project_evidence_ids=[
                        evidence_id for item in used for evidence_id in item["evidence_ids"]
                    ],
                    trace={
                        "engine_version": run.engine_version,
                        "resolved_inputs": used,
                        "operations": evaluation.operations,
                        "clause": rule["clause"],
                    },
                )
            )
    run.status = "completed"
    run.completed_at = datetime.now(UTC)
    await session.flush()
    return {"check_run_id": str(run.id), "result_counts": counts}


async def run_check_processing_job(job_id: UUID) -> None:
    await run_persisted_job(
        async_session_factory,
        job_id,
        execute_check,
        error_code="check_run_failed",
    )


async def _run_and_dispose(job_id: UUID) -> None:
    try:
        await run_check_processing_job(job_id)
    finally:
        await engine.dispose()


@celery_app.task(name="checks.run")  # type: ignore[untyped-decorator]
def process_check_run(job_id: str) -> None:
    logger.info("Starting check job %s", job_id)
    asyncio.run(_run_and_dispose(UUID(job_id)))
