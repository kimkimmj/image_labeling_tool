"""rename assignment_status submitted -> done

Revision ID: 008
Revises: 007
Create Date: 2026-05-10
"""
from __future__ import annotations

from alembic import op

revision = "008_rename_submitted_to_done"
down_revision = "007_auto_label_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE assignment_status RENAME VALUE 'submitted' TO 'done'")


def downgrade() -> None:
    op.execute("ALTER TYPE assignment_status RENAME VALUE 'done' TO 'submitted'")
