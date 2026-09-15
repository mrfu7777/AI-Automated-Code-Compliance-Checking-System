from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from app.domain.m1_schemas import ApiModel
from app.domain.m3_schemas import CheckRunCreated


class IncrementalCheckRunCreate(ApiModel):
    baseline_run_id: UUID
    name: str = Field(default="Incremental compliance review", min_length=1, max_length=255)


class ChangeImpactResponse(ApiModel):
    baseline_run_id: UUID
    changed_fact_keys: list[str]
    affected_rule_ids: list[str]
    unaffected_rule_ids: list[str]


class DependencyGraphResponse(ApiModel):
    review_package_id: UUID
    nodes: list[dict[str, str]]
    edges: list[dict[str, str]]


class ConflictResolution(ApiModel):
    selected_rule_id: UUID
    note: str = Field(min_length=1, max_length=2000)


class ConflictResponse(ApiModel):
    id: str
    fact_key: str
    rule_ids: list[str]
    rule_codes: list[str]
    authority_levels: list[str]
    reason: str
    resolution: dict[str, Any] | None = None


class CheckComparisonItem(ApiModel):
    rule_code: str
    title: str
    change: str
    before_status: str | None
    after_status: str | None


class CheckComparisonResponse(ApiModel):
    baseline_run_id: UUID
    run_id: UUID
    summary: dict[str, int]
    items: list[CheckComparisonItem]


class IncrementalCreated(CheckRunCreated):
    impact: ChangeImpactResponse


class StandardRecommendation(ApiModel):
    standard_id: UUID
    standard_code: str
    standard_title: str
    standard_version_id: UUID
    edition: str
    jurisdiction: str
    recommended: bool
    reasons: list[str]
    warnings: list[str]


class ClauseDifference(ApiModel):
    clause_number: str
    change: str
    before_clause_id: UUID | None
    after_clause_id: UUID | None
    before_text: str | None
    after_text: str | None


class StandardVersionComparison(ApiModel):
    from_version_id: UUID
    to_version_id: UUID
    summary: dict[str, int]
    differences: list[ClauseDifference]
