"""project_invitations and invitation enums

Revision ID: 002_project_invitations
Revises: 001_step1
Create Date:

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "002_project_invitations"
down_revision = "001_step1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE project_invitation_role AS ENUM ('annotator', 'reviewer');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE invitation_status AS ENUM (
                'pending', 'accepted', 'expired', 'cancelled'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    invitation_role_enum = postgresql.ENUM(
        "annotator",
        "reviewer",
        name="project_invitation_role",
        create_type=False,
    )
    invitation_status_enum = postgresql.ENUM(
        "pending",
        "accepted",
        "expired",
        "cancelled",
        name="invitation_status",
        create_type=False,
    )

    tables = inspector.get_table_names()
    if "project_invitations" not in tables:
        op.create_table(
            "project_invitations",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.BigInteger(), nullable=False),
            sa.Column("role", invitation_role_enum, nullable=False),
            sa.Column("token_hash", sa.Text(), nullable=False),
            sa.Column("status", invitation_status_enum, nullable=False),
            sa.Column("invited_by", sa.BigInteger(), nullable=False),
            sa.Column("accepted_by", sa.BigInteger(), nullable=True),
            sa.Column("accepted_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=False),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "expires_at > created_at",
                name="ck_project_invitations_expires_after_created",
            ),
            sa.ForeignKeyConstraint(
                ["project_id"],
                ["projects.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["invited_by"],
                ["users.id"],
            ),
            sa.ForeignKeyConstraint(
                ["accepted_by"],
                ["users.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_project_invitations_token_hash"),
        )
        op.create_index(
            "idx_project_invitations_project_status",
            "project_invitations",
            ["project_id", "status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if "project_invitations" in tables:
        op.drop_index(
            "idx_project_invitations_project_status",
            table_name="project_invitations",
        )
        op.drop_table("project_invitations")

    op.execute("DROP TYPE IF EXISTS invitation_status")
    op.execute("DROP TYPE IF EXISTS project_invitation_role")
