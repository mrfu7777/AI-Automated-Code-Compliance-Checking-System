"""Add M3 rule review and reproducibility fields.

Revision ID: d2a6f4b981ce
Revises: 8c17d6e294ab
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d2a6f4b981ce"
down_revision: str | None = "8c17d6e294ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rule_packs", sa.Column("published_by_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_rule_packs_published_by_id_users"),
        "rule_packs",
        "users",
        ["published_by_id"],
        ["id"],
    )
    op.add_column("rules", sa.Column("reviewed_by_id", sa.Uuid(), nullable=True))
    op.add_column("rules", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_rules_reviewed_by_id_users"), "rules", "users", ["reviewed_by_id"], ["id"]
    )
    op.add_column("project_facts", sa.Column("verified_by_id", sa.Uuid(), nullable=True))
    op.add_column(
        "project_facts", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_project_facts_verified_by_id_users"),
        "project_facts",
        "users",
        ["verified_by_id"],
        ["id"],
    )
    op.add_column(
        "check_runs",
        sa.Column(
            "engine_version", sa.String(length=64), server_default="m3.engine.v1", nullable=False
        ),
    )
    op.add_column(
        "check_runs",
        sa.Column(
            "input_hash",
            sa.String(length=64),
            server_default="0000000000000000000000000000000000000000000000000000000000000000",
            nullable=False,
        ),
    )
    op.alter_column("check_runs", "engine_version", server_default=None)
    op.alter_column("check_runs", "input_hash", server_default=None)


def downgrade() -> None:
    op.drop_column("check_runs", "input_hash")
    op.drop_column("check_runs", "engine_version")
    op.drop_constraint(
        op.f("fk_project_facts_verified_by_id_users"), "project_facts", type_="foreignkey"
    )
    op.drop_column("project_facts", "verified_at")
    op.drop_column("project_facts", "verified_by_id")
    op.drop_constraint(op.f("fk_rules_reviewed_by_id_users"), "rules", type_="foreignkey")
    op.drop_column("rules", "reviewed_at")
    op.drop_column("rules", "reviewed_by_id")
    op.drop_constraint(
        op.f("fk_rule_packs_published_by_id_users"), "rule_packs", type_="foreignkey"
    )
    op.drop_column("rule_packs", "published_by_id")
