from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.ml_model import MlModel, ModelClass, ProjectClass
from app.models.project import Project, ProjectInvitation, ProjectUser
from app.models.upload import Annotation, Image, ImageAssignment, UploadJob

oauth_provider_db = PG_ENUM(
    "google",
    "naver",
    "kakao",
    name="oauth_provider",
    create_type=False,
)


class User(Base):
    """앱 사용자. OAuth 전용은 password_hash 가 NULL일 수 있다."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="FALSE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    oauth_identities: Mapped[list["OAuthIdentity"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class OAuthIdentity(Base):
    """외부 IdP 계정과 users 행을 매핑한다."""

    __tablename__ = "oauth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_oauth_provider_subject"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(oauth_provider_db, nullable=False)
    provider_subject: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="oauth_identities")
