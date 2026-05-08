import secrets
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.session_store import RedisSessionStore
from app.domains.oAuth.repositories.oauth_identity_repository import OAuthIdentityRepository
from app.domains.oAuth.repositories.user_repository import UserRepository
from app.domains.oAuth.services.exceptions import EmailConflictError, OAuthInvalidStateError
from app.domains.oAuth.services.idp import OAuthIdpClient, OAuthProfile
from app.domains.oAuth.services.pkce import PkceGenerator
from app.models.enums import OAuthProvider


@dataclass(frozen=True)
class OAuthCookiePayload:
    """OAuth 콜백 시 브라우저가 보내는 state/PKCE·redirect_uri 쿠키 묶음."""

    verifier: str
    state: str
    redirect_uri: str


class OAuthLoginService:
    """OAuth 코드 플로우로 사용자를 조회·생성하고 Redis 세션을 발급한다.

    Repository·IdP·PKCE를 생성자 주입으로 받아 유스케이스 단위로 조합한다.
    """

    def __init__(
        self,
        db: Session,
        session_store: RedisSessionStore,
        user_repository: UserRepository,
        oauth_identity_repository: OAuthIdentityRepository,
        idp_client: OAuthIdpClient,
        pkce_generator: PkceGenerator,
    ) -> None:
        self._db = db
        self._sessions = session_store
        self._users = user_repository
        self._oauth_identities = oauth_identity_repository
        self._idp = idp_client
        self._pkce = pkce_generator

    def build_oauth_login_url(
        self,
        provider: OAuthProvider,
        *,
        redirect_uri: str,
    ) -> tuple[str, str, str]:
        """인가 URL과 state·PKCE verifier(쿠키 저장용)를 준비한다.

        GET /auth/oauth/{provider}/login 처리 시 호출한다.

        Returns:
            (authorize_url, state, verifier). Naver는 verifier가 빈 문자열이다.
        """
        state = secrets.token_urlsafe(16)
        if provider == OAuthProvider.naver:
            verifier = ""
            url = self._idp.build_authorize_url(
                provider,
                state=state,
                code_challenge="",
                redirect_uri=redirect_uri,
            )
            return url, state, verifier
        verifier, challenge = self._pkce.generate_pair()
        url = self._idp.build_authorize_url(
            provider,
            state=state,
            code_challenge=challenge,
            redirect_uri=redirect_uri,
        )
        return url, state, verifier

    def complete_oauth_login(
        self,
        provider: OAuthProvider,
        *,
        code: str,
        state_query: str,
        payload: OAuthCookiePayload | None,
    ) -> tuple[int, str]:
        """콜백 코드 검증 후 사용자 확정·커밋 및 세션 ID 발급을 수행한다.

        GET /auth/oauth/{provider}/callback 에서 호출한다.

        Returns:
            (user_id, session_id).

        Raises:
            OAuthInvalidStateError: 쿠키/state/PKCE 불일치.
            OAuthExchangeError, OAuthEmailMissingError: IdP 계층에서 전달.
            EmailConflictError: 이메일이 다른 계정에 이미 존재.
        """
        if payload is None:
            raise OAuthInvalidStateError("missing oauth flow cookies")
        if payload.state != state_query:
            raise OAuthInvalidStateError("oauth state mismatch")
        if provider != OAuthProvider.naver and not payload.verifier:
            raise OAuthInvalidStateError("missing pkce verifier cookie")

        try:
            profile = self._idp.fetch_profile_after_code(
                provider,
                code=code,
                code_verifier=payload.verifier,
                redirect_uri=payload.redirect_uri,
            )
            user_id = self._resolve_or_create_user(provider, profile)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        session_id = self._sessions.create(user_id)
        return user_id, session_id

    def _resolve_or_create_user(
        self,
        provider: OAuthProvider,
        profile: OAuthProfile,
    ) -> int:
        """기존 oauth_identity 또는 신규 user+identity 행을 확정한다."""
        existing_identity = self._oauth_identities.find_by_provider_subject(
            provider,
            profile.provider_subject,
        )
        if existing_identity is not None:
            return existing_identity.user_id

        other = self._users.get_by_email(profile.email)
        if other is not None:
            raise EmailConflictError()

        user = self._users.create(email=profile.email, password_hash=None)
        self._oauth_identities.create(
            user_id=user.id,
            provider=provider,
            provider_subject=profile.provider_subject,
        )
        return user.id
