"""Add M2 regulation digitization and correction records.

Revision ID: 8c17d6e294ab
Revises: f4d8c2a71e30
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8c17d6e294ab"
down_revision: str | None = "f4d8c2a71e30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("standards", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.execute(
        "INSERT INTO organizations (id, name, slug) "
        "SELECT '00000000-0000-0000-0000-000000000001', "
        "'Migrated Organization', 'migrated-organization' "
        "WHERE EXISTS (SELECT 1 FROM standards) "
        "AND NOT EXISTS (SELECT 1 FROM organizations)"
    )
    op.execute(
        "UPDATE standards SET organization_id = "
        "(SELECT id FROM organizations ORDER BY created_at LIMIT 1)"
    )
    op.alter_column("standards", "organization_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_standards_organization_id_organizations"),
        "standards",
        "organizations",
        ["organization_id"],
        ["id"],
    )
    op.create_index(op.f("ix_standards_organization_id"), "standards", ["organization_id"])
    op.drop_constraint(op.f("uq_standards_code"), "standards", type_="unique")
    op.create_unique_constraint(
        "uq_standards_organization_code", "standards", ["organization_id", "code"]
    )

    op.create_table(
        "document_pages",
        sa.Column("file_version_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("extraction_method", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("average_confidence", sa.Float(), nullable=True),
        sa.Column("image_object_key", sa.String(length=1024), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["file_version_id"], ["file_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_version_id", "page_number", name="uq_document_pages_file_page"),
    )
    op.create_index(
        op.f("ix_document_pages_file_version_id"), "document_pages", ["file_version_id"]
    )

    op.add_column("clauses", sa.Column("source_page_id", sa.Uuid(), nullable=True))
    op.add_column(
        "clauses",
        sa.Column("level", sa.String(length=32), server_default="article", nullable=False),
    )
    op.add_column("clauses", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("clauses", sa.Column("reviewed_by_id", sa.Uuid(), nullable=True))
    op.add_column("clauses", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(None, "clauses", "document_pages", ["source_page_id"], ["id"])
    op.create_foreign_key(None, "clauses", "users", ["reviewed_by_id"], ["id"])
    op.create_index(op.f("ix_clauses_source_page_id"), "clauses", ["source_page_id"])

    op.create_table(
        "clause_revisions",
        sa.Column("clause_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("clause_number", sa.String(length=128), nullable=False),
        sa.Column("heading", sa.String(length=512), nullable=True),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("bounding_box", sa.JSON(), nullable=True),
        sa.Column("changed_by_id", sa.Uuid(), nullable=False),
        sa.Column("change_reason", sa.String(length=512), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["clause_id"], ["clauses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clause_id", "revision_number", name="uq_clause_revisions_number"),
    )
    op.create_index(op.f("ix_clause_revisions_clause_id"), "clause_revisions", ["clause_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_clause_revisions_clause_id"), table_name="clause_revisions")
    op.drop_table("clause_revisions")
    op.drop_index(op.f("ix_clauses_source_page_id"), table_name="clauses")
    op.drop_constraint(op.f("fk_clauses_reviewed_by_id_users"), "clauses", type_="foreignkey")
    op.drop_constraint(
        op.f("fk_clauses_source_page_id_document_pages"), "clauses", type_="foreignkey"
    )
    for column in ("reviewed_at", "reviewed_by_id", "confidence", "level", "source_page_id"):
        op.drop_column("clauses", column)
    op.drop_index(op.f("ix_document_pages_file_version_id"), table_name="document_pages")
    op.drop_table("document_pages")
    op.drop_constraint("uq_standards_organization_code", "standards", type_="unique")
    op.create_unique_constraint(op.f("uq_standards_code"), "standards", ["code"])
    op.drop_index(op.f("ix_standards_organization_id"), table_name="standards")
    op.drop_constraint(
        op.f("fk_standards_organization_id_organizations"), "standards", type_="foreignkey"
    )
    op.drop_column("standards", "organization_id")
