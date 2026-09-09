from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.domain.m1_schemas import ApiModel, JobResponse


class RegulationIngest(ApiModel):
    file_version_id: UUID
    code: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=512)
    edition: str = Field(min_length=1, max_length=128)
    jurisdiction: str = Field(min_length=1, max_length=255)
    effective_from: date | None = None
    effective_to: date | None = None


class StandardVersionResponse(ApiModel):
    id: UUID
    standard_id: UUID
    edition: str
    effective_from: date | None
    effective_to: date | None
    lifecycle_status: str
    source_file_version_id: UUID
    document_hash: str
    parser_version: str | None
    created_at: datetime
    updated_at: datetime


class StandardResponse(ApiModel):
    id: UUID
    code: str
    title: str
    jurisdiction: str
    versions: list[StandardVersionResponse] = Field(default_factory=list)


class RegulationIngestResponse(ApiModel):
    standard: StandardResponse
    version: StandardVersionResponse
    job: JobResponse


class PageResponse(ApiModel):
    id: UUID
    file_version_id: UUID
    page_number: int
    width: float
    height: float
    extraction_method: str
    text: str
    char_count: int
    average_confidence: float | None
    image_url: str | None = None


class ClauseResponse(ApiModel):
    id: UUID
    standard_version_id: UUID
    parent_id: UUID | None
    source_page_id: UUID | None
    clause_number: str
    level: str
    heading: str | None
    original_text: str
    page_number: int
    bounding_box: dict[str, Any] | None
    confidence: float | None
    lifecycle_status: str
    reviewed_by_id: UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ClauseUpdate(ApiModel):
    clause_number: str | None = Field(default=None, min_length=1, max_length=128)
    level: str | None = Field(default=None, max_length=32)
    heading: str | None = Field(default=None, max_length=512)
    original_text: str | None = Field(default=None, min_length=1)
    parent_id: UUID | None = None
    bounding_box: dict[str, Any] | None = None
    change_reason: str = Field(min_length=1, max_length=512)


class ClauseSplit(ApiModel):
    first_text: str = Field(min_length=1)
    second_number: str = Field(min_length=1, max_length=128)
    second_text: str = Field(min_length=1)
    change_reason: str = Field(min_length=1, max_length=512)


class ClauseMerge(ApiModel):
    clause_ids: list[UUID] = Field(min_length=2)
    target_number: str = Field(min_length=1, max_length=128)
    merged_text: str = Field(min_length=1)
    change_reason: str = Field(min_length=1, max_length=512)
