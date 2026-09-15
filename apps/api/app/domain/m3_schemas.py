from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.domain.m1_schemas import ApiModel, JobResponse


class RuleTemplateResponse(ApiModel):
    key: str
    title: str
    severity: str
    inputs: list[dict[str, Any]]
    applicability: dict[str, Any]
    expression: dict[str, Any]


class RulePackCreate(ApiModel):
    standard_version_id: UUID
    name: str = Field(min_length=1, max_length=255)
    semantic_version: str = Field(pattern=r"^\d+\.\d+\.\d+$", max_length=32)


class RulePackClone(ApiModel):
    semantic_version: str = Field(pattern=r"^\d+\.\d+\.\d+$", max_length=32)


class RulePackResponse(ApiModel):
    id: UUID
    standard_version_id: UUID
    name: str
    semantic_version: str
    lifecycle_status: str
    content_hash: str
    published_at: datetime | None
    published_by_id: UUID | None
    created_at: datetime
    updated_at: datetime


class RuleWrite(ApiModel):
    source_clause_id: UUID
    code: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=512)
    severity: str
    applicability: dict[str, Any] = Field(default_factory=dict)
    inputs: list[dict[str, Any]] = Field(default_factory=list)
    expression: dict[str, Any]
    missing_data_status: str = "insufficient_information"


class RuleCreate(RuleWrite):
    pass


class RuleUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    severity: str | None = None
    applicability: dict[str, Any] | None = None
    inputs: list[dict[str, Any]] | None = None
    expression: dict[str, Any] | None = None
    missing_data_status: str | None = None


class RuleResponse(RuleWrite):
    id: UUID
    rule_pack_id: UUID
    lifecycle_status: str
    reviewed_by_id: UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RuleTrialRequest(ApiModel):
    facts: dict[str, dict[str, Any]]


class RuleTrialResponse(ApiModel):
    status: str
    message: str
    fact_keys: list[str]
    operations: list[dict[str, Any]]
    clause: dict[str, Any]


class ProjectFactCreate(ApiModel):
    key: str = Field(min_length=1, max_length=255)
    value: Any
    unit: str | None = Field(default=None, max_length=64)
    scope_data: dict[str, Any] = Field(default_factory=dict)
    justification: str = Field(min_length=1, max_length=2000)


class ProjectFactResponse(ApiModel):
    id: UUID
    project_id: UUID
    key: str
    value: Any
    unit: str | None
    scope_data: dict[str, Any]
    source: str
    verification_status: str
    confidence: float | None
    supersedes_id: UUID | None
    verified_by_id: UUID | None
    verified_at: datetime | None
    evidence_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CheckRunCreate(ApiModel):
    project_id: UUID
    rule_pack_ids: list[UUID] = Field(min_length=1)
    name: str = Field(default="Compliance review", min_length=1, max_length=255)


class CheckResultResponse(ApiModel):
    id: UUID
    rule_id: UUID
    status: str
    severity: str
    message: str
    fact_ids: list[str]
    regulation_evidence_ids: list[str]
    project_evidence_ids: list[str]
    trace: dict[str, Any]
    workflow_status: str
    assignee_id: UUID | None
    reviewer_notes: str | None


class CheckRunResponse(ApiModel):
    id: UUID
    review_package_id: UUID
    status: str
    project_snapshot: dict[str, Any]
    rule_pack_snapshot: list[dict[str, Any]]
    engine_version: str
    input_hash: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    results: list[CheckResultResponse] = Field(default_factory=list)


class CheckRunCreated(ApiModel):
    run: CheckRunResponse
    job: JobResponse
