"""프로젝트·초대 유스케이스."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domains.projects.exceptions import (
    InvitationInvalidError,
    ProjectActiveUploadsError,
    ProjectDeleteNameMismatchError,
    ProjectForbiddenError,
    ProjectNotFoundError,
    ProjectStoragePurgeError,
)
from app.domains.projects.repositories.invitation_repository import InvitationRepository
from app.domains.projects.repositories.project_repository import ProjectRepository
from app.domains.uploads.repositories.upload_repository import UploadRepository
from app.core.storage import StorageClient
from app.models.enums import InvitationStatus, ProjectRole


def _utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProjectSummaryDTO:
    id: int
    name: str
    description: str | None
    created_at: datetime


@dataclass(frozen=True)
class ProjectDetailDTO:
    id: int
    name: str
    description: str | None
    created_at: datetime
    my_role: str


@dataclass(frozen=True)
class ProjectMemberDTO:
    user_id: int
    email: str
    role: str
    created_at: datetime


@dataclass(frozen=True)
class CreateInvitationResultDTO:
    invitation_id: int
    token: str
    join_url: str
    expires_at: datetime


class ProjectService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._projects = ProjectRepository(db)
        self._invitations = InvitationRepository(db)

    def _membership_or_raise(self, project_id: int, user_id: int) -> None:
        m = self._projects.get_membership(project_id, user_id)
        if m is None:
            raise ProjectNotFoundError

    def _owner_membership_or_raise(self, project_id: int, user_id: int) -> None:
        m = self._projects.get_membership(project_id, user_id)
        if m is None:
            raise ProjectNotFoundError
        if m.role != ProjectRole.owner.value:
            raise ProjectForbiddenError

    def create_project(
        self,
        *,
        user_id: int,
        name: str,
        description: str | None,
    ) -> ProjectSummaryDTO:
        project = self._projects.create_project(
            name=name,
            description=description,
            created_by=user_id,
        )
        self._projects.add_member(
            project_id=project.id,
            user_id=user_id,
            role=ProjectRole.owner.value,
            invited_by=user_id,
        )
        self._db.commit()
        self._db.refresh(project)
        return ProjectSummaryDTO(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
        )

    def list_owned(self, user_id: int) -> list[ProjectSummaryDTO]:
        rows = self._projects.list_projects_owned_by(user_id)
        return [
            ProjectSummaryDTO(id=p.id, name=p.name, description=p.description, created_at=p.created_at)
            for p in rows
        ]

    def list_member_non_owner(self, user_id: int) -> list[ProjectSummaryDTO]:
        rows = self._projects.list_projects_member_non_owner(user_id)
        return [
            ProjectSummaryDTO(id=p.id, name=p.name, description=p.description, created_at=p.created_at)
            for p in rows
        ]

    def get_project_for_member(self, project_id: int, user_id: int) -> ProjectDetailDTO:
        m = self._projects.get_membership(project_id, user_id)
        if m is None:
            raise ProjectNotFoundError
        project = self._projects.get_project(project_id)
        if project is None:
            raise ProjectNotFoundError
        return ProjectDetailDTO(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            my_role=m.role,
        )

    def delete_project_as_owner(
        self,
        *,
        project_id: int,
        owner_user_id: int,
        confirm_name: str,
        storage: StorageClient,
    ) -> bool:
        """스토리지 prefix 삭제 후 DB에서 프로젝트를 삭제한다.

        Returns:
            True if a row was deleted, False if project was already absent (idempotent).

        Raises:
            ProjectNotFoundError / ProjectForbiddenError
            ProjectDeleteNameMismatchError
            ProjectActiveUploadsError
            ProjectStoragePurgeError
        """
        project = self._projects.get_project(project_id)
        if project is None:
            return False

        self._owner_membership_or_raise(project_id, owner_user_id)

        if confirm_name != project.name:
            raise ProjectDeleteNameMismatchError

        uploads = UploadRepository(self._db)
        if uploads.count_active_upload_jobs(project_id) > 0:
            raise ProjectActiveUploadsError

        prefix = f"projects/{project_id}/"
        try:
            storage.delete_prefix(prefix)
        except Exception as exc:
            raise ProjectStoragePurgeError(str(exc)) from exc

        try:
            self._projects.delete_project(project_id)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        return True

    def list_members(self, project_id: int, user_id: int) -> list[ProjectMemberDTO]:
        self._owner_membership_or_raise(project_id, user_id)
        rows = self._projects.list_members_for_project(project_id)
        return [
            ProjectMemberDTO(
                user_id=pu.user_id,
                email=u.email,
                role=pu.role,
                created_at=pu.created_at,
            )
            for pu, u in rows
        ]

    def create_invitation(
        self,
        *,
        project_id: int,
        owner_user_id: int,
        role: str,
    ) -> CreateInvitationResultDTO:
        self._owner_membership_or_raise(project_id, owner_user_id)
        raw = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw)
        now = _utc_naive_now()
        expires_at = now + timedelta(seconds=settings.invite_link_ttl_seconds)
        inv = self._invitations.create(
            project_id=project_id,
            role=role,
            token_hash=token_hash,
            status=InvitationStatus.pending.value,
            invited_by=owner_user_id,
            expires_at=expires_at,
        )
        self._db.commit()
        self._db.refresh(inv)
        base = settings.public_app_url.rstrip("/")
        path = settings.invite_join_path if settings.invite_join_path.startswith("/") else f"/{settings.invite_join_path}"
        join_url = f"{base}{path}?token={raw}"
        return CreateInvitationResultDTO(
            invitation_id=inv.id,
            token=raw,
            join_url=join_url,
            expires_at=inv.expires_at,
        )

    def accept_invitation(self, *, user_id: int, token: str) -> ProjectDetailDTO:
        token_hash = _hash_token(token)
        inv = self._invitations.get_pending_by_token_hash(token_hash)
        now = _utc_naive_now()
        if inv is None:
            raise InvitationInvalidError
        if inv.expires_at < now:
            raise InvitationInvalidError
        existing = self._projects.get_membership(inv.project_id, user_id)
        if existing is not None:
            self._invitations.mark_accepted(inv, accepted_by=user_id, accepted_at=now)
            self._db.commit()
            project = self._projects.get_project(inv.project_id)
            assert project is not None
            return ProjectDetailDTO(
                id=project.id,
                name=project.name,
                description=project.description,
                created_at=project.created_at,
                my_role=existing.role,
            )
        self._projects.add_member(
            project_id=inv.project_id,
            user_id=user_id,
            role=inv.role,
            invited_by=inv.invited_by,
        )
        self._invitations.mark_accepted(inv, accepted_by=user_id, accepted_at=now)
        self._db.commit()
        project = self._projects.get_project(inv.project_id)
        membership = self._projects.get_membership(inv.project_id, user_id)
        assert project is not None and membership is not None
        return ProjectDetailDTO(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            my_role=membership.role,
        )
