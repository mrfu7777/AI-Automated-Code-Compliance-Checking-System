from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.enums import (
    CheckStatus,
    EvidenceKind,
    LifecycleStatus,
    Severity,
)
from app.domain.schemas import EvidenceRef, RuleDefinition


def test_file_evidence_requires_a_file_version() -> None:
    with pytest.raises(ValidationError, match="requires a file version"):
        EvidenceRef(
            id=uuid4(),
            kind=EvidenceKind.DOCUMENT_REGION,
            created_at=datetime.now(UTC),
        )


def test_manual_evidence_does_not_require_a_file_version() -> None:
    evidence = EvidenceRef(
        id=uuid4(),
        kind=EvidenceKind.MANUAL_ASSERTION,
        excerpt="Confirmed by the project architect.",
        created_at=datetime.now(UTC),
    )

    assert evidence.file_version_id is None


def test_missing_data_cannot_be_configured_as_compliant() -> None:
    with pytest.raises(ValidationError, match="cannot produce a compliance decision"):
        RuleDefinition(
            id=uuid4(),
            rule_pack_id=uuid4(),
            code="egress.exit-count",
            title="Minimum exit count",
            source_clause_id=uuid4(),
            lifecycle_status=LifecycleStatus.DRAFT,
            severity=Severity.HIGH,
            expression={"operator": "greater_than_or_equal"},
            missing_data_status=CheckStatus.COMPLIANT,
        )
