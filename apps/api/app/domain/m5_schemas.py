from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.domain.m1_schemas import ApiModel, JobResponse
from app.domain.m4_schemas import FactCandidateResponse


class DrawingExtractionCreate(ApiModel):
    file_version_id: UUID


class DrawingExtractionResponse(ApiModel):
    job: JobResponse


class DrawingPageResponse(ApiModel):
    id: UUID
    file_version_id: UUID
    page_number: int
    width: float
    height: float
    extraction_method: str
    average_confidence: float | None
    image_url: str | None


class Point(ApiModel):
    x: float
    y: float


class DrawingAnnotationCreate(ApiModel):
    file_version_id: UUID
    page_number: int = Field(ge=1)
    annotation_kind: Literal["object", "dimension", "path", "scale"]
    fact_key: str = Field(min_length=1, max_length=255)
    value: Any | None = None
    unit: str | None = Field(default=None, max_length=64)
    label: str = Field(min_length=1, max_length=500)
    bbox: dict[str, float] | None = None
    points: list[Point] = Field(default_factory=list)
    pixels_per_meter: float | None = Field(default=None, gt=0)
    corrects_fact_id: UUID | None = None

    @model_validator(mode="after")
    def validate_geometry(self) -> DrawingAnnotationCreate:
        if self.annotation_kind == "path" and (len(self.points) < 2 or not self.pixels_per_meter):
            raise ValueError("Path annotations require at least two points and pixels_per_meter")
        if self.annotation_kind != "path" and self.value is None:
            raise ValueError("Non-path annotations require a value")
        return self


class DrawingAnnotationResponse(ApiModel):
    candidate: FactCandidateResponse


class FindingUpdate(ApiModel):
    workflow_status: Literal["open", "in_review", "resolved", "accepted_risk"] | None = None
    assignee_id: UUID | None = None
    reviewer_notes: str | None = Field(default=None, max_length=5000)


class WorkbenchEvidence(ApiModel):
    id: UUID
    kind: str
    file_version_id: UUID | None
    location: dict[str, Any]
    excerpt: str | None
    image_url: str | None = None


class WorkbenchFinding(ApiModel):
    result_id: UUID
    rule_id: UUID
    status: str
    severity: str
    message: str
    workflow_status: str
    assignee_id: UUID | None
    reviewer_notes: str | None
    trace: dict[str, Any]
    project_evidence: list[WorkbenchEvidence]
    regulation_evidence: list[WorkbenchEvidence]


class WorkbenchResponse(ApiModel):
    run_id: UUID
    findings: list[WorkbenchFinding]
