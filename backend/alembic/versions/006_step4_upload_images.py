"""step4: upload_jobs, images, image_assignments, annotations

Revision ID: 006_step4_upload
Revises: 005_is_admin
Create Date:

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "006_step4_upload"
down_revision = "005_is_admin"
branch_labels = None
depends_on = None

_ENUMS = {
    "upload_type": ("image_zip", "video"),
    "upload_status": ("pending", "processing", "completed", "failed"),
    "assignment_status": (
        "assigned",
        "in_progress",
        "submitted",
        "review_assigned",
        "approved",
        "reverted",
        "rejected",
    ),
    "annotation_source": ("auto", "manual"),
    "export_status": ("pending", "processing", "completed", "failed"),
}


def _create_enum_if_missing(bind: object, name: str, values: tuple[str, ...]) -> None:
    enum = postgresql.ENUM(*values, name=name)
    enum.create(bind, checkfirst=True)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    for name, values in _ENUMS.items():
        _create_enum_if_missing(bind, name, values)

    if "upload_jobs" not in tables:
        op.create_table(
            "upload_jobs",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.BigInteger(), nullable=False),
            sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
            sa.Column(
                "upload_type",
                postgresql.ENUM("image_zip", "video", name="upload_type", create_type=False),
                nullable=False,
            ),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "pending", "processing", "completed", "failed",
                    name="upload_status",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("original_file_name", sa.Text(), nullable=False),
            sa.Column("original_file_path", sa.Text(), nullable=False),
            sa.Column("options", postgresql.JSONB(), nullable=True),
            sa.Column("progress", sa.Integer(), nullable=True),
            sa.Column("processed_count", sa.Integer(), nullable=True),
            sa.Column("total_count", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "source_videos" not in tables:
        op.create_table(
            "source_videos",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.BigInteger(), nullable=False),
            sa.Column("upload_job_id", sa.BigInteger(), nullable=False),
            sa.Column("original_name", sa.Text(), nullable=False),
            sa.Column("file_path", sa.Text(), nullable=False),
            sa.Column("duration_sec", sa.Float(), nullable=True),
            sa.Column("fps", sa.Float(), nullable=True),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["upload_job_id"], ["upload_jobs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if "images" not in tables:
        op.create_table(
            "images",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.BigInteger(), nullable=False),
            sa.Column("upload_job_id", sa.BigInteger(), nullable=False),
            sa.Column("source_video_id", sa.BigInteger(), nullable=True),
            sa.Column("file_name", sa.Text(), nullable=False),
            sa.Column("file_path", sa.Text(), nullable=False),
            sa.Column("width", sa.Integer(), nullable=False),
            sa.Column("height", sa.Integer(), nullable=False),
            sa.Column("frame_index", sa.Integer(), nullable=True),
            sa.Column("timestamp_sec", sa.Float(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["upload_job_id"], ["upload_jobs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_video_id"], ["source_videos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_images_project", "images", ["project_id"])

    if "image_assignments" not in tables:
        op.create_table(
            "image_assignments",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("image_id", sa.BigInteger(), nullable=False),
            sa.Column("assigned_to", sa.BigInteger(), nullable=False),
            sa.Column("assigned_by", sa.BigInteger(), nullable=False),
            sa.Column("reviewer_id", sa.BigInteger(), nullable=True),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "assigned",
                    "in_progress",
                    "submitted",
                    "review_assigned",
                    "approved",
                    "reverted",
                    "rejected",
                    name="assignment_status",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("approved_by", sa.BigInteger(), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("reverted_by", sa.BigInteger(), nullable=True),
            sa.Column("reverted_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("revert_reason", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
            sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["reverted_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("image_id", name="uq_image_assignment"),
        )
        op.create_index("idx_assignment_status", "image_assignments", ["status"])

    if "annotations" not in tables:
        op.create_table(
            "annotations",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("assignment_id", sa.BigInteger(), nullable=False),
            sa.Column("image_id", sa.BigInteger(), nullable=False),
            sa.Column("class_id", sa.BigInteger(), nullable=False),
            sa.Column("x", sa.Float(), nullable=False),
            sa.Column("y", sa.Float(), nullable=False),
            sa.Column("width", sa.Float(), nullable=False),
            sa.Column("height", sa.Float(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column(
                "source",
                postgresql.ENUM("auto", "manual", name="annotation_source", create_type=False),
                nullable=False,
            ),
            sa.Column("created_by", sa.BigInteger(), nullable=False),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "x >= 0 AND x <= 1 AND y >= 0 AND y <= 1"
                " AND width > 0 AND width <= 1 AND height > 0 AND height <= 1",
                name="chk_bbox_coordinate",
            ),
            sa.ForeignKeyConstraint(["assignment_id"], ["image_assignments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["class_id"], ["project_classes.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_annotations_image", "annotations", ["image_id"])
        op.create_index("idx_annotations_assignment", "annotations", ["assignment_id"])
        op.create_index("idx_annotations_class", "annotations", ["class_id"])

    if "dataset_versions" not in tables:
        op.create_table(
            "dataset_versions",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.BigInteger(), nullable=False),
            sa.Column("version", sa.Text(), nullable=False),
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
            sa.UniqueConstraint("project_id", "version", name="uq_dataset_version"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    for tbl in [
        "dataset_versions",
        "annotations",
        "image_assignments",
        "images",
        "source_videos",
        "upload_jobs",
    ]:
        if tbl in tables:
            op.drop_table(tbl)
