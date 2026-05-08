"""인증 도메인 전용 Set-Cookie 헬퍼 (OAuth 플로우 + 세션 ID)."""

import base64
import json

from fastapi import Response

from app.core.config import settings


class OAuthFlowCookieWriter:
    """OAuth 로그인 시작·완료 시 state/PKCE 쿠키를 설정하거나 제거한다."""

    def set_flow_cookies(
        self,
        response: Response,
        *,
        verifier: str,
        state: str,
        oauth_redirect_uri: str,
    ) -> None:
        """로그인 리다이렉트 응답에 짧은 TTL HttpOnly 쿠키를 붙인다.

        브라우저가 IdP에서 돌아올 때 콜백에서 state/PKCE·redirect_uri를 검증하기 위해 사용한다.
        """
        common = {
            "max_age": settings.oauth_cookie_max_age_seconds,
            "httponly": True,
            "secure": settings.session_cookie_secure,
            "samesite": settings.session_cookie_same_site,
            "path": "/",
        }
        blob = json.dumps(
            {"s": state, "v": verifier, "r": oauth_redirect_uri},
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        encoded = base64.urlsafe_b64encode(blob).decode("ascii")
        response.set_cookie(settings.oauth_flow_cookie_name, encoded, **common)

    def clear_flow_cookies(self, response: Response) -> None:
        """콜백 성공 후 OAuth 플로우 전용 쿠키를 만료시킨다."""
        response.delete_cookie(settings.oauth_flow_cookie_name, path="/")
        response.delete_cookie(settings.oauth_state_cookie_name, path="/")
        response.delete_cookie(settings.oauth_pkce_cookie_name, path="/")
        response.delete_cookie(settings.oauth_redirect_uri_cookie_name, path="/")


class SessionCookieWriter:
    """Redis 세션 ID를 HttpOnly 쿠키로 내려주거나 로그아웃 시 제거한다."""

    def set_session_cookie(self, response: Response, session_id: str) -> None:
        """OAuth 성공 리다이렉트 등에 세션 쿠키를 설정한다."""
        response.set_cookie(
            settings.session_cookie_name,
            session_id,
            max_age=settings.session_ttl_seconds,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite=settings.session_cookie_same_site,
            path="/",
        )

    def clear_session_cookie(self, response: Response) -> None:
        """로그아웃 응답에서 세션 쿠키를 만료시킨다."""
        response.delete_cookie(settings.session_cookie_name, path="/")


def get_oauth_flow_cookie_writer() -> OAuthFlowCookieWriter:
    """OAuthFlowCookieWriter 의존성 팩토리."""
    return OAuthFlowCookieWriter()


def get_session_cookie_writer() -> SessionCookieWriter:
    """SessionCookieWriter 의존성 팩토리."""
    return SessionCookieWriter()
