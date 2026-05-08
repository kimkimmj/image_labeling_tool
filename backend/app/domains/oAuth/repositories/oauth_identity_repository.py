from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OAuthIdentity
from app.models.enums import OAuthProvider


class OAuthIdentityRepository:
    """oauth_identities 테이블 전용 조회·생성."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_provider_subject(
        self,
        provider: OAuthProvider,
        provider_subject: str,
    ) -> OAuthIdentity | None:
        """기 로그인 여부 판별 시 (provider, subject)로 한 건 조회한다."""
        stmt = select(OAuthIdentity).where(
            OAuthIdentity.provider == provider.value,
            OAuthIdentity.provider_subject == provider_subject,
        )
        return self._session.scalar(stmt)

    def create(
        self,
        *,
        user_id: int,
        provider: OAuthProvider,
        provider_subject: str,
    ) -> OAuthIdentity:
        """신규 OAuth 연동 행을 추가하고 flush한다."""
        row = OAuthIdentity(
            user_id=user_id,
            provider=provider.value,
            provider_subject=provider_subject,
        )
        self._session.add(row)
        self._session.flush()
        return row
