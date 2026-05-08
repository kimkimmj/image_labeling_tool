"""OAuth 플로우 쿠키: 단일 쿠키(Base64(JSON)) 또는 구버전 분리 쿠키 해석."""

from __future__ import annotations

import base64
import json

from fastapi import Request

from app.core.config import settings
from app.domains.oAuth.oauth_redirect import default_oauth_redirect_uri, is_trusted_oauth_redirect_uri
from app.domains.oAuth.services.login_service import OAuthCookiePayload
from app.models.enums import OAuthProvider


def _b64_decode_json(blob: str) -> dict[str, str] | None:
    try:
        pad = "=" * (-len(blob) % 4)
        raw = base64.urlsafe_b64decode(blob.strip() + pad)
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    out = {}
    for k, v in parsed.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out


def oauth_flow_payload_from_request(
    request: Request,
    provider: OAuthProvider,
) -> OAuthCookiePayload | None:
    """통합 또는 레거시 쿠키에서 OAuthCookiePayload를 조립한다."""

    unified = request.cookies.get(settings.oauth_flow_cookie_name)
    if unified:
        data = _b64_decode_json(unified)
        if not data:
            return None
        state = data.get("s") or ""
        if not state:
            return None
        verifier = data.get("v") or ""
        raw_redirect = (data.get("r") or "").strip()
        if raw_redirect and is_trusted_oauth_redirect_uri(raw_redirect):
            redirect_uri = raw_redirect
        else:
            redirect_uri = default_oauth_redirect_uri(provider)
        return OAuthCookiePayload(
            verifier=verifier,
            state=state,
            redirect_uri=redirect_uri,
        )

    raw_state = request.cookies.get(settings.oauth_state_cookie_name)
    if not raw_state:
        return None
    raw_verifier = request.cookies.get(settings.oauth_pkce_cookie_name, "") or ""
    raw_redirect = (request.cookies.get(settings.oauth_redirect_uri_cookie_name) or "").strip()
    if raw_redirect and is_trusted_oauth_redirect_uri(raw_redirect):
        callback_redirect_uri = raw_redirect
    else:
        callback_redirect_uri = default_oauth_redirect_uri(provider)
    return OAuthCookiePayload(
        verifier=raw_verifier,
        state=raw_state,
        redirect_uri=callback_redirect_uri,
    )
