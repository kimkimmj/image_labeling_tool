"""OAuth redirect_uri 값을 IdP 등록값과 일관되게 관리한다."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request

from app.core.config import settings
from app.core.local_dev_origins import LAN_VITE_ORIGIN_RE
from app.models.enums import OAuthProvider

_CALLBACK_SUFFIX: dict[OAuthProvider, str] = {
    OAuthProvider.google: "/api/auth/oauth/google/callback",
    OAuthProvider.naver: "/api/auth/oauth/naver/callback",
    OAuthProvider.kakao: "/api/auth/oauth/kakao/callback",
}


def _norm_origin_base(origin: str) -> str:
    return origin.strip().rstrip("/").lower()


def _oauth_request_origin_candidates(request: Request) -> list[str]:
    out: list[str] = []
    origin = request.headers.get("origin")
    if origin and origin.strip():
        out.append(origin.strip())
    referer = request.headers.get("referer")
    if referer and referer.strip():
        p = urlparse(referer.strip())
        if p.scheme and p.netloc:
            out.append(f"{p.scheme}://{p.netloc}")
    return out


def _google_callback_from_cors_origin(request: Request) -> str | None:
    """CORS 허용 Origin 과 호스트가 같으면 해당 호스트의 Google callback URL."""
    suffix = _CALLBACK_SUFFIX[OAuthProvider.google]
    allowed = {_norm_origin_base(x) for x in settings.cors_origins}
    for raw in _oauth_request_origin_candidates(request):
        p = urlparse(raw)
        if not p.scheme or not p.netloc:
            continue
        base = f"{p.scheme}://{p.netloc}".rstrip("/")
        if _norm_origin_base(base) in allowed:
            return f"{base}{suffix}"
    # `CORS_ORIGINS`에 LAN IP를 일일이 넣지 않아도 local + 사설망 Vite 접근 가능
    if settings.app_env == "local":
        for raw in _oauth_request_origin_candidates(request):
            p = urlparse(raw)
            if not p.scheme or not p.netloc:
                continue
            base = f"{p.scheme}://{p.netloc}".rstrip("/")
            if LAN_VITE_ORIGIN_RE.match(base):
                return f"{base}{suffix}"
    return None


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
    """로그인 요청의 Origin·Referer에 맞춰 Google redirect_uri 후보를 고른다.

    LAN IP처럼 CORS 에 등록한 프론트 호스트와 콜백 호스트를 맞추고, localhost/127 은 예전처럼
    둘 중 하나를 고른다. 호스트별 쿠키 분리 때문에 프론트 호스트와 콜백 호스트가 달라지면 안 된다.
    """
    from_cors = _google_callback_from_cors_origin(request)
    if from_cors:
        return from_cors
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
    """IdP에 넘길 redirect_uri. Google은 시작 페이지 호스트(CORS 허용 Origin 포함)와 콜백을 맞춘다.

    Google Cloud Console 에는 사용하는 각 redirect_uri를 모두 등록해야 한다(localhost, LAN IP 등).
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
    pu = urlparse(u)
    if settings.app_env == "local" and pu.scheme and pu.netloc:
        origin = f"{pu.scheme}://{pu.netloc}"
        if LAN_VITE_ORIGIN_RE.match(origin):
            pth = pu.path.rstrip("/")
            oauth_paths = {s.rstrip("/") for s in _CALLBACK_SUFFIX.values()}
            if pth in oauth_paths:
                return True
    trusted = {
        settings.oauth_google_redirect_uri,
        settings.oauth_naver_redirect_uri,
        settings.oauth_kakao_redirect_uri,
    }
    trusted |= google_oauth_redirect_variants()
    return u in trusted
