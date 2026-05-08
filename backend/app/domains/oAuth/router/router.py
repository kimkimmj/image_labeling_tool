import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.core.config import settings
from app.domains.oAuth.cookies import (
    OAuthFlowCookieWriter,
    SessionCookieWriter,
    get_oauth_flow_cookie_writer,
    get_session_cookie_writer,
)
from app.domains.oAuth.deps import (
    get_current_user,
    get_oauth_idp_client,
    get_oauth_login_service,
    get_session_service,
    parse_oauth_provider,
)
from app.domains.oAuth.schemas.schemas import MeResponse
from app.domains.oAuth.services.exceptions import (
    EmailConflictError,
    OAuthEmailMissingError,
    OAuthExchangeError,
    OAuthInvalidStateError,
)
from app.domains.oAuth.oauth_flow_cookie_parse import oauth_flow_payload_from_request
from app.domains.oAuth.oauth_redirect import (
    get_oauth_redirect_uri,
)
from app.domains.oAuth.services.idp import OAuthIdpClient
from app.domains.oAuth.services.login_service import OAuthCookiePayload, OAuthLoginService
from app.domains.oAuth.services.session_service import SessionService
from app.models import User
from app.models.enums import OAuthProvider

router = APIRouter(tags=["auth"])

_logger = logging.getLogger(__name__)


@router.get("/auth/oauth/{provider}/login")
def oauth_login(
    provider: str,
    request: Request,
    idp_client: OAuthIdpClient = Depends(get_oauth_idp_client),
    oauth_svc: OAuthLoginService = Depends(get_oauth_login_service),
    flow_cookies: OAuthFlowCookieWriter = Depends(get_oauth_flow_cookie_writer),
) -> RedirectResponse:
    """브라우저를 IdP 인가 페이지로 보내고 state/PKCE 쿠키를 심는다."""
    p = parse_oauth_provider(provider)
    # oauth provider의 설정값이 있는지 확인
    if not idp_client.has_provider_configured(p):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth provider not configured",
        )
    redirect_uri = get_oauth_redirect_uri(request, p)
    if p == OAuthProvider.google:
        _logger.info(
            "Google OAuth: redirect_uri=%s — Google Cloud Console에 이 문자열을 그대로 등록하세요.",
            redirect_uri,
        )
    url, state, verifier = oauth_svc.build_oauth_login_url(p, redirect_uri=redirect_uri)
    response = RedirectResponse(url=url, status_code=302)
    flow_cookies.set_flow_cookies(
        response,
        verifier=verifier,
        state=state,
        oauth_redirect_uri=redirect_uri,
    )
    return response


@router.get("/auth/oauth/{provider}/callback")
def oauth_callback(
    provider: str,
    request: Request,
    code: str,
    state: str,
    oauth_svc: OAuthLoginService = Depends(get_oauth_login_service),
    flow_cookies: OAuthFlowCookieWriter = Depends(get_oauth_flow_cookie_writer),
    session_cookies: SessionCookieWriter = Depends(get_session_cookie_writer),
) -> RedirectResponse:
    """인가 코드 교환·사용자 확정 후 세션 쿠키를 설정하고 프론트로 리다이렉트한다."""
    p = parse_oauth_provider(provider)
    payload: OAuthCookiePayload | None = oauth_flow_payload_from_request(request, p)

    try:
        _, session_id = oauth_svc.complete_oauth_login(
            p,
            code=code,
            state_query=state,
            payload=payload,
        )
    except OAuthInvalidStateError as exc:
        msg = str(exc) or "invalid oauth state"
        _logger.warning("oauth google callback invalid state: %s", msg)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from exc
    except OAuthEmailMissingError as exc:
        _logger.warning("oauth google callback missing email")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="email required from identity provider",
        ) from exc
    except OAuthExchangeError as exc:
        _logger.warning("oauth google token exchange failed: %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except EmailConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="email already registered with another login method",
        ) from exc

    response = RedirectResponse(
        settings.oauth_success_redirect_url,
        status_code=302,
    )
    session_cookies.set_session_cookie(response, session_id)
    flow_cookies.clear_flow_cookies(response)
    return response


@router.post("/auth/logout")
def logout(
    request: Request,
    session_svc: SessionService = Depends(get_session_service),
    cookie_writer: SessionCookieWriter = Depends(get_session_cookie_writer),
) -> JSONResponse:
    """Redis 세션을 삭제하고 세션 쿠키를 만료시킨다."""
    sid = request.cookies.get(settings.session_cookie_name)
    session_svc.logout(sid)
    body = JSONResponse({"ok": True})
    cookie_writer.clear_session_cookie(body)
    return body


@router.get("/me", response_model=MeResponse)
def read_me(current_user: User = Depends(get_current_user)) -> MeResponse:
    """세션으로 인증된 사용자 정보를 DTO로 반환한다."""
    return MeResponse.model_validate(current_user)
