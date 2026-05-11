"""step3: ml_models, model_classes, project_classes

Revision ID: 003_step3
Revises: 002_project_invitations
Create Date:

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "003_step3"
down_revision = "002_project_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if "ml_models" not in tables:
        op.create_table(
            "ml_models",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("owner_id", sa.BigInteger(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("version", sa.Text(), nullable=True),
            sa.Column("framework", sa.Text(), nullable=False),
            sa.Column("file_path", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "model_classes" not in tables:
        op.create_table(
            "model_classes",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("model_id", sa.BigInteger(), nullable=False),
            sa.Column("class_index", sa.Integer(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["model_id"], ["ml_models.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("model_id", "class_index", name="uq_model_class_index"),
        )

    if "project_classes" not in tables:
        op.create_table(
            "project_classes",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.BigInteger(), nullable=False),
            sa.Column("model_class_id", sa.BigInteger(), nullable=True),
            sa.Column("export_index", sa.Integer(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("color", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("created_by", sa.BigInteger(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["model_class_id"], ["model_classes.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "export_index", name="uq_project_export_index"),
            sa.UniqueConstraint("project_id", "name", name="uq_project_class_name"),
        )

    # projects.selected_model_id FK 추가 (컬럼은 이미 db_table.sql 초기화로 존재할 수 있음)
    if "projects" in tables:
        fks = {fk["name"] for fk in inspector.get_foreign_keys("projects")}
        if "projects_selected_model_id_fkey" not in fks:
            # 기존에 ml_models가 없어서 FK 없이 생성된 경우에만 추가
            try:
                op.create_foreign_key(
                    "projects_selected_model_id_fkey",
                    "projects",
                    "ml_models",
                    ["selected_model_id"],
                    ["id"],
                )
            except Exception:
                pass


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if "projects" in tables:
        fks = {fk["name"] for fk in inspector.get_foreign_keys("projects")}
        if "projects_selected_model_id_fkey" in fks:
            op.drop_constraint("projects_selected_model_id_fkey", "projects", type_="foreignkey")

    if "project_classes" in tables:
        op.drop_table("project_classes")

    if "model_classes" in tables:
        op.drop_table("model_classes")

    if "ml_models" in tables:
        op.drop_table("ml_models")
