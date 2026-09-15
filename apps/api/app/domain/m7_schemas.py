from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from app.domain.m1_schemas import ApiModel


class ApiKeyCreate(ApiModel):
    name: str = Field(min_length=1, max_length=255)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def require_explicit_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("expires_at must include a UTC offset")
        return value


class ApiKeyCreated(ApiModel):
    id: UUID
    name: str
    prefix: str
    token: str
    expires_at: datetime | None
    created_at: datetime


class ApiKeySummary(ApiModel):
    id: UUID
    name: str
    prefix: str
    expires_at: datetime | None
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


class PilotFeedbackCreate(ApiModel):
    category: str = Field(
        pattern="^(false_positive|false_negative|evidence|usability|value|other)$"
    )
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    summary: str = Field(min_length=1, max_length=512)
    details: str = Field(min_length=1, max_length=5000)
    time_saved_minutes: int | None = Field(default=None, ge=0, le=100000)


class PilotFeedbackResponse(PilotFeedbackCreate):
    id: UUID
    project_id: UUID
    submitted_by_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime


class PilotFeedbackUpdate(ApiModel):
    status: str = Field(pattern="^(open|triaged|resolved|accepted_limit)$")


class MissingInformationItem(ApiModel):
    fact_key: str
    affected_rules: list[str]
    severity: str
    action: str


class MissingInformationResponse(ApiModel):
    run_id: UUID
    items: list[MissingInformationItem]


class OperationsOverview(ApiModel):
    organization_id: UUID
    jobs_by_status: dict[str, int]
    jobs_by_type: dict[str, int]
    check_runs: int
    open_findings: int
    stored_file_bytes: int
    pilot_feedback_by_status: dict[str, int]
    external_model_enabled: bool
    external_model_calls: int
    estimated_model_cost: float
    deterministic_checks_available: bool


class AuditEventResponse(ApiModel):
    id: UUID
    actor_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    request_id: str | None
    payload: dict[str, Any]
    occurred_at: datetime
