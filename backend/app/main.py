from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.router import api_router
from app.core.config import settings
from app.middleware.csrf import CsrfOriginMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 기동 시 Redis 클라이언트를 app.state에 붙이고 종료 시 연결을 닫는다."""
    app.state.redis_client = redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    try:
        yield
    finally:
        app.state.redis_client.close()


def create_app() -> FastAPI:
    """FastAPI 인스턴스를 만들고 미들웨어·API 라우터를 등록한다."""
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(CsrfOriginMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
