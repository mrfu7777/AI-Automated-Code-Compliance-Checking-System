from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Evidence, ProjectFact


@dataclass(frozen=True)
class CandidateWrite:
    key: str
    value: Any
    unit: str | None
    scope_data: dict[str, Any]
    location: dict[str, Any]
    excerpt: str
    confidence: float


async def persist_fact_candidates(
    session: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    file_version_id: UUID,
    candidates: Iterable[CandidateWrite],
    source: str,
    evidence_kind: str,
    extractor_version: str,
) -> tuple[list[str], int]:
    """Persist candidates through the single M4 conflict and evidence path."""
    created_ids: list[str] = []
    conflicts = 0
    for candidate in candidates:
        scope = json.dumps(candidate.scope_data, sort_keys=True, separators=(",", ":"))
        existing = list(
            await session.scalars(
                select(ProjectFact).where(
                    ProjectFact.project_id == project_id,
                    ProjectFact.key == candidate.key,
                    ProjectFact.verification_status.in_(["candidate", "conflicting", "verified"]),
                )
            )
        )
        different = [
            fact
            for fact in existing
            if json.dumps(fact.scope_data, sort_keys=True, separators=(",", ":")) == scope
            and (fact.value != candidate.value or fact.unit != candidate.unit)
        ]
        candidate_status = "conflicting" if different else "candidate"
        if different:
            conflicts += 1
            for fact in different:
                if fact.verification_status == "candidate":
                    fact.verification_status = "conflicting"
        fact = ProjectFact(
            project_id=project_id,
            key=candidate.key,
            value=candidate.value,
            unit=candidate.unit,
            scope_data=candidate.scope_data,
            source=source,
            verification_status=candidate_status,
            confidence=candidate.confidence,
            extractor_version=extractor_version,
        )
        session.add(fact)
        await session.flush()
        session.add(
            Evidence(
                organization_id=organization_id,
                project_fact_id=fact.id,
                file_version_id=file_version_id,
                kind=evidence_kind,
                location={**candidate.location, "extractor_version": extractor_version},
                excerpt=candidate.excerpt,
            )
        )
        created_ids.append(str(fact.id))
    return created_ids, conflicts
