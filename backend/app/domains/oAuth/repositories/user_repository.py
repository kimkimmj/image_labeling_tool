from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    """users 테이블 전용 조회·생성."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: int) -> User | None:
        """PK로 사용자 한 건을 조회한다."""
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        """이메일 UNIQUE 검색으로 충돌 여부를 확인할 때 사용한다."""
        stmt = select(User).where(User.email == email)
        return self._session.scalar(stmt)

    def create(self, *, email: str, password_hash: str | None = None) -> User:
        """신규 사용자 행을 추가하고 flush하여 ID를 채운다."""
        user = User(email=email, password_hash=password_hash)
        self._session.add(user)
        self._session.flush()
        return user
