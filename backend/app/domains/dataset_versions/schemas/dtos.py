"""Dataset version API DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectPathDTO(BaseModel):
    project_id: int = Field(..., ge=1)


class DatasetVersionPathDTO(BaseModel):
    project_id: int = Field(..., ge=1)
    dataset_version_id: int = Field(..., ge=1)


class CreateDatasetVersionBodyDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)


class DatasetItemResponse(BaseModel):
    id: int
    image_id: int
    assignment_id: int
    created_at: datetime


class DatasetVersionSummaryResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: str | None
    created_by: int
    created_at: datetime
    item_count: int


class DatasetVersionDetailResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: str | None
    created_by: int
    created_at: datetime
    items: list[DatasetItemResponse]
