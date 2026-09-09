from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent


def record_audit_event(
    session: AsyncSession,
    *,
    organization_id: UUID,
    actor_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID,
    request_id: str | None,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEvent(
            organization_id=organization_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=request_id,
            payload=payload or {},
            occurred_at=datetime.now(UTC),
        )
    )
