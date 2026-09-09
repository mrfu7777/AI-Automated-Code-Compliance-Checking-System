"""Add M1 file and request trace fields to jobs.

Revision ID: f4d8c2a71e30
Revises: bde94e64f993
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f4d8c2a71e30"
down_revision: str | None = "bde94e64f993"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_project_files_project_name", "project_files", ["project_id", "logical_name"]
    )
    op.add_column("jobs", sa.Column("file_version_id", sa.Uuid(), nullable=True))
    op.add_column(
        "jobs", sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False)
    )
    op.add_column("jobs", sa.Column("request_id", sa.String(length=128), nullable=True))
    op.create_foreign_key(
        op.f("fk_jobs_file_version_id_file_versions"),
        "jobs",
        "file_versions",
        ["file_version_id"],
        ["id"],
    )
    op.create_index(op.f("ix_jobs_file_version_id"), "jobs", ["file_version_id"])
    op.create_index(op.f("ix_jobs_request_id"), "jobs", ["request_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_request_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_file_version_id"), table_name="jobs")
    op.drop_constraint(
        op.f("fk_jobs_file_version_id_file_versions"), "jobs", type_="foreignkey"
    )
    op.drop_column("jobs", "request_id")
    op.drop_column("jobs", "max_attempts")
    op.drop_column("jobs", "file_version_id")
    op.drop_constraint("uq_project_files_project_name", "project_files", type_="unique")
