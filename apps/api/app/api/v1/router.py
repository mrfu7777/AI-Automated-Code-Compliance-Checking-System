from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.jobs import router as jobs_router
from app.api.v1.projects import file_versions_router
from app.api.v1.projects import router as projects_router
from app.api.v1.regulations import router as regulations_router
from app.domain.enums import CheckStatus, EvidenceKind, JobStatus

router = APIRouter()
router.include_router(projects_router)
router.include_router(file_versions_router)
router.include_router(jobs_router)
router.include_router(regulations_router)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    api_version: Literal["v1"]


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


@router.get("/contracts", response_model=ContractSummary, tags=["system"])
async def contracts() -> ContractSummary:
    return ContractSummary(
        check_statuses=list(CheckStatus),
        evidence_kinds=list(EvidenceKind),
        job_statuses=list(JobStatus),
    )
