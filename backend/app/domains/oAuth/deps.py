from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.session_store import RedisSessionStore, redis_session_store_from_request
from app.db.session import get_db
from app.domains.oAuth.repositories.oauth_identity_repository import OAuthIdentityRepository
from app.domains.oAuth.repositories.user_repository import UserRepository
from app.domains.oAuth.services.idp import OAuthIdpClient
from app.domains.oAuth.services.login_service import OAuthLoginService
from app.domains.oAuth.services.pkce import PkceGenerator
from app.domains.oAuth.services.session_service import SessionService
from app.models import User
from app.models.enums import OAuthProvider


def parse_oauth_provider(provider: str) -> OAuthProvider:
    """경로 변수 문자열을 OAuthProvider 열거(Enum)형으로 반환한다.

    알 수 없는 값이면 404를 위한 HTTPException을 발생시키므로 라우터에서 그대로 사용한다.
    """
    try:
        return OAuthProvider(provider)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="unknown oauth provider",
        ) from exc


def get_session_store(request: Request) -> RedisSessionStore:
    """요청 스코프 Redis 세션 스토어를 반환한다."""
    return redis_session_store_from_request(request)


def get_session_service(
    store: RedisSessionStore = Depends(get_session_store),
) -> SessionService:
    """로그아웃 등 세션 무효화용 서비스."""
    return SessionService(store)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """세션 쿠키로 로그인 사용자 ORM을 조회한다.

    미인증이면 401을 발생시키므로 보호 라우트에서 Depends로 사용한다.
    """
    sid = request.cookies.get(settings.session_cookie_name)
    store = redis_session_store_from_request(request)
    uid = store.get_user_id(sid)
    if uid is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    return user


def get_oauth_idp_client() -> OAuthIdpClient:
    """상태 없는 IdP 클라이언트 인스턴스를 반환한다."""
    return OAuthIdpClient()


def get_pkce_generator() -> PkceGenerator:
    """PKCE 생성기 인스턴스를 반환한다."""
    return PkceGenerator()


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    """SQLAlchemy 세션에 묶인 UserRepository를 반환한다."""
    return UserRepository(db)


def get_oauth_identity_repository(
    db: Session = Depends(get_db),
) -> OAuthIdentityRepository:
    """SQLAlchemy 세션에 묶인 OAuthIdentityRepository를 반환한다."""
    return OAuthIdentityRepository(db)


def get_oauth_login_service(
    db: Session = Depends(get_db),
    store: RedisSessionStore = Depends(get_session_store),
    users: UserRepository = Depends(get_user_repository),
    oauth_identities: OAuthIdentityRepository = Depends(get_oauth_identity_repository),
    idp_client: OAuthIdpClient = Depends(get_oauth_idp_client),
    pkce: PkceGenerator = Depends(get_pkce_generator),
) -> OAuthLoginService:
    """OAuth 로그인 유스케이스 서비스를 생성자 주입으로 조립한다."""
    return OAuthLoginService(
        db,
        store,
        users,
        oauth_identities,
        idp_client,
        pkce,
    )
