"""add auto_label_status columns to upload_jobs

Revision ID: 007_auto_label_status
Revises: 006_step4_upload
Create Date:

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "007_auto_label_status"
down_revision = "006_step4_upload"
branch_labels = None
depends_on = None

_ENUM_NAME = "auto_label_status"
_ENUM_VALUES = ("skipped", "pending", "running", "completed", "failed")


def upgrade() -> None:
    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
        {"name": _ENUM_NAME},
    ).fetchone()
    if not existing:
        auto_label_status = postgresql.ENUM(*_ENUM_VALUES, name=_ENUM_NAME)
        auto_label_status.create(conn)

    op.add_column(
        "upload_jobs",
        sa.Column(
            "auto_label_status",
            postgresql.ENUM(*_ENUM_VALUES, name=_ENUM_NAME, create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "upload_jobs",
        sa.Column("auto_label_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "upload_jobs",
        sa.Column(
            "auto_label_completed_at",
            sa.DateTime(timezone=False),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("upload_jobs", "auto_label_completed_at")
    op.drop_column("upload_jobs", "auto_label_error")
    op.drop_column("upload_jobs", "auto_label_status")

    conn = op.get_bind()
    conn.execute(sa.text(f"DROP TYPE IF EXISTS {_ENUM_NAME}"))
