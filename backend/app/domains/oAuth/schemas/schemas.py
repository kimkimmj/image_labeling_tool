from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MeResponse(BaseModel):
    """현재 로그인 사용자 API 응답 DTO."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime
