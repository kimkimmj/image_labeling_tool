"""Export 도메인 스키마."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    """YOLO 포맷 export 요청."""

    project_id: int = Field(..., ge=1)
    format: str = Field("yolo_v8", pattern=r"^(yolo_v8|coco)$")
    include_unapproved: bool = False


class ExportStatusResponse(BaseModel):
    export_job_id: str
    status: str
    download_url: str | None = None
    error: str | None = None
