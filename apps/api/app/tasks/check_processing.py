from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery.utils.log import get_task_logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CheckResult, CheckRun, Job, ReviewPackage
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
    package = await session.get_one(ReviewPackage, run.review_package_id)
    unresolved_rules: set[str] = set()
    excluded_rules: set[str] = set()
    for conflict in package.conflict_candidates:
        resolution = run.conflict_resolution_snapshot.get(conflict["id"])
        if resolution is None:
            unresolved_rules.update(conflict["rule_ids"])
        else:
            excluded_rules.update(
                rule_id
                for rule_id in conflict["rule_ids"]
                if rule_id != resolution["selected_rule_id"]
            )
    baseline_results: dict[str, CheckResult] = {}
    if run.run_mode == "incremental" and run.baseline_run_id is not None:
        baseline_results = {
            str(item.rule_id): item
            for item in await session.scalars(
                select(CheckResult).where(CheckResult.check_run_id == run.baseline_run_id)
            )
        }
    affected = set(run.affected_rule_ids)
    counts: dict[str, int] = {}
    for pack in run.rule_pack_snapshot:
        for rule in pack["rules"]:
            rule_id = str(rule["id"])
            copied = (
                run.run_mode == "incremental"
                and rule_id not in affected
                and rule_id in baseline_results
            )
            if copied:
                baseline_result = baseline_results[rule_id]
                result_values = {
                    "status": baseline_result.status,
                    "message": baseline_result.message,
                    "fact_ids": baseline_result.fact_ids,
                    "regulation_evidence_ids": baseline_result.regulation_evidence_ids,
                    "project_evidence_ids": baseline_result.project_evidence_ids,
                    "trace": {
                        **baseline_result.trace,
                        "incremental": {
                            "executed": False,
                            "baseline_result_id": str(baseline_result.id),
                        },
                    },
                }
            elif rule_id in unresolved_rules:
                result_values = {
                    "status": "manual_review_required",
                    "message": "A cross-code conflict requires human resolution before evaluation.",
                    "fact_ids": [],
                    "regulation_evidence_ids": rule["clause"]["evidence_ids"],
                    "project_evidence_ids": [],
                    "trace": {
                        "engine_version": run.engine_version,
                        "clause": rule["clause"],
                        "conflict": "unresolved",
                    },
                }
            elif rule_id in excluded_rules:
                result_values = {
                    "status": "not_applicable",
                    "message": "Excluded by a recorded human conflict resolution.",
                    "fact_ids": [],
                    "regulation_evidence_ids": rule["clause"]["evidence_ids"],
                    "project_evidence_ids": [],
                    "trace": {
                        "engine_version": run.engine_version,
                        "clause": rule["clause"],
                        "conflict": "human_resolved_exclusion",
                    },
                }
            else:
                evaluation = evaluate_rule(
                    title=rule["title"],
                    applicability=rule["applicability"],
                    expression=rule["expression"],
                    inputs=rule["inputs"],
                    missing_data_status=rule["missing_data_status"],
                    facts=facts,
                )
                used = [
                    fact_snapshots[key] for key in evaluation.fact_keys if key in fact_snapshots
                ]
                result_values = {
                    "status": str(evaluation.status),
                    "message": evaluation.message,
                    "fact_ids": [item["id"] for item in used],
                    "regulation_evidence_ids": rule["clause"]["evidence_ids"],
                    "project_evidence_ids": [
                        evidence_id for item in used for evidence_id in item["evidence_ids"]
                    ],
                    "trace": {
                        "engine_version": run.engine_version,
                        "resolved_inputs": used,
                        "operations": evaluation.operations,
                        "clause": rule["clause"],
                        "incremental": {
                            "executed": run.run_mode == "incremental",
                            "changed_fact_keys": run.changed_fact_keys,
                        },
                    },
                }
            status = str(result_values["status"])
            counts[status] = counts.get(status, 0) + 1
            session.add(
                CheckResult(
                    check_run_id=run.id,
                    rule_id=UUID(rule["id"]),
                    severity=rule["severity"],
                    **result_values,
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
