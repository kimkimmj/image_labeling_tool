"""step1: oauth_identities, nullable password_hash

Revision ID: 001_step1
Revises:
Create Date:

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "001_step1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if "oauth_identities" not in tables:
        # init 스크립트로 타입만 있을 수도, 아예 없을 수도 있음.
        op.execute(
            """
            DO $$ BEGIN
                CREATE TYPE oauth_provider AS ENUM ('google', 'naver', 'kakao');
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
        oauth_provider_enum = postgresql.ENUM(
            "google",
            "naver",
            "kakao",
            name="oauth_provider",
            create_type=False,
        )

        op.create_table(
            "oauth_identities",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("provider", oauth_provider_enum, nullable=False),
            sa.Column("provider_subject", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "provider_subject", name="uq_oauth_provider_subject"),
        )
        op.create_index("idx_oauth_identities_user_id", "oauth_identities", ["user_id"])

    if "users" in tables:
        cols = {c["name"] for c in inspector.get_columns("users")}
        if "password" in cols and "password_hash" not in cols:
            op.alter_column(
                "users",
                "password",
                existing_type=sa.Text(),
                nullable=True,
            )
            op.execute("ALTER TABLE users RENAME COLUMN password TO password_hash")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if "users" in tables:
        cols = {c["name"] for c in inspector.get_columns("users")}
        if "password_hash" in cols and "password" not in cols:
            op.execute("ALTER TABLE users RENAME COLUMN password_hash TO password")
            op.alter_column(
                "users",
                "password",
                existing_type=sa.Text(),
                nullable=False,
            )

    if "oauth_identities" in tables:
        op.drop_index("idx_oauth_identities_user_id", table_name="oauth_identities")
        op.drop_table("oauth_identities")

    op.execute("DROP TYPE IF EXISTS oauth_provider")
