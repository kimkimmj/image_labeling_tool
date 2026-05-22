"""STEP 9-11: dataset_items, splits, export_jobs; version -> name; split_items by dataset_item_id

Revision ID: 011_dataset_version_split_export
Revises: 010_assignment_status_submitted
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "011_dataset_version_split_export"
down_revision = "010_assignment_status_submitted"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if "dataset_versions" in tables:
        cols = {c["name"] for c in inspector.get_columns("dataset_versions")}
        if "version" in cols and "name" not in cols:
            op.alter_column("dataset_versions", "version", new_column_name="name")
            op.drop_constraint("uq_dataset_version", "dataset_versions", type_="unique")
            op.create_unique_constraint(
                "uq_dataset_version",
                "dataset_versions",
                ["project_id", "name"],
            )
    else:
        op.create_table(
            "dataset_versions",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.BigInteger(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "name", name="uq_dataset_version"),
        )

    if "dataset_items" not in tables:
        op.create_table(
            "dataset_items",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("dataset_version_id", sa.BigInteger(), nullable=False),
            sa.Column("image_id", sa.BigInteger(), nullable=False),
            sa.Column("assignment_id", sa.BigInteger(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["dataset_version_id"],
                ["dataset_versions.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["image_id"], ["images.id"]),
            sa.ForeignKeyConstraint(["assignment_id"], ["image_assignments.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "dataset_version_id",
                "image_id",
                name="uq_dataset_item_version_image",
            ),
        )
        op.create_index(
            "idx_dataset_items_version",
            "dataset_items",
            ["dataset_version_id"],
        )

    if "dataset_splits" not in tables:
        op.create_table(
            "dataset_splits",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("dataset_version_id", sa.BigInteger(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("train_ratio", sa.Float(), nullable=False),
            sa.Column("val_ratio", sa.Float(), nullable=False),
            sa.Column("test_ratio", sa.Float(), nullable=False),
            sa.Column("random_seed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.BigInteger(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "train_ratio + val_ratio + test_ratio = 100",
                name="chk_split_ratio",
            ),
            sa.ForeignKeyConstraint(
                ["dataset_version_id"],
                ["dataset_versions.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "split_items" not in tables:
        op.create_table(
            "split_items",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("split_id", sa.BigInteger(), nullable=False),
            sa.Column("dataset_item_id", sa.BigInteger(), nullable=False),
            sa.Column("split_type", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "split_type IN ('train', 'val', 'test')",
                name="chk_split_type",
            ),
            sa.ForeignKeyConstraint(
                ["split_id"],
                ["dataset_splits.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["dataset_item_id"], ["dataset_items.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "split_id",
                "dataset_item_id",
                name="uq_split_item_per_dataset_item",
            ),
        )
        op.create_index("idx_split_items_split", "split_items", ["split_id"])

    if "export_jobs" not in tables:
        export_status = sa.Enum(
            "pending",
            "processing",
            "completed",
            "failed",
            name="export_status",
            create_type=False,
        )
        op.create_table(
            "export_jobs",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.BigInteger(), nullable=False),
            sa.Column("dataset_version_id", sa.BigInteger(), nullable=False),
            sa.Column("split_id", sa.BigInteger(), nullable=False),
            sa.Column("requested_by", sa.BigInteger(), nullable=False),
            sa.Column("status", export_status, nullable=False),
            sa.Column("export_path", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"]),
            sa.ForeignKeyConstraint(["split_id"], ["dataset_splits.id"]),
            sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_export_jobs_project", "export_jobs", ["project_id"])
        op.create_index("idx_export_jobs_status", "export_jobs", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    for tbl in ("export_jobs", "split_items", "dataset_splits", "dataset_items"):
        if tbl in tables:
            op.drop_table(tbl)

    if "dataset_versions" in tables:
        cols = {c["name"] for c in inspector.get_columns("dataset_versions")}
        if "name" in cols:
            op.drop_constraint("uq_dataset_version", "dataset_versions", type_="unique")
            op.alter_column("dataset_versions", "name", new_column_name="version")
            op.create_unique_constraint(
                "uq_dataset_version",
                "dataset_versions",
                ["project_id", "version"],
            )
