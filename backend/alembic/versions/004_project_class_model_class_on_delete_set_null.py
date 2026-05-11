"""project_classes.model_class_id FK ON DELETE SET NULL

Revision ID: 004_step3_fk_fix
Revises: 003_step3
Create Date:

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "004_step3_fk_fix"
down_revision = "003_step3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "project_classes" not in inspector.get_table_names():
        return

    fks = inspector.get_foreign_keys("project_classes")
    for fk in fks:
        if fk.get("constrained_columns") == ["model_class_id"]:
            name = fk.get("name") or "project_classes_model_class_id_fkey"
            op.drop_constraint(name, "project_classes", type_="foreignkey")
            break

    op.create_foreign_key(
        "project_classes_model_class_id_fkey",
        "project_classes",
        "model_classes",
        ["model_class_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "project_classes" not in inspector.get_table_names():
        return

    fks = inspector.get_foreign_keys("project_classes")
    for fk in fks:
        if fk.get("constrained_columns") == ["model_class_id"]:
            name = fk.get("name") or "project_classes_model_class_id_fkey"
            op.drop_constraint(name, "project_classes", type_="foreignkey")
            break

    op.create_foreign_key(
        "project_classes_model_class_id_fkey",
        "project_classes",
        "model_classes",
        ["model_class_id"],
        ["id"],
    )
