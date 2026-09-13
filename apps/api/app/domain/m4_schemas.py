from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.domain.m1_schemas import ApiModel, JobResponse


class ProjectExtractionCreate(ApiModel):
    file_version_id: UUID


class ProjectExtractionResponse(ApiModel):
    document_kind: str
    job: JobResponse


class FactTypeResponse(ApiModel):
    key: str
    label: str
    unit: str | None


class FactEvidenceResponse(ApiModel):
    id: UUID
    file_version_id: UUID | None
    kind: str
    location: dict[str, Any]
    excerpt: str | None


class FactCandidateResponse(ApiModel):
    id: UUID
    project_id: UUID
    key: str
    value: Any
    unit: str | None
    scope_data: dict[str, Any]
    source: str
    verification_status: str
    confidence: float | None
    extractor_version: str | None
    supersedes_id: UUID | None
    verified_by_id: UUID | None
    verified_at: datetime | None
    evidence: list[FactEvidenceResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FactDecision(ApiModel):
    reason: str = Field(min_length=1, max_length=2000)
