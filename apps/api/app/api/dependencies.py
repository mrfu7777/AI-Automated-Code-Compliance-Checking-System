import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.db.models import ApiKey, Organization, User
from app.db.session import get_database_session


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    organization_id: UUID
    role: str


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
    request: Request,
    x_user_id: Annotated[str | None, Header(alias="X-User-ID")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> Actor:
    settings = get_settings()
    effective_role: str | None = None
    if settings.auth_mode == "api_key":
        if not authorization or not authorization.startswith("Bearer "):
            raise ApplicationError(
                "authentication_required", "A bearer API key is required", status_code=401
            )
        token = authorization.removeprefix("Bearer ").strip()
        if settings.bootstrap_api_key and secrets.compare_digest(
            token, settings.bootstrap_api_key
        ):
            user = await _ensure_default_actor(session)
            effective_role = "admin"
        else:
            digest = hashlib.sha256(f"{settings.api_key_pepper}:{token}".encode()).hexdigest()
            credential = await session.scalar(select(ApiKey).where(ApiKey.key_hash == digest))
            now = datetime.now(UTC)
            expires_at = credential.expires_at if credential is not None else None
            if expires_at is not None and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if (
                credential is None
                or credential.revoked_at is not None
                or (expires_at is not None and expires_at <= now)
            ):
                raise ApplicationError(
                    "invalid_api_key", "The API key is invalid or expired", status_code=401
                )
            authenticated_user = await session.get(User, credential.user_id)
            if authenticated_user is None or not authenticated_user.is_active:
                raise ApplicationError("unknown_user", "User is not active", status_code=401)
            user = authenticated_user
            effective_role = user.role
            credential.last_used_at = now
            await session.commit()
    elif x_user_id is None:
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
    role = effective_role or user.role
    if role not in {"viewer", "architect", "admin"}:
        raise ApplicationError("unknown_role", "User role is not recognized", status_code=403)
    if request.method not in {"GET", "HEAD", "OPTIONS"} and role not in {
        "architect",
        "admin",
    }:
        raise ApplicationError("write_forbidden", "Viewer accounts are read-only", status_code=403)
    return Actor(user_id=user.id, organization_id=user.organization_id, role=role)


async def require_admin(
    actor: Annotated[Actor, Depends(get_current_actor)],
) -> Actor:
    if actor.role != "admin":
        raise ApplicationError(
            "admin_required", "Administrator access is required", status_code=403
        )
    return actor


def get_request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None
