"""add is_admin to users

Revision ID: 005_is_admin
Revises: 004_step3_fk_fix
Create Date:

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "005_is_admin"
down_revision = "004_step3_fk_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "users" not in inspector.get_table_names():
        return

    existing_cols = {c["name"] for c in inspector.get_columns("users")}
    if "is_admin" not in existing_cols:
        op.add_column(
            "users",
            sa.Column(
                "is_admin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "users" not in inspector.get_table_names():
        return

    existing_cols = {c["name"] for c in inspector.get_columns("users")}
    if "is_admin" in existing_cols:
        op.drop_column("users", "is_admin")
