"""split_items: legacy image_id/assignment_id -> dataset_item_id

Docker initdb or older DDL may have created split_items without dataset_item_id.
Migration 011 skips table creation when split_items already exists.

Revision ID: 013_split_items_dataset_item_id
Revises: 012_export_job_format
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "013_split_items_dataset_item_id"
down_revision = "012_export_job_format"
branch_labels = None
depends_on = None


def _constraint_names(inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_unique_constraints(table)} | {
        c["name"] for c in inspector.get_check_constraints(table)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    if "split_items" not in tables:
        return

    cols = {c["name"] for c in inspector.get_columns("split_items")}
    if "dataset_item_id" in cols:
        return

    if "image_id" not in cols or "assignment_id" not in cols:
        raise RuntimeError(
            "split_items exists but has neither dataset_item_id nor legacy image_id/assignment_id; "
            "manual schema fix required"
        )

    op.add_column(
        "split_items",
        sa.Column("dataset_item_id", sa.BigInteger(), nullable=True),
    )

    op.execute(
        text(
            """
            UPDATE split_items AS si
            SET dataset_item_id = di.id
            FROM dataset_splits AS ds, dataset_items AS di
            WHERE si.split_id = ds.id
              AND di.dataset_version_id = ds.dataset_version_id
              AND di.image_id = si.image_id
              AND di.assignment_id = si.assignment_id
            """
        )
    )

    op.execute(text("DELETE FROM split_items WHERE dataset_item_id IS NULL"))

    op.alter_column("split_items", "dataset_item_id", nullable=False)

    for fk in inspector.get_foreign_keys("split_items"):
        cols = set(fk.get("constrained_columns") or [])
        if cols & {"image_id", "assignment_id"}:
            op.drop_constraint(fk["name"], "split_items", type_="foreignkey")

    op.create_foreign_key(
        "split_items_dataset_item_id_fkey",
        "split_items",
        "dataset_items",
        ["dataset_item_id"],
        ["id"],
    )

    op.drop_column("split_items", "image_id")
    op.drop_column("split_items", "assignment_id")

    names = _constraint_names(inspector, "split_items")
    if "chk_split_type" not in names:
        op.create_check_constraint(
            "chk_split_type",
            "split_items",
            "split_type IN ('train', 'val', 'test')",
        )
    if "uq_split_item_per_dataset_item" not in names:
        op.create_unique_constraint(
            "uq_split_item_per_dataset_item",
            "split_items",
            ["split_id", "dataset_item_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "split_items" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("split_items")}
    if "dataset_item_id" not in cols:
        return

    op.add_column("split_items", sa.Column("image_id", sa.BigInteger(), nullable=True))
    op.add_column("split_items", sa.Column("assignment_id", sa.BigInteger(), nullable=True))

    op.execute(
        text(
            """
            UPDATE split_items AS si
            SET image_id = di.image_id,
                assignment_id = di.assignment_id
            FROM dataset_items AS di
            WHERE di.id = si.dataset_item_id
            """
        )
    )

    op.alter_column("split_items", "image_id", nullable=False)
    op.alter_column("split_items", "assignment_id", nullable=False)

    for name in ("uq_split_item_per_dataset_item", "chk_split_type"):
        try:
            op.drop_constraint(name, "split_items", type_="unique")
        except Exception:
            try:
                op.drop_constraint(name, "split_items", type_="check")
            except Exception:
                pass

    op.drop_constraint("split_items_dataset_item_id_fkey", "split_items", type_="foreignkey")
    op.drop_column("split_items", "dataset_item_id")
