from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Actor, get_current_actor, get_request_id
from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.db.session import get_database_session
from app.domain.m8_schemas import DemoScenarioResponse
from app.services.audit import record_audit_event
from app.services.demo_scenario import create_demo_scenario
from app.services.storage import ObjectStorage, get_object_storage

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post(
    "/scenario",
    response_model=DemoScenarioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def seed_demo_scenario(
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> DemoScenarioResponse:
    settings = get_settings()
    if settings.app_env != "development" or not settings.demo_mode_enabled:
        raise ApplicationError("demo_disabled", "Demo mode is not enabled", status_code=404)
    scenario = await create_demo_scenario(
        session,
        storage,
        organization_id=actor.organization_id,
        actor_id=actor.user_id,
    )
    if scenario.created:
        record_audit_event(
            session,
            organization_id=actor.organization_id,
            actor_id=actor.user_id,
            action="demo_scenario.created",
            entity_type="project",
            entity_id=scenario.project.id,
            request_id=get_request_id(request),
            payload={"rule_pack_id": str(scenario.rule_pack.id), "synthetic": True},
        )
        await session.commit()
    return DemoScenarioResponse(
        created=scenario.created,
        project_id=scenario.project.id,
        rule_pack_id=scenario.rule_pack.id,
        project_name=scenario.project.name,
        rule_pack_name=scenario.rule_pack.name,
        expected_statuses={
            "DEMO-EXIT-COUNT": "non_compliant",
            "DEMO-EXIT-WIDTH": "compliant",
            "DEMO-BUILDING-HEIGHT": "compliant",
            "DEMO-COMPARTMENT-AREA": "insufficient_information",
        },
        next_steps=[
            "Select the generated project and rule pack.",
            "Run the existing compliance check and wait for its persisted job.",
            "Inspect each finding, both evidence columns, and the missing-information action.",
            "Download the preliminary PDF or Excel report.",
        ],
    )
