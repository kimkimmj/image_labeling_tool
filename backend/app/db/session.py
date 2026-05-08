from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.resolved_database_url,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """요청 단위 SQLAlchemy 세션을 제공하는 FastAPI Depends용 제너레이터.

    요청 종료 시 세션을 닫아 커넥션을 풀에 반환한다.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
