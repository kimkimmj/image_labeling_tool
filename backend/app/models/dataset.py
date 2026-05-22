"""Dataset version, split, and export job ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

export_status_db = PG_ENUM(
    "pending",
    "processing",
    "completed",
    "failed",
    name="export_status",
    create_type=False,
)


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_dataset_version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    items: Mapped[list["DatasetItem"]] = relationship(
        back_populates="dataset_version",
        cascade="all, delete-orphan",
    )
    splits: Mapped[list["DatasetSplit"]] = relationship(
        back_populates="dataset_version",
        cascade="all, delete-orphan",
    )


class DatasetItem(Base):
    __tablename__ = "dataset_items"
    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "image_id",
            name="uq_dataset_item_version_image",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("images.id"), nullable=False)
    assignment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("image_assignments.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    dataset_version: Mapped[DatasetVersion] = relationship(back_populates="items")


class DatasetSplit(Base):
    __tablename__ = "dataset_splits"
    __table_args__ = (
        CheckConstraint(
            "train_ratio + val_ratio + test_ratio = 100",
            name="chk_split_ratio",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    train_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    val_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    test_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    dataset_version: Mapped[DatasetVersion] = relationship(back_populates="splits")
    split_items: Mapped[list["SplitItem"]] = relationship(
        back_populates="dataset_split",
        cascade="all, delete-orphan",
    )


class SplitItem(Base):
    __tablename__ = "split_items"
    __table_args__ = (
        CheckConstraint(
            "split_type IN ('train', 'val', 'test')",
            name="chk_split_type",
        ),
        UniqueConstraint(
            "split_id",
            "dataset_item_id",
            name="uq_split_item_per_dataset_item",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    split_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("dataset_splits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("dataset_items.id"),
        nullable=False,
    )
    split_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    dataset_split: Mapped[DatasetSplit] = relationship(back_populates="split_items")
    dataset_item: Mapped[DatasetItem] = relationship()


class ExportJob(Base):
    __tablename__ = "export_jobs"
    __table_args__ = (
        CheckConstraint(
            "export_format IN ('yolo', 'coco')",
            name="chk_export_format",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("dataset_versions.id"),
        nullable=False,
    )
    split_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("dataset_splits.id"),
        nullable=False,
    )
    requested_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(export_status_db, nullable=False, index=True)
    export_format: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="yolo",
    )
    export_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
