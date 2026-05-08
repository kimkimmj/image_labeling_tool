import secrets

from starlette.requests import Request

from app.core.config import settings


class RedisSessionStore:
    """Redis에 `sess:{id}` 형태로 user_id를 TTL과 함께 저장하는 세션 백엔드."""

    PREFIX = "sess:"

    def __init__(self, redis_client: object, ttl_seconds: int) -> None:
        self._r = redis_client
        self._ttl = ttl_seconds

    def create(self, user_id: int) -> str:
        """무작위 세션 ID를 만들고 Redis에 user_id를 저장한 뒤 ID를 반환한다."""
        sid = secrets.token_urlsafe(32)
        key = self.PREFIX + sid
        self._r.setex(key, self._ttl, str(user_id))
        return sid

    def get_user_id(self, session_id: str | None) -> int | None:
        """세션 ID로 user_id를 조회한다. 없거나 만료되면 None."""
        if not session_id:
            return None
        raw = self._r.get(self.PREFIX + session_id)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return int(raw)

    def delete(self, session_id: str | None) -> None:
        """로그아웃 시 해당 세션 키를 삭제한다."""
        if session_id:
            self._r.delete(self.PREFIX + session_id)


def redis_session_store_from_request(request: Request) -> RedisSessionStore:
    """요청의 FastAPI app.state Redis 클라이언트로 세션 스토어를 만든다."""
    return RedisSessionStore(
        request.app.state.redis_client,
        settings.session_ttl_seconds,
    )
