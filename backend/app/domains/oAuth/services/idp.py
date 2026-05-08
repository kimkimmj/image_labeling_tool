from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.domains.oAuth.services.exceptions import OAuthEmailMissingError, OAuthExchangeError
from app.models.enums import OAuthProvider


@dataclass(frozen=True)
class OAuthProfile:
    """IdP에서 조회한 최소 사용자 식별 정보."""

    provider_subject: str
    email: str


def _oauth_token_error_message(response: httpx.Response) -> str:
    """토큰 엔드포인트 4xx 시 응답 본문에서 사람이 읽을 수 있는 메시지를 뽑는다."""
    try:
        payload = response.json()
    except Exception:
        return response.text.strip() or response.reason_phrase
    err = payload.get("error_description") or payload.get("error")
    if isinstance(err, str) and err.strip():
        return err.strip()
    return response.text.strip() or response.reason_phrase


class OAuthIdpClient:
    """Google/Naver/Kakao OAuth2(OIDC) 인가 URL 생성 및 코드 교환·프로필 조회.

    라우터·OAuthLoginService가 IdP와 통신할 때 사용한다. 상태를 두지 않는 게이트웨이다.
    """

    def build_authorize_url(
        self,
        provider: OAuthProvider,
        *,
        state: str,
        code_challenge: str,
        redirect_uri: str,
    ) -> str:
        """인가 엔드포인트로 리다이렉트할 전체 URL을 만든다.

        로그인 시작(/oauth/.../login) 시 브라우저를 IdP로 보낼 때 호출한다.

        Raises:
            OAuthExchangeError: 지원하지 않는 provider인 경우.
        """
        if provider == OAuthProvider.google:
            return self._google_authorize_url(
                state=state,
                code_challenge=code_challenge,
                redirect_uri=redirect_uri,
            )
        if provider == OAuthProvider.naver:
            return self._naver_authorize_url(
                state=state,
                redirect_uri=redirect_uri,
            )
        if provider == OAuthProvider.kakao:
            return self._kakao_authorize_url(
                state=state,
                code_challenge=code_challenge,
                redirect_uri=redirect_uri,
            )
        raise OAuthExchangeError("unsupported provider")

    def fetch_profile_after_code(
        self,
        provider: OAuthProvider,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> OAuthProfile:
        """인가 코드로 액세스 토큰을 받고 프로필에서 subject·이메일을 추출한다.

        OAuth 콜백 처리 중 Redis 세션을 만들기 전에 호출한다.

        Raises:
            OAuthExchangeError: HTTP 오류 또는 필수 필드 누락.
            OAuthEmailMissingError: 이메일 동의·스코프 부족 등으로 이메일이 비어 있는 경우.
        """
        try:
            if provider == OAuthProvider.google:
                return self._google_profile(
                    code=code,
                    code_verifier=code_verifier,
                    redirect_uri=redirect_uri,
                )
            if provider == OAuthProvider.naver:
                return self._naver_profile(
                    code=code,
                    code_verifier=code_verifier,
                    redirect_uri=redirect_uri,
                )
            if provider == OAuthProvider.kakao:
                return self._kakao_profile(
                    code=code,
                    code_verifier=code_verifier,
                    redirect_uri=redirect_uri,
                )
        except httpx.HTTPError as exc:
            raise OAuthExchangeError(str(exc)) from exc
        raise OAuthExchangeError("unsupported provider")

    def has_provider_configured(self, provider: OAuthProvider) -> bool:
        """환경 변수에 해당 IdP 클라이언트 설정이 있는지 확인한다.

        로그인 라우트에서 미설정 시 503을 내기 위해 호출한다.
        """
        if provider == OAuthProvider.google:
            return bool(
                settings.oauth_google_client_id and settings.oauth_google_client_secret
            )
        if provider == OAuthProvider.naver:
            return bool(
                settings.oauth_naver_client_id and settings.oauth_naver_client_secret
            )
        if provider == OAuthProvider.kakao:
            return bool(
                settings.oauth_kakao_client_id and settings.oauth_kakao_client_secret
            )
        return False

    @staticmethod
    def _google_authorize_url(
        *, state: str, code_challenge: str, redirect_uri: str
    ) -> str:
        q = urlencode(
            {
                "client_id": settings.oauth_google_client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": "openid email profile",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{q}"

    @staticmethod
    def _naver_authorize_url(*, state: str, redirect_uri: str) -> str:
        q = urlencode(
            {
                "response_type": "code",
                "client_id": settings.oauth_naver_client_id,
                "redirect_uri": redirect_uri,
                "state": state,
            }
        )
        return f"https://nid.naver.com/oauth2.0/authorize?{q}"

    @staticmethod
    def _kakao_authorize_url(
        *, state: str, code_challenge: str, redirect_uri: str
    ) -> str:
        q = urlencode(
            {
                "response_type": "code",
                "client_id": settings.oauth_kakao_client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": "account_email",
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"https://kauth.kakao.com/oauth/authorize?{q}"

    @staticmethod
    def _google_profile(*, code: str, code_verifier: str, redirect_uri: str) -> OAuthProfile:
        with httpx.Client(timeout=30.0) as client:
            token_res = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.oauth_google_client_id,
                    "client_secret": settings.oauth_google_client_secret,
                    "code": code,
                    "code_verifier": code_verifier,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            if token_res.is_error:
                raise OAuthExchangeError(_oauth_token_error_message(token_res))
            access_token = token_res.json()["access_token"]
            ui = client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            ui.raise_for_status()
            data = ui.json()
        email = (data.get("email") or "").strip()
        sub = data.get("sub")
        if not sub:
            raise OAuthExchangeError("missing subject")
        if not email:
            raise OAuthEmailMissingError()
        return OAuthProfile(provider_subject=str(sub), email=email)

    @staticmethod
    def _naver_profile(*, code: str, code_verifier: str, redirect_uri: str) -> OAuthProfile:
        _ = code_verifier
        with httpx.Client(timeout=30.0) as client:
            token_res = client.post(
                "https://nid.naver.com/oauth2.0/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.oauth_naver_client_id,
                    "client_secret": settings.oauth_naver_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            token_res.raise_for_status()
            access_token = token_res.json()["access_token"]
            ui = client.get(
                "https://openapi.naver.com/v1/nid/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            ui.raise_for_status()
            payload = ui.json()
        resp = payload.get("response") or {}
        subject = resp.get("id")
        email = (resp.get("email") or "").strip()
        if subject is None:
            raise OAuthExchangeError("missing naver id")
        if not email:
            raise OAuthEmailMissingError()
        return OAuthProfile(provider_subject=str(subject), email=email)

    @staticmethod
    def _kakao_profile(*, code: str, code_verifier: str, redirect_uri: str) -> OAuthProfile:
        with httpx.Client(timeout=30.0) as client:
            token_res = client.post(
                "https://kauth.kakao.com/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.oauth_kakao_client_id,
                    "client_secret": settings.oauth_kakao_client_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                    "code_verifier": code_verifier,
                },
            )
            token_res.raise_for_status()
            access_token = token_res.json()["access_token"]
            ui = client.get(
                "https://kapi.kakao.com/v2/user/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            ui.raise_for_status()
            data = ui.json()
        kid = data.get("id")
        acct = data.get("kakao_account") or {}
        email = (acct.get("email") or "").strip()
        if kid is None:
            raise OAuthExchangeError("missing kakao id")
        if not email:
            raise OAuthEmailMissingError()
        return OAuthProfile(provider_subject=str(kid), email=email)
