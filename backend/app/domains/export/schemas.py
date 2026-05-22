"""Export API DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ExportFormat = Literal["yolo", "coco"]


class ProjectPathDTO(BaseModel):
    project_id: int = Field(..., ge=1)


class ExportJobPathDTO(BaseModel):
    project_id: int = Field(..., ge=1)
    export_job_id: int = Field(..., ge=1)


class CreateExportBodyDTO(BaseModel):
    dataset_version_id: int = Field(..., ge=1)
    dataset_split_id: int = Field(..., ge=1)
    format: ExportFormat = Field("yolo", description="Export dataset format: yolo or coco")


class ExportJobResponse(BaseModel):
    id: int
    project_id: int
    dataset_version_id: int
    split_id: int
    format: ExportFormat
    status: str
    export_path: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    download_url: str | None
