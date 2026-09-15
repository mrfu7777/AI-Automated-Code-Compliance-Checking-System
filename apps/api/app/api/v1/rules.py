from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Actor, get_current_actor, get_request_id
from app.core.errors import ApplicationError
from app.db.models import Clause, Evidence, Rule, RulePack, Standard, StandardVersion
from app.db.session import get_database_session
from app.domain.enums import CheckStatus, Severity
from app.domain.m3_schemas import (
    RuleCreate,
    RulePackClone,
    RulePackCreate,
    RulePackResponse,
    RuleResponse,
    RuleTemplateResponse,
    RuleTrialRequest,
    RuleTrialResponse,
    RuleUpdate,
)
from app.services.audit import record_audit_event
from app.services.rule_engine import RuleValidationError, evaluate_rule, validate_expression
from app.services.rule_templates import RULE_TEMPLATES

router = APIRouter(tags=["rules"])


async def _owned_pack(session: AsyncSession, pack_id: UUID, actor: Actor) -> RulePack:
    pack = await session.scalar(
        select(RulePack)
        .join(StandardVersion)
        .join(Standard)
        .where(RulePack.id == pack_id, Standard.organization_id == actor.organization_id)
    )
    if pack is None:
        raise ApplicationError("rule_pack_not_found", "Rule pack was not found", status_code=404)
    return pack


async def _owned_rule(session: AsyncSession, rule_id: UUID, actor: Actor) -> tuple[Rule, RulePack]:
    row = (
        await session.execute(
            select(Rule, RulePack)
            .join(RulePack, RulePack.id == Rule.rule_pack_id)
            .join(StandardVersion)
            .join(Standard)
            .where(Rule.id == rule_id, Standard.organization_id == actor.organization_id)
        )
    ).one_or_none()
    if row is None:
        raise ApplicationError("rule_not_found", "Rule was not found", status_code=404)
    return row[0], row[1]


def _validate_rule(payload: RuleCreate | RuleUpdate) -> None:
    data = payload.model_dump(exclude_unset=True)
    try:
        if "expression" in data and data["expression"] is not None:
            validate_expression(data["expression"])
        if data.get("applicability"):
            validate_expression(data["applicability"])
        if data.get("severity") is not None:
            Severity(data["severity"])
        if data.get("missing_data_status") is not None:
            missing = CheckStatus(data["missing_data_status"])
            if missing not in {
                CheckStatus.INSUFFICIENT_INFORMATION,
                CheckStatus.MANUAL_REVIEW_REQUIRED,
            }:
                raise ValueError("Unsupported missing-data status")
    except (RuleValidationError, ValueError) as exception:
        raise ApplicationError("invalid_rule", str(exception), status_code=422) from exception


def _pack_hash(rules: list[Rule]) -> str:
    content = [
        {
            "applicability": rule.applicability,
            "code": rule.code,
            "expression": rule.expression,
            "inputs": rule.inputs,
            "missing_data_status": rule.missing_data_status,
            "severity": rule.severity,
            "source_clause_id": str(rule.source_clause_id),
            "title": rule.title,
        }
        for rule in sorted(rules, key=lambda item: item.code)
    ]
    canonical = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@router.get("/rule-templates", response_model=list[RuleTemplateResponse])
async def list_rule_templates() -> list[dict[str, Any]]:
    return [item.__dict__ for item in RULE_TEMPLATES]


@router.post("/rule-packs", response_model=RulePackResponse, status_code=status.HTTP_201_CREATED)
async def create_rule_pack(
    payload: RulePackCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> RulePack:
    version = await session.scalar(
        select(StandardVersion)
        .join(Standard)
        .where(
            StandardVersion.id == payload.standard_version_id,
            Standard.organization_id == actor.organization_id,
        )
    )
    if version is None:
        raise ApplicationError(
            "standard_version_not_found", "Standard version was not found", status_code=404
        )
    if version.lifecycle_status != "published":
        raise ApplicationError(
            "standard_version_not_published",
            "Rules can only reference a published standard version",
            status_code=409,
        )
    duplicate = await session.scalar(
        select(RulePack.id).where(
            RulePack.standard_version_id == version.id,
            RulePack.semantic_version == payload.semantic_version,
        )
    )
    if duplicate:
        raise ApplicationError(
            "rule_pack_version_exists", "Rule pack version exists", status_code=409
        )
    pack = RulePack(**payload.model_dump(), lifecycle_status="draft", content_hash="")
    session.add(pack)
    await session.flush()
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="rule_pack.created",
        entity_type="rule_pack",
        entity_id=pack.id,
        request_id=get_request_id(request),
    )
    await session.commit()
    await session.refresh(pack)
    return pack


@router.get("/rule-packs", response_model=list[RulePackResponse])
async def list_rule_packs(
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> list[RulePack]:
    return list(
        await session.scalars(
            select(RulePack)
            .join(StandardVersion)
            .join(Standard)
            .where(Standard.organization_id == actor.organization_id)
            .order_by(RulePack.created_at.desc())
        )
    )


@router.post("/rule-packs/{pack_id}/rules", response_model=RuleResponse, status_code=201)
async def create_rule(
    pack_id: UUID,
    payload: RuleCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> Rule:
    pack = await _owned_pack(session, pack_id, actor)
    if pack.lifecycle_status != "draft":
        raise ApplicationError(
            "published_rule_pack_immutable", "Published packs are immutable", status_code=409
        )
    clause = await session.scalar(
        select(Clause).where(
            Clause.id == payload.source_clause_id,
            Clause.standard_version_id == pack.standard_version_id,
            Clause.lifecycle_status == "published",
        )
    )
    if clause is None:
        raise ApplicationError(
            "published_clause_not_found",
            "The source clause must be published in the pack's standard version",
            status_code=409,
        )
    _validate_rule(payload)
    if await session.scalar(
        select(Rule.id).where(Rule.rule_pack_id == pack.id, Rule.code == payload.code)
    ):
        raise ApplicationError(
            "rule_code_exists", "Rule code already exists in this pack", status_code=409
        )
    rule = Rule(rule_pack_id=pack.id, lifecycle_status="draft", **payload.model_dump())
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


@router.get("/rule-packs/{pack_id}/rules", response_model=list[RuleResponse])
async def list_rules(
    pack_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> list[Rule]:
    await _owned_pack(session, pack_id, actor)
    return list(
        await session.scalars(select(Rule).where(Rule.rule_pack_id == pack_id).order_by(Rule.code))
    )


@router.patch("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: UUID,
    payload: RuleUpdate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> Rule:
    rule, pack = await _owned_rule(session, rule_id, actor)
    if pack.lifecycle_status != "draft":
        raise ApplicationError(
            "published_rule_pack_immutable", "Published packs are immutable", status_code=409
        )
    _validate_rule(payload)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    rule.lifecycle_status, rule.reviewed_by_id, rule.reviewed_at = "draft", None, None
    await session.commit()
    await session.refresh(rule)
    return rule


@router.post("/rules/{rule_id}/review", response_model=RuleResponse)
async def review_rule(
    rule_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> Rule:
    rule, pack = await _owned_rule(session, rule_id, actor)
    if pack.lifecycle_status != "draft":
        raise ApplicationError(
            "published_rule_pack_immutable", "Published packs are immutable", status_code=409
        )
    rule.lifecycle_status = "reviewed"
    rule.reviewed_by_id, rule.reviewed_at = actor.user_id, datetime.now(UTC)
    await session.commit()
    await session.refresh(rule)
    return rule


@router.post("/rule-packs/{pack_id}/publish", response_model=RulePackResponse)
async def publish_rule_pack(
    pack_id: UUID,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> RulePack:
    pack = await _owned_pack(session, pack_id, actor)
    if pack.lifecycle_status == "published":
        return pack
    rules = list(await session.scalars(select(Rule).where(Rule.rule_pack_id == pack.id)))
    if not rules or any(rule.lifecycle_status != "reviewed" for rule in rules):
        raise ApplicationError(
            "rules_require_review", "Every rule must be reviewed before publishing", status_code=409
        )
    pack.content_hash = _pack_hash(rules)
    pack.lifecycle_status = "published"
    pack.published_by_id, pack.published_at = actor.user_id, datetime.now(UTC)
    for rule in rules:
        rule.lifecycle_status = "published"
    record_audit_event(
        session,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
        action="rule_pack.published",
        entity_type="rule_pack",
        entity_id=pack.id,
        request_id=get_request_id(request),
        payload={"content_hash": pack.content_hash, "rule_count": len(rules)},
    )
    await session.commit()
    await session.refresh(pack)
    return pack


@router.post("/rule-packs/{pack_id}/clone", response_model=RulePackResponse, status_code=201)
async def clone_rule_pack(
    pack_id: UUID,
    payload: RulePackClone,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> RulePack:
    source = await _owned_pack(session, pack_id, actor)
    if source.lifecycle_status != "published":
        raise ApplicationError(
            "source_pack_not_published", "Only published packs can be cloned", status_code=409
        )
    duplicate = await session.scalar(
        select(RulePack.id).where(
            RulePack.standard_version_id == source.standard_version_id,
            RulePack.semantic_version == payload.semantic_version,
        )
    )
    if duplicate:
        raise ApplicationError(
            "rule_pack_version_exists", "Rule pack version exists", status_code=409
        )
    clone = RulePack(
        standard_version_id=source.standard_version_id,
        name=source.name,
        semantic_version=payload.semantic_version,
        authority_level=source.authority_level,
        lifecycle_status="draft",
        content_hash="",
    )
    session.add(clone)
    await session.flush()
    source_rules = list(await session.scalars(select(Rule).where(Rule.rule_pack_id == source.id)))
    for item in source_rules:
        session.add(
            Rule(
                rule_pack_id=clone.id,
                source_clause_id=item.source_clause_id,
                code=item.code,
                title=item.title,
                severity=item.severity,
                lifecycle_status="draft",
                applicability=item.applicability,
                inputs=item.inputs,
                expression=item.expression,
                missing_data_status=item.missing_data_status,
            )
        )
    await session.commit()
    await session.refresh(clone)
    return clone


@router.post("/rules/{rule_id}/trial", response_model=RuleTrialResponse)
async def trial_rule(
    rule_id: UUID,
    payload: RuleTrialRequest,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> RuleTrialResponse:
    rule, _pack = await _owned_rule(session, rule_id, actor)
    clause = await session.get_one(Clause, rule.source_clause_id)
    evidence_ids = [
        str(item)
        for item in await session.scalars(
            select(Evidence.id).where(Evidence.clause_id == clause.id)
        )
    ]
    result = evaluate_rule(
        title=rule.title,
        applicability=rule.applicability,
        expression=rule.expression,
        inputs=rule.inputs,
        missing_data_status=rule.missing_data_status,
        facts=payload.facts,
    )
    return RuleTrialResponse(
        status=result.status,
        message=result.message,
        fact_keys=result.fact_keys,
        operations=result.operations,
        clause={
            "id": str(clause.id),
            "number": clause.clause_number,
            "original_text": clause.original_text,
            "page_number": clause.page_number,
            "evidence_ids": evidence_ids,
        },
    )
