from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import JobStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ProjectCreate(ApiModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=128)
    jurisdiction: str | None = Field(default=None, max_length=255)
    design_date: date | None = None
    building_type: str | None = Field(default=None, max_length=128)


class ProjectResponse(ApiModel):
    id: UUID
    name: str
    code: str | None
    jurisdiction: str | None
    design_date: date | None
    building_type: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class FileVersionResponse(ApiModel):
    id: UUID
    project_file_id: UUID
    version_number: int
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class ProjectFileResponse(ApiModel):
    id: UUID
    project_id: UUID
    logical_name: str
    purpose: str
    created_at: datetime
    versions: list[FileVersionResponse] = Field(default_factory=list)


class JobResponse(ApiModel):
    id: UUID
    project_id: UUID | None
    file_version_id: UUID | None
    job_type: str
    status: JobStatus
    progress: float
    attempts: int
    max_attempts: int
    output_data: dict[str, Any] | None
    error_data: dict[str, Any] | None
    request_id: str | None
    created_at: datetime
    updated_at: datetime


class UploadResponse(ApiModel):
    project_file: ProjectFileResponse
    file_version: FileVersionResponse
    job: JobResponse


class DownloadResponse(ApiModel):
    url: str
    expires_in_seconds: int = 900
