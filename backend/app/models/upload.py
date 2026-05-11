"""UploadJob, Image, ImageAssignment, Annotation ORM 모델."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

upload_type_db = PG_ENUM(
    "image_zip",
    "video",
    name="upload_type",
    create_type=False,
)

upload_status_db = PG_ENUM(
    "pending",
    "processing",
    "completed",
    "failed",
    name="upload_status",
    create_type=False,
)

assignment_status_db = PG_ENUM(
    "unassigned",
    "assigned",
    "in_progress",
    "done",
    "submitted",
    "review_assigned",
    "approved",
    "reverted",
    "rejected",
    name="assignment_status",
    create_type=False,
)

annotation_source_db = PG_ENUM(
    "auto",
    "manual",
    name="annotation_source",
    create_type=False,
)


class SourceVideo(Base):
    """비디오 업로드 원본 (현재 범위: image_zip 전용이므로 참조만 존재)."""

    __tablename__ = "source_videos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    upload_job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("upload_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )


auto_label_status_db = PG_ENUM(
    "skipped",
    "pending",
    "running",
    "completed",
    "failed",
    name="auto_label_status",
    create_type=False,
)


class UploadJob(Base):
    __tablename__ = "upload_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
    )
    upload_type: Mapped[str] = mapped_column(upload_type_db, nullable=False)
    status: Mapped[str] = mapped_column(upload_status_db, nullable=False)
    original_file_name: Mapped[str] = mapped_column(Text, nullable=False)
    original_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    # Phase 4 — 자동 라벨링 상태 분리 추적
    auto_label_status: Mapped[str | None] = mapped_column(auto_label_status_db, nullable=True)
    auto_label_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_label_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )

    images: Mapped[list["Image"]] = relationship(
        back_populates="upload_job",
        cascade="all, delete-orphan",
    )


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    upload_job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("upload_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_video_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("source_videos.id"),
        nullable=True,
    )
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    frame_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    upload_job: Mapped[UploadJob] = relationship(back_populates="images")
    assignment: Mapped["ImageAssignment | None"] = relationship(
        back_populates="image",
        uselist=False,
        cascade="all, delete-orphan",
    )
    annotations: Mapped[list["Annotation"]] = relationship(
        back_populates="image",
        cascade="all, delete-orphan",
    )


class ImageAssignment(Base):
    __tablename__ = "image_assignments"
    __table_args__ = (UniqueConstraint("image_id", name="uq_image_assignment"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    image_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("images.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_to: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
    )
    assigned_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
    )
    reviewer_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(assignment_status_db, nullable=False, index=True)
    approved_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    reverted_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
    )
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    revert_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    image: Mapped[Image] = relationship(back_populates="assignment")
    annotations: Mapped[list["Annotation"]] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
    )


class Annotation(Base):
    __tablename__ = "annotations"
    __table_args__ = (
        CheckConstraint(
            "x >= 0 AND x <= 1 AND y >= 0 AND y <= 1"
            " AND width > 0 AND width <= 1 AND height > 0 AND height <= 1",
            name="chk_bbox_coordinate",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("image_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("images.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    class_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("project_classes.id"),
        nullable=False,
        index=True,
    )
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(annotation_source_db, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="FALSE",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    assignment: Mapped[ImageAssignment] = relationship(back_populates="annotations")
    image: Mapped[Image] = relationship(back_populates="annotations")
