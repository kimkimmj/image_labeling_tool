"""Dataset split API DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ProjectPathDTO(BaseModel):
    project_id: int = Field(..., ge=1)


class DatasetSplitPathDTO(BaseModel):
    project_id: int = Field(..., ge=1)
    dataset_split_id: int = Field(..., ge=1)


class DatasetVersionSplitsPathDTO(BaseModel):
    project_id: int = Field(..., ge=1)
    dataset_version_id: int = Field(..., ge=1)


class CreateDatasetSplitBodyDTO(BaseModel):
    dataset_version_id: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=200)
    train_ratio: float = Field(..., ge=0, le=100)
    val_ratio: float = Field(..., ge=0, le=100)
    test_ratio: float = Field(..., ge=0, le=100)
    random_seed: int = Field(0)

    @model_validator(mode="after")
    def ratios_sum_to_100(self) -> CreateDatasetSplitBodyDTO:
        total = self.train_ratio + self.val_ratio + self.test_ratio
        if abs(total - 100.0) > 1e-6:
            raise ValueError("train_ratio + val_ratio + test_ratio must equal 100")
        return self


class DatasetSplitDetailResponse(BaseModel):
    id: int
    dataset_version_id: int
    name: str
    train_ratio: float
    val_ratio: float
    test_ratio: float
    random_seed: int
    created_by: int
    created_at: datetime
    train_count: int
    val_count: int
    test_count: int
    total_count: int
