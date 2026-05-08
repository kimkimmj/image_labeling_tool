from collections.abc import Callable

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_EXEMPT_PATH_PREFIXES = (
    "/api/auth/oauth/",
)


def _origin_allowed(origin: str | None, referer: str | None, allowed: list[str]) -> bool:
    """Origin 또는 Referer가 허용 목록에 속하는지 판별한다.

    동일 출처 프록시 개발 환경에서 일부 클라이언트가 Origin을 생략할 때 Referer로 보완한다.
    """
    if origin:
        return origin in allowed
    if referer:
        base = referer.rstrip("/")
        return any(
            referer.startswith(a + "/") or base == a.rstrip("/")
            for a in allowed
        )
    return False


class CsrfOriginMiddleware(BaseHTTPMiddleware):
    """HttpOnly 세션 쿠키 기반 요청에 대해 Origin/Referer 기반 CSRF 완화를 적용한다.

    OAuth 콜백 등 GET 예외 경로는 제외한다.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """안전 메서드·예외 경로가 아니면 허용 출처 검사 후 다음 핸들러를 호출한다."""
        if request.method in _SAFE_METHODS:
            return await call_next(request)
        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PATH_PREFIXES):
            return await call_next(request)
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        if not _origin_allowed(origin, referer, settings.cors_origins):
            return JSONResponse(
                {"detail": "origin or referer not allowed"},
                status_code=403,
            )
        return await call_next(request)
