from app.core.session_store import RedisSessionStore


class SessionService:
    """브라우저 세션 쿠키와 연계된 Redis 세션 무효화 유스케이스."""

    def __init__(self, session_store: RedisSessionStore) -> None:
        self._store = session_store

    def logout(self, session_id: str | None) -> None:
        """세션 ID에 해당하는 Redis 키를 삭제한다.

        POST /auth/logout 에서 쿠키 값을 읽은 뒤 호출한다.
        """
        self._store.delete(session_id)
