"""Add M6 multi-code and incremental review fields.

Revision ID: a61e74c932bf
Revises: 9f4d1c2b7a60
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a61e74c932bf"
down_revision: str | None = "9f4d1c2b7a60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rule_packs",
        sa.Column(
            "authority_level",
            sa.String(length=32),
            server_default="national",
            nullable=False,
        ),
    )
    op.add_column(
        "review_packages",
        sa.Column("conflict_candidates", sa.JSON(), server_default="[]", nullable=False),
    )
    op.add_column(
        "review_packages",
        sa.Column("conflict_resolutions", sa.JSON(), server_default="{}", nullable=False),
    )
    op.add_column(
        "check_runs",
        sa.Column(
            "run_mode", sa.String(length=32), server_default="full", nullable=False
        ),
    )
    op.add_column("check_runs", sa.Column("baseline_run_id", sa.Uuid(), nullable=True))
    op.add_column(
        "check_runs", sa.Column("changed_fact_keys", sa.JSON(), server_default="[]", nullable=False)
    )
    op.add_column(
        "check_runs", sa.Column("affected_rule_ids", sa.JSON(), server_default="[]", nullable=False)
    )
    op.add_column(
        "check_runs",
        sa.Column("conflict_resolution_snapshot", sa.JSON(), server_default="{}", nullable=False),
    )
    op.create_index(op.f("ix_check_runs_baseline_run_id"), "check_runs", ["baseline_run_id"])
    op.create_foreign_key(
        op.f("fk_check_runs_baseline_run_id_check_runs"),
        "check_runs",
        "check_runs",
        ["baseline_run_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_check_runs_baseline_run_id_check_runs"), "check_runs", type_="foreignkey"
    )
    op.drop_index(op.f("ix_check_runs_baseline_run_id"), table_name="check_runs")
    op.drop_column("check_runs", "conflict_resolution_snapshot")
    op.drop_column("check_runs", "affected_rule_ids")
    op.drop_column("check_runs", "changed_fact_keys")
    op.drop_column("check_runs", "baseline_run_id")
    op.drop_column("check_runs", "run_mode")
    op.drop_column("review_packages", "conflict_resolutions")
    op.drop_column("review_packages", "conflict_candidates")
    op.drop_column("rule_packs", "authority_level")
