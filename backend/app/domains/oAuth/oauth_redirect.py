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


def google_oauth_redirect_variants() -> frozenset[str]:
    """Google 콜백 URL 후보(127.0.0.1 ↔ localhost). 둘 다 IdP 콘솔에 등록해야 한다."""
    primary = (settings.oauth_google_redirect_uri or "").strip()
    if not primary:
        return frozenset()
    out: set[str] = {primary}
    if "127.0.0.1" in primary:
        out.add(primary.replace("127.0.0.1", "localhost", 1))
    elif "localhost" in primary:
        out.add(primary.replace("localhost", "127.0.0.1", 1))
    return frozenset(out)


def pick_google_redirect_uri(request: Request) -> str:
    """로그인 요청의 Origin/Referer에 맞춰 localhost vs 127.0.0.1 콜백을 고른다.

    브라우저는 호스트별로 쿠키를 분리하므로, 프론트를 localhost로 열었는데 콜백만 127.0.0.1이면
    PKCE/state 쿠키가 콜백 요청에 실리지 않는다.
    """
    variants = sorted(google_oauth_redirect_variants())
    if not variants:
        return settings.oauth_google_redirect_uri
    origin = (request.headers.get("origin") or "").lower()
    referer = (request.headers.get("referer") or "").lower()
    blob = f"{origin} {referer}"
    if "localhost" in blob:
        for v in variants:
            if "localhost" in v:
                return v
    if "127.0.0.1" in blob:
        for v in variants:
            if "127.0.0.1" in v:
                return v
    return variants[0]


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
    """IdP에 넘길 redirect_uri. Google은 로그인 시작 페이지 호스트와 맞추기 위해 localhost / 127.0.0.1 을 고른다.

    Google Cloud Console에는 `google_oauth_redirect_variants()`에 나오는 URI를 모두 등록해야 한다.
    """
    if provider == OAuthProvider.google:
        return pick_google_redirect_uri(request)
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
    trusted |= google_oauth_redirect_variants()
    return u in trusted
