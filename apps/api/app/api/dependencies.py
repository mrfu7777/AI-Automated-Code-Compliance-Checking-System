from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.db.models import Organization, User
from app.db.session import get_database_session


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    organization_id: UUID


async def _ensure_default_actor(session: AsyncSession) -> User:
    settings = get_settings()
    organization_id = UUID(settings.default_organization_id)
    user_id = UUID(settings.default_user_id)
    user = await session.get(User, user_id)
    if user is not None:
        return user

    organization = await session.get(Organization, organization_id)
    if organization is None:
        session.add(
            Organization(
                id=organization_id,
                name="Local Development Organization",
                slug="local-development",
            )
        )
    user = User(
        id=user_id,
        organization_id=organization_id,
        email="architect@local.invalid",
        display_name="Local Architect",
        role="architect",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    return user


async def get_current_actor(
    session: Annotated[AsyncSession, Depends(get_database_session)],
    x_user_id: Annotated[str | None, Header(alias="X-User-ID")] = None,
) -> Actor:
    if x_user_id is None:
        user = await _ensure_default_actor(session)
    else:
        try:
            user_id = UUID(x_user_id)
        except ValueError as exception:
            raise ApplicationError(
                "invalid_user_id", "X-User-ID must be a UUID", status_code=401
            ) from exception
        found_user = await session.scalar(select(User).where(User.id == user_id))
        if found_user is None or not found_user.is_active:
            raise ApplicationError("unknown_user", "User is not active", status_code=401)
        user = found_user
    return Actor(user_id=user.id, organization_id=user.organization_id)


def get_request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None
