from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션·DB·Redis·OAuth·세션 관련 환경 설정."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Image Labeling Tool API"
    app_env: str = "local"

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "ilt"
    db_user: str = "ilt"
    db_password: str = "ilt"

    database_url: str | None = None

    redis_url: str = "redis://127.0.0.1:6379/0"

    session_ttl_seconds: int = 60 * 60 * 24 * 7
    session_cookie_name: str = "ilt_session"
    session_cookie_secure: bool = False
    session_cookie_same_site: str = "lax"

    oauth_pkce_cookie_name: str = "ilt_oauth_pkce"
    oauth_state_cookie_name: str = "ilt_oauth_state"
    oauth_redirect_uri_cookie_name: str = "ilt_oauth_redirect_uri"
    oauth_flow_cookie_name: str = "ilt_oauth_flow"
    oauth_cookie_max_age_seconds: int = 600

    oauth_success_redirect_url: str = "http://localhost:5173/"

    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_google_redirect_uri: str = (
        "http://localhost:5173/api/auth/oauth/google/callback"
    )

    oauth_naver_client_id: str = ""
    oauth_naver_client_secret: str = ""
    oauth_naver_redirect_uri: str = (
        "http://localhost:5173/api/auth/oauth/naver/callback"
    )

    oauth_kakao_client_id: str = ""
    oauth_kakao_client_secret: str = ""
    oauth_kakao_redirect_uri: str = (
        "http://localhost:5173/api/auth/oauth/kakao/callback"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved_database_url(self) -> str:
        """SQLAlchemy·Alembic에서 사용할 최종 DB URL을 반환한다.

        `DATABASE_URL`이 있으면 우선 사용하고, 없으면 개별 DB_* 필드로 psycopg URL을 만든다.
        """
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
