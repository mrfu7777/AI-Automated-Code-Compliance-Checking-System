"""Add M5 finding workflow fields.

Revision ID: 9f4d1c2b7a60
Revises: d2a6f4b981ce
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9f4d1c2b7a60"
down_revision: str | None = "d2a6f4b981ce"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "check_results",
        sa.Column("workflow_status", sa.String(length=64), server_default="open", nullable=False),
    )
    op.add_column("check_results", sa.Column("assignee_id", sa.Uuid(), nullable=True))
    op.add_column("check_results", sa.Column("reviewer_notes", sa.Text(), nullable=True))
    op.create_index(op.f("ix_check_results_assignee_id"), "check_results", ["assignee_id"])
    op.create_foreign_key(
        op.f("fk_check_results_assignee_id_users"),
        "check_results",
        "users",
        ["assignee_id"],
        ["id"],
    )
    op.alter_column("check_results", "workflow_status", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_check_results_assignee_id_users"), "check_results", type_="foreignkey"
    )
    op.drop_index(op.f("ix_check_results_assignee_id"), table_name="check_results")
    op.drop_column("check_results", "reviewer_notes")
    op.drop_column("check_results", "assignee_id")
    op.drop_column("check_results", "workflow_status")
