"""assignment pool: add unassigned status, make assigned_to nullable, migrate existing rows

Revision ID: 009_assignment_pool
Revises: 008_rename_submitted_to_done
Create Date: 2026-05-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "009_assignment_pool"
down_revision = "008_rename_submitted_to_done"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) enum 에 unassigned 추가
    op.execute("ALTER TYPE assignment_status ADD VALUE IF NOT EXISTS 'unassigned'")

    # enum 변경이 트랜잭션 밖에 반영되도록 커밋 (PostgreSQL 특성)
    op.execute("COMMIT")
    op.execute("BEGIN")

    # 2) assigned_to nullable 로 변경 (FK 는 이미 nullable=True 허용)
    op.alter_column(
        "image_assignments",
        "assigned_to",
        existing_type=sa.BigInteger(),
        nullable=True,
    )

    # 3) 기존 데이터 전부 풀로 정리
    #    approved / reverted 제외한 모든 행 → unassigned 풀
    #    (approved 는 그대로 유지, reverted 는 이미 완결된 상태이므로 유지)
    op.execute(
        """
        UPDATE image_assignments
        SET status = 'unassigned',
            assigned_to = NULL,
            reviewer_id = NULL
        WHERE status NOT IN ('approved', 'reverted')
        """
    )


def downgrade() -> None:
    # assigned_to NOT NULL 로 복구 (데이터 손실 가능 — NULL 행 제거 후)
    op.execute(
        """
        DELETE FROM image_assignments WHERE assigned_to IS NULL
        """
    )
    op.alter_column(
        "image_assignments",
        "assigned_to",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    # enum 값 제거는 PostgreSQL 에서 직접 지원 안 함 — 수동 필요
