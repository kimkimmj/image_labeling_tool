"""export_jobs.export_format (yolo | coco)

Revision ID: 012_export_job_format
Revises: 011_dataset_version_split_export
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "012_export_job_format"
down_revision = "011_dataset_version_split_export"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "export_jobs" not in inspector.get_table_names():
        return

    cols = {c["name"] for c in inspector.get_columns("export_jobs")}
    if "export_format" not in cols:
        op.add_column(
            "export_jobs",
            sa.Column(
                "export_format",
                sa.Text(),
                nullable=False,
                server_default="yolo",
            ),
        )
        op.create_check_constraint(
            "chk_export_format",
            "export_jobs",
            "export_format IN ('yolo', 'coco')",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "export_jobs" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("export_jobs")}
    if "export_format" in cols:
        op.drop_constraint("chk_export_format", "export_jobs", type_="check")
        op.drop_column("export_jobs", "export_format")
