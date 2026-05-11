"""ML 모델 API 응답 스키마."""

from datetime import datetime

from pydantic import BaseModel


class MlModelRecordResponse(BaseModel):
    id: int
    name: str
    version: str | None = None
    framework: str
    file_path: str
    created_at: datetime
