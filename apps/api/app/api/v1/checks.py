from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Actor, get_current_actor, get_request_id
from app.core.errors import ApplicationError
from app.db.models import (
    CheckResult,
    CheckRun,
    Clause,
    Evidence,
    Job,
    Project,
    ProjectFact,
    ReviewPackage,
    ReviewPackageRulePack,
    Rule,
    RulePack,
    Standard,
    StandardVersion,
)
from app.db.session import get_database_session
from app.domain.enums import JobStatus
from app.domain.m1_schemas import JobResponse
from app.domain.m3_schemas import (
    CheckResultResponse,
    CheckRunCreate,
    CheckRunCreated,
    CheckRunResponse,
)
from app.services.audit import record_audit_event
from app.services.dispatch import JobDispatcher, dispatch_persisted_job, get_job_dispatcher
from app.services.rule_engine import ENGINE_VERSION

router = APIRouter(tags=["checks"])


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


async def _owned_run(session: AsyncSession, run_id: UUID, actor: Actor) -> CheckRun:
    run = await session.scalar(
        select(CheckRun)
        .join(ReviewPackage)
        .join(Project)
        .where(CheckRun.id == run_id, Project.organization_id == actor.organization_id)
    )
    if run is None:
        raise ApplicationError("check_run_not_found", "Check run was not found", status_code=404)
    return run


async def _run_response(session: AsyncSession, run: CheckRun) -> CheckRunResponse:
    results = list(
        await session.scalars(
            select(CheckResult)
            .where(CheckResult.check_run_id == run.id)
            .order_by(CheckResult.created_at)
        )
    )
    response = CheckRunResponse.model_validate(run)
    return response.model_copy(
        update={"results": [CheckResultResponse.model_validate(item) for item in results]}
    )


async def _project_snapshot(session: AsyncSession, project_id: UUID) -> dict[str, Any]:
    rows = list(
        await session.scalars(
            select(ProjectFact)
            .where(
                ProjectFact.project_id == project_id,
                ProjectFact.verification_status == "verified",
            )
            .order_by(ProjectFact.created_at.desc())
        )
    )
    superseded_ids = {fact.supersedes_id for fact in rows if fact.supersedes_id is not None}
    latest: dict[tuple[str, str], ProjectFact] = {}
    for fact in rows:
        if fact.id in superseded_ids:
            continue
        scope = json.dumps(fact.scope_data, sort_keys=True, separators=(",", ":"))
        latest.setdefault((fact.key, scope), fact)
    facts = []
    for fact in latest.values():
        evidence_ids = [
            str(item)
            for item in await session.scalars(
                select(Evidence.id).where(Evidence.project_fact_id == fact.id)
            )
        ]
        facts.append(
            {
                "id": str(fact.id),
                "key": fact.key,
                "value": fact.value,
                "unit": fact.unit,
                "scope_data": fact.scope_data,
                "source": fact.source,
                "verified_at": fact.verified_at.isoformat() if fact.verified_at else None,
                "evidence_ids": evidence_ids,
            }
        )
    return {"project_id": str(project_id), "facts": sorted(facts, key=lambda item: item["key"])}


async def _pack_snapshot(session: AsyncSession, packs: list[RulePack]) -> list[dict[str, Any]]:
    result = []
    for pack in sorted(packs, key=lambda item: str(item.id)):
        rules = list(
            await session.scalars(
                select(Rule).where(Rule.rule_pack_id == pack.id).order_by(Rule.code)
            )
        )
        snapshots = []
        for rule in rules:
            clause = await session.get_one(Clause, rule.source_clause_id)
            evidence_ids = [
                str(item)
                for item in await session.scalars(
                    select(Evidence.id).where(Evidence.clause_id == clause.id)
                )
            ]
            snapshots.append(
                {
                    "id": str(rule.id),
                    "code": rule.code,
                    "title": rule.title,
                    "severity": rule.severity,
                    "applicability": rule.applicability,
                    "inputs": rule.inputs,
                    "expression": rule.expression,
                    "missing_data_status": rule.missing_data_status,
                    "clause": {
                        "id": str(clause.id),
                        "number": clause.clause_number,
                        "original_text": clause.original_text,
                        "page_number": clause.page_number,
                        "evidence_ids": evidence_ids,
                    },
                }
            )
        result.append(
            {
                "id": str(pack.id),
                "name": pack.name,
                "semantic_version": pack.semantic_version,
                "content_hash": pack.content_hash,
                "rules": snapshots,
            }
        )
    return result


@router.post("/check-runs", response_model=CheckRunCreated, status_code=status.HTTP_201_CREATED)
async def create_check_run(
    payload: CheckRunCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
) -> CheckRunCreated:
    project = await session.scalar(
        select(Project).where(
            Project.id == payload.project_id, Project.organization_id == actor.organization_id
        )
    )
    if project is None:
        raise ApplicationError("project_not_found", "Project was not found", status_code=404)
    pack_ids = list(dict.fromkeys(payload.rule_pack_ids))
    packs = list(
        await session.scalars(
            select(RulePack)
            .join(StandardVersion)
            .join(Standard)
            .where(
                RulePack.id.in_(pack_ids),
                RulePack.lifecycle_status == "published",
                Standard.organization_id == actor.organization_id,
            )
        )
    )
    if len(packs) != len(pack_ids):
        raise ApplicationError(
            "published_rule_pack_not_found",
            "Every selected rule pack must exist and be published",
            status_code=409,
        )
    project_snapshot = await _project_snapshot(session, project.id)
    rule_snapshot = await _pack_snapshot(session, packs)
    input_hash = _canonical_hash({"project": project_snapshot, "rule_packs": rule_snapshot})
    package = ReviewPackage(
        project_id=project.id,
        name=payload.name,
        status="frozen",
        project_snapshot_hash=_canonical_hash(project_snapshot),
    )
    session.add(package)
    await session.flush()
    for pack in packs:
        session.add(ReviewPackageRulePack(review_package_id=package.id, rule_pack_id=pack.id))
    run = CheckRun(
        review_package_id=package.id,
        status="queued",
        project_snapshot=project_snapshot,
        rule_pack_snapshot=rule_snapshot,
        engine_version=ENGINE_VERSION,
        input_hash=input_hash,
    )
    session.add(run)
    await session.flush()
    job = Job(
        organization_id=actor.organization_id,
        project_id=project.id,
        job_type="check.run",
        status=JobStatus.QUEUED,
        progress=0,
        input_data={"check_run_id": str(run.id)},
        request_id=get_request_id(request),
    )
    session.add(job)
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="check_run.queued",
        entity_type="check_run",
        entity_id=run.id,
        request_id=get_request_id(request),
        payload={"input_hash": input_hash, "rule_pack_ids": [str(item) for item in pack_ids]},
    )
    await session.commit()
    await dispatch_persisted_job(session, dispatcher, job)
    return CheckRunCreated(
        run=await _run_response(session, run), job=JobResponse.model_validate(job)
    )


@router.get("/check-runs/{run_id}", response_model=CheckRunResponse)
async def get_check_run(
    run_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> CheckRunResponse:
    return await _run_response(session, await _owned_run(session, run_id, actor))


@router.get("/projects/{project_id}/check-runs", response_model=list[CheckRunResponse])
async def list_check_runs(
    project_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> list[CheckRunResponse]:
    owned = await session.scalar(
        select(Project.id).where(
            Project.id == project_id, Project.organization_id == actor.organization_id
        )
    )
    if owned is None:
        raise ApplicationError("project_not_found", "Project was not found", status_code=404)
    runs = list(
        await session.scalars(
            select(CheckRun)
            .join(ReviewPackage)
            .where(ReviewPackage.project_id == project_id)
            .order_by(CheckRun.created_at.desc())
        )
    )
    return [await _run_response(session, item) for item in runs]


@router.get("/check-runs/{run_id}/export")
async def export_check_run(
    run_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> JSONResponse:
    response = await _run_response(session, await _owned_run(session, run_id, actor))
    return JSONResponse(
        content=response.model_dump(mode="json"),
        headers={"Content-Disposition": f'attachment; filename="check-run-{run_id}.json"'},
    )
