from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(128))
    jurisdiction: Mapped[str | None] = mapped_column(String(255))
    design_date: Mapped[date | None] = mapped_column(Date)
    building_type: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_projects_organization_code"),
    )


class ProjectFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_files"

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    logical_name: Mapped[str] = mapped_column(String(512), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False, default="project_document")

    __table_args__ = (
        UniqueConstraint("project_id", "logical_name", name="uq_project_files_project_name"),
    )


class FileVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "file_versions"

    project_file_id: Mapped[UUID | None] = mapped_column(ForeignKey("project_files.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    uploaded_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    __table_args__ = (
        UniqueConstraint(
            "project_file_id",
            "version_number",
            name="uq_file_versions_file_version_number",
        ),
    )


class Standard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "standards"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_standards_organization_code"),
    )


class StandardVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "standard_versions"

    standard_id: Mapped[UUID] = mapped_column(
        ForeignKey("standards.id"), nullable=False, index=True
    )
    edition: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    lifecycle_status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")
    source_file_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("file_versions.id"), nullable=False
    )
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(ForeignKey("standard_versions.id"))
    parser_version: Mapped[str | None] = mapped_column(String(128))

    __table_args__ = (
        UniqueConstraint("standard_id", "edition", name="uq_standard_versions_edition"),
    )


class Clause(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clauses"

    standard_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("standard_versions.id"), nullable=False, index=True
    )
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("clauses.id"))
    source_page_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_pages.id"), index=True)
    clause_number: Mapped[str] = mapped_column(String(128), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False, default="article")
    heading: Mapped[str | None] = mapped_column(String(512))
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    bounding_box: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    reviewed_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")

    __table_args__ = (
        UniqueConstraint(
            "standard_version_id",
            "clause_number",
            name="uq_clauses_standard_version_number",
        ),
    )


class DocumentPage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_pages"

    file_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("file_versions.id"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    average_confidence: Mapped[float | None] = mapped_column(Float)
    image_object_key: Mapped[str | None] = mapped_column(String(1024))

    __table_args__ = (
        UniqueConstraint("file_version_id", "page_number", name="uq_document_pages_file_page"),
    )


class ClauseRevision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clause_revisions"

    clause_id: Mapped[UUID] = mapped_column(ForeignKey("clauses.id"), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    clause_number: Mapped[str] = mapped_column(String(128), nullable=False)
    heading: Mapped[str | None] = mapped_column(String(512))
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    bounding_box: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    changed_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    change_reason: Mapped[str] = mapped_column(String(512), nullable=False)

    __table_args__ = (
        UniqueConstraint("clause_id", "revision_number", name="uq_clause_revisions_number"),
    )


class RulePack(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rule_packs"

    standard_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("standard_versions.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    semantic_version: Mapped[str] = mapped_column(String(32), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "standard_version_id",
            "semantic_version",
            name="uq_rule_packs_standard_version_semver",
        ),
    )


class Rule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rules"

    rule_pack_id: Mapped[UUID] = mapped_column(
        ForeignKey("rule_packs.id"), nullable=False, index=True
    )
    source_clause_id: Mapped[UUID] = mapped_column(
        ForeignKey("clauses.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    severity: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")
    applicability: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    inputs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    expression: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    missing_data_status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="insufficient_information"
    )

    __table_args__ = (UniqueConstraint("rule_pack_id", "code", name="uq_rules_rule_pack_code"),)


class ProjectFact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_facts"

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(64))
    scope_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    extractor_version: Mapped[str | None] = mapped_column(String(128))
    supersedes_id: Mapped[UUID | None] = mapped_column(ForeignKey("project_facts.id"))


class Evidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evidence"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    project_fact_id: Mapped[UUID | None] = mapped_column(ForeignKey("project_facts.id"), index=True)
    clause_id: Mapped[UUID | None] = mapped_column(ForeignKey("clauses.id"), index=True)
    file_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("file_versions.id"), index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    excerpt: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))


class ReviewPackage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_packages"

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")
    project_snapshot_hash: Mapped[str | None] = mapped_column(String(64))


class ReviewPackageRulePack(Base):
    __tablename__ = "review_package_rule_packs"

    review_package_id: Mapped[UUID] = mapped_column(
        ForeignKey("review_packages.id"), primary_key=True
    )
    rule_pack_id: Mapped[UUID] = mapped_column(ForeignKey("rule_packs.id"), primary_key=True)


class CheckRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "check_runs"

    review_package_id: Mapped[UUID] = mapped_column(
        ForeignKey("review_packages.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    project_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    rule_pack_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CheckResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "check_results"

    check_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("check_runs.id"), nullable=False, index=True
    )
    rule_id: Mapped[UUID] = mapped_column(ForeignKey("rules.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    fact_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    regulation_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    project_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    trace: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("check_run_id", "rule_id", name="uq_check_results_run_rule"),
    )


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"), index=True)
    file_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("file_versions.id"), index=True)
    job_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    input_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    request_id: Mapped[str | None] = mapped_column(String(128), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)
    request_id: Mapped[str | None] = mapped_column(String(128), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


Index("ix_project_facts_project_key", ProjectFact.project_id, ProjectFact.key)
Index("ix_clauses_standard_order", Clause.standard_version_id, Clause.order_index)
