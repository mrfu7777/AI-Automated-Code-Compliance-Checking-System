from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.checks import router as checks_router
from app.api.v1.demo import router as demo_router
from app.api.v1.drawings import router as drawings_router
from app.api.v1.extractions import router as extractions_router
from app.api.v1.facts import router as facts_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.operations import router as operations_router
from app.api.v1.projects import file_versions_router
from app.api.v1.projects import router as projects_router
from app.api.v1.regulations import router as regulations_router
from app.api.v1.rules import router as rules_router
from app.core.config import get_settings
from app.db.session import get_database_session
from app.domain.enums import CheckStatus, EvidenceKind, JobStatus
from app.domain.m8_schemas import ReleaseManifestResponse
from app.services.drawing_pipeline import DRAWING_EXTRACTOR_VERSION
from app.services.project_extraction import EXTRACTOR_VERSION
from app.services.rule_engine import ENGINE_VERSION
from app.tasks.regulation_processing import PARSER_VERSION

router = APIRouter()
router.include_router(projects_router)
router.include_router(file_versions_router)
router.include_router(jobs_router)
router.include_router(regulations_router)
router.include_router(rules_router)
router.include_router(facts_router)
router.include_router(checks_router)
router.include_router(extractions_router)
router.include_router(drawings_router)
router.include_router(operations_router)
router.include_router(demo_router)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    api_version: Literal["v1"]


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    database: Literal["reachable"]


class ContractSummary(BaseModel):
    check_statuses: list[CheckStatus]
    evidence_kinds: list[EvidenceKind]
    job_statuses: list[JobStatus]


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="code-compliance-api",
        api_version="v1",
    )


@router.get("/ready", response_model=ReadinessResponse, tags=["system"])
async def readiness(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ReadinessResponse:
    await session.execute(text("SELECT 1"))
    return ReadinessResponse(status="ready", database="reachable")


@router.get("/release", response_model=ReleaseManifestResponse, tags=["system"])
async def release_manifest() -> ReleaseManifestResponse:
    settings = get_settings()
    return ReleaseManifestResponse(
        app_version="1.0.0",
        source_revision=settings.release_revision,
        image=settings.release_image,
        schema_revision="c73f20e184ad",
        rule_engine_version=ENGINE_VERSION,
        regulation_parser_version=PARSER_VERSION,
        project_extractor_version=EXTRACTOR_VERSION,
        drawing_extractor_version=DRAWING_EXTRACTOR_VERSION,
        demo_mode_enabled=settings.demo_mode_enabled,
    )


@router.get("/contracts", response_model=ContractSummary, tags=["system"])
async def contracts() -> ContractSummary:
    return ContractSummary(
        check_statuses=list(CheckStatus),
        evidence_kinds=list(EvidenceKind),
        job_statuses=list(JobStatus),
    )
