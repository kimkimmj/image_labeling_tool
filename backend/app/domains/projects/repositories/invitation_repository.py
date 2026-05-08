"""프로젝트 초대(토큰) DB 접근."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProjectInvitation


class InvitationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        project_id: int,
        role: str,
        token_hash: str,
        status: str,
        invited_by: int,
        expires_at: datetime,
    ) -> ProjectInvitation:
        row = ProjectInvitation(
            project_id=project_id,
            role=role,
            token_hash=token_hash,
            status=status,
            invited_by=invited_by,
            expires_at=expires_at,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get_pending_by_token_hash(self, token_hash: str) -> ProjectInvitation | None:
        stmt = select(ProjectInvitation).where(
            ProjectInvitation.token_hash == token_hash,
            ProjectInvitation.status == "pending",
        )
        return self._session.scalar(stmt)

    def mark_accepted(
        self,
        invitation: ProjectInvitation,
        *,
        accepted_by: int,
        accepted_at: datetime,
    ) -> None:
        invitation.status = "accepted"
        invitation.accepted_by = accepted_by
        invitation.accepted_at = accepted_at
