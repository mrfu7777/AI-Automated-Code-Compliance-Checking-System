from __future__ import annotations

from typing import Literal
from uuid import UUID

from app.domain.m1_schemas import ApiModel


class DemoScenarioResponse(ApiModel):
    created: bool
    project_id: UUID
    rule_pack_id: UUID
    project_name: str
    rule_pack_name: str
    expected_statuses: dict[str, str]
    next_steps: list[str]


class ReleaseManifestResponse(ApiModel):
    app_version: Literal["1.0.0"]
    source_revision: str
    image: str
    schema_revision: Literal["c73f20e184ad"]
    rule_engine_version: str
    regulation_parser_version: str
    project_extractor_version: str
    drawing_extractor_version: str
    demo_mode_enabled: bool
