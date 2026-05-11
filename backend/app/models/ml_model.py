"""ML 모델·클래스·프로젝트 클래스 ORM."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MlModel(Base):
    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str | None] = mapped_column(Text, nullable=True)
    framework: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    classes: Mapped[list["ModelClass"]] = relationship(
        back_populates="model",
        cascade="all, delete-orphan",
    )


class ModelClass(Base):
    __tablename__ = "model_classes"
    __table_args__ = (
        UniqueConstraint("model_id", "class_index", name="uq_model_class_index"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ml_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    class_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    model: Mapped[MlModel] = relationship(back_populates="classes")


class ProjectClass(Base):
    __tablename__ = "project_classes"
    __table_args__ = (
        UniqueConstraint("project_id", "export_index", name="uq_project_export_index"),
        UniqueConstraint("project_id", "name", name="uq_project_class_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_class_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("model_classes.id", ondelete="SET NULL"),
        nullable=True,
    )
    export_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )
