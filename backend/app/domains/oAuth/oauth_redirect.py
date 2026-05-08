"""OAuth redirect_uri 값을 IdP 등록값과 일관되게 관리한다."""

from __future__ import annotations

from fastapi import Request

from app.core.config import settings
from app.models.enums import OAuthProvider

_CALLBACK_SUFFIX: dict[OAuthProvider, str] = {
    OAuthProvider.google: "/api/auth/oauth/google/callback",
    OAuthProvider.naver: "/api/auth/oauth/naver/callback",
    OAuthProvider.kakao: "/api/auth/oauth/kakao/callback",
}


def default_oauth_redirect_uri(provider: OAuthProvider) -> str:
    """환경 변수에 정의된 해당 IdP 기본 콜백 URL."""
    if provider == OAuthProvider.google:
        return settings.oauth_google_redirect_uri
    if provider == OAuthProvider.naver:
        return settings.oauth_naver_redirect_uri
    return settings.oauth_kakao_redirect_uri


def request_browser_origin(request: Request) -> str | None:
    """Origin 헤더 또는 Referer에서 브라우저가 쓰는 scheme://host[:port] 를 뽑는다."""
    _ = request
    return None


def get_oauth_redirect_uri(request: Request, provider: OAuthProvider) -> str:
    """환경 변수에 등록한 OAuth 콜백 URI를 그대로 사용한다.

    Google은 인가 요청과 콘솔 등록 URI가 문자 단위로 일치해야 하므로,
    브라우저 출처로 URI를 동적으로 바꾸지 않는다.
    """
    _ = request
    return default_oauth_redirect_uri(provider)


def is_trusted_oauth_redirect_uri(uri: str) -> bool:
    """콜백 시 쿠키에 저장된 redirect_uri 재사용 가능 여부 (오픈 리다이렉트 방지)."""
    u = uri.strip()
    if not u.startswith("http://") and not u.startswith("https://"):
        return False
    allowed_bases = {x.rstrip("/") for x in settings.cors_origins}
    for base in allowed_bases:
        for suffix in _CALLBACK_SUFFIX.values():
            if u == f"{base}{suffix}":
                return True
    trusted = {
        settings.oauth_google_redirect_uri,
        settings.oauth_naver_redirect_uri,
        settings.oauth_kakao_redirect_uri,
    }
    return u in trusted
