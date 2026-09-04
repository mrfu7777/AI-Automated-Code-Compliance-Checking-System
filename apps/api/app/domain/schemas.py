from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    CheckStatus,
    EvidenceKind,
    FactSource,
    LifecycleStatus,
    Severity,
    VerificationStatus,
)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class BoundingBox(DomainModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class EvidenceLocation(DomainModel):
    page_number: int | None = Field(default=None, ge=1)
    bounding_box: BoundingBox | None = None
    sheet_name: str | None = None
    cell_range: str | None = None
    ifc_global_id: str | None = None
    property_path: str | None = None


class EvidenceRef(DomainModel):
    id: UUID
    kind: EvidenceKind
    file_version_id: UUID | None = None
    location: EvidenceLocation = Field(default_factory=EvidenceLocation)
    excerpt: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_source(self) -> EvidenceRef:
        file_based = self.kind in {
            EvidenceKind.DOCUMENT_REGION,
            EvidenceKind.IMAGE_REGION,
            EvidenceKind.SPREADSHEET_RANGE,
            EvidenceKind.IFC_OBJECT,
        }
        if file_based and self.file_version_id is None:
            raise ValueError("File-based evidence requires a file version")
        return self


class ProjectFact(DomainModel):
    id: UUID
    project_id: UUID
    key: str = Field(min_length=1, max_length=255)
    value: Any
    unit: str | None = Field(default=None, max_length=64)
    scope: dict[str, Any] = Field(default_factory=dict)
    source: FactSource
    verification_status: VerificationStatus
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime


class ClauseRef(DomainModel):
    id: UUID
    standard_version_id: UUID
    clause_number: str = Field(min_length=1, max_length=128)
    original_text: str = Field(min_length=1)
    page_number: int = Field(ge=1)


class RuleInput(DomainModel):
    fact_key: str = Field(min_length=1, max_length=255)
    required: bool = True
    expected_unit: str | None = Field(default=None, max_length=64)


class RuleDefinition(DomainModel):
    id: UUID
    rule_pack_id: UUID
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    title: str = Field(min_length=1, max_length=255)
    source_clause_id: UUID
    lifecycle_status: LifecycleStatus
    severity: Severity
    applicability: dict[str, Any] = Field(default_factory=dict)
    inputs: list[RuleInput] = Field(default_factory=list)
    expression: dict[str, Any]
    missing_data_status: CheckStatus = CheckStatus.INSUFFICIENT_INFORMATION

    @model_validator(mode="after")
    def validate_missing_data_status(self) -> RuleDefinition:
        allowed = {
            CheckStatus.INSUFFICIENT_INFORMATION,
            CheckStatus.MANUAL_REVIEW_REQUIRED,
        }
        if self.missing_data_status not in allowed:
            raise ValueError("Missing data cannot produce a compliance decision")
        return self


class RulePackRef(DomainModel):
    id: UUID
    standard_version_id: UUID
    name: str = Field(min_length=1, max_length=255)
    semantic_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    lifecycle_status: LifecycleStatus
    content_hash: str = Field(min_length=64, max_length=64)


class CheckTrace(DomainModel):
    applicability: dict[str, Any] = Field(default_factory=dict)
    resolved_inputs: dict[str, Any] = Field(default_factory=dict)
    operations: list[dict[str, Any]] = Field(default_factory=list)


class CheckResult(DomainModel):
    id: UUID
    check_run_id: UUID
    rule_id: UUID
    status: CheckStatus
    severity: Severity
    message: str = Field(min_length=1)
    fact_ids: list[UUID] = Field(default_factory=list)
    regulation_evidence_ids: list[UUID] = Field(default_factory=list)
    project_evidence_ids: list[UUID] = Field(default_factory=list)
    trace: CheckTrace
    created_at: datetime
