"""assignment_status 에 submitted 추가 (검토 요청 후 리뷰 배정 대기)

Revision ID: 010_assignment_status_submitted
Revises: 009_assignment_pool
Create Date: 2026-05-10
"""

from __future__ import annotations

from alembic import op

revision = "010_assignment_status_submitted"
down_revision = "009_assignment_pool"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE assignment_status ADD VALUE IF NOT EXISTS 'submitted'")
    op.execute("COMMIT")
    op.execute("BEGIN")


def downgrade() -> None:
    raise NotImplementedError("PostgreSQL에서 ENUM 값 제거는 지원하지 않습니다.")
