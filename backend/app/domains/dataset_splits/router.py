"""Dataset split API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domains.dataset_splits.exceptions import (
    DatasetSplitForbiddenError,
    DatasetSplitInvalidRatiosError,
    DatasetSplitNotFoundError,
    DatasetSplitVersionNotFoundError,
)
from app.domains.dataset_splits.schemas.dtos import (
    CreateDatasetSplitBodyDTO,
    DatasetSplitDetailResponse,
    DatasetSplitPathDTO,
    DatasetVersionSplitsPathDTO,
    ProjectPathDTO,
)
from app.domains.dataset_splits.services.dataset_split_service import (
    DatasetSplitDetailDTO,
    DatasetSplitService,
)
from app.domains.oAuth.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/projects", tags=["dataset-splits"])


def project_path(project_id: Annotated[int, Path(ge=1)]) -> ProjectPathDTO:
    return ProjectPathDTO(project_id=project_id)


def split_path(
    project_id: Annotated[int, Path(ge=1)],
    dataset_split_id: Annotated[int, Path(ge=1)],
) -> DatasetSplitPathDTO:
    return DatasetSplitPathDTO(project_id=project_id, dataset_split_id=dataset_split_id)


def version_splits_path(
    project_id: Annotated[int, Path(ge=1)],
    dataset_version_id: Annotated[int, Path(ge=1)],
) -> DatasetVersionSplitsPathDTO:
    return DatasetVersionSplitsPathDTO(
        project_id=project_id,
        dataset_version_id=dataset_version_id,
    )


def get_dataset_split_service(db: Session = Depends(get_db)) -> DatasetSplitService:
    return DatasetSplitService(db)


def _to_response(dto: DatasetSplitDetailDTO) -> DatasetSplitDetailResponse:
    return DatasetSplitDetailResponse(
        id=dto.id,
        dataset_version_id=dto.dataset_version_id,
        name=dto.name,
        train_ratio=dto.train_ratio,
        val_ratio=dto.val_ratio,
        test_ratio=dto.test_ratio,
        random_seed=dto.random_seed,
        created_by=dto.created_by,
        created_at=dto.created_at,
        train_count=dto.train_count,
        val_count=dto.val_count,
        test_count=dto.test_count,
        total_count=dto.total_count,
    )


@router.post(
    "/{project_id}/dataset-splits",
    response_model=DatasetSplitDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dataset_split(
    path: ProjectPathDTO = Depends(project_path),
    body: CreateDatasetSplitBodyDTO = Body(...),
    user: User = Depends(get_current_user),
    svc: DatasetSplitService = Depends(get_dataset_split_service),
) -> DatasetSplitDetailResponse:
    try:
        result = svc.create_split(
            project_id=path.project_id,
            user_id=user.id,
            dataset_version_id=body.dataset_version_id,
            name=body.name,
            train_ratio=body.train_ratio,
            val_ratio=body.val_ratio,
            test_ratio=body.test_ratio,
            random_seed=body.random_seed,
        )
    except DatasetSplitForbiddenError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden") from None
    except DatasetSplitInvalidRatiosError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_split_ratios") from None
    except DatasetSplitVersionNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="dataset_version_not_found") from None
    return _to_response(result)


@router.get(
    "/{project_id}/dataset-versions/{dataset_version_id}/dataset-splits",
    response_model=list[DatasetSplitDetailResponse],
)
def list_dataset_splits(
    path: DatasetVersionSplitsPathDTO = Depends(version_splits_path),
    user: User = Depends(get_current_user),
    svc: DatasetSplitService = Depends(get_dataset_split_service),
) -> list[DatasetSplitDetailResponse]:
    try:
        rows = svc.list_splits_for_version(
            project_id=path.project_id,
            version_id=path.dataset_version_id,
            user_id=user.id,
        )
    except DatasetSplitForbiddenError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden") from None
    except DatasetSplitVersionNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="dataset_version_not_found") from None
    return [_to_response(r) for r in rows]


@router.get(
    "/{project_id}/dataset-splits/{dataset_split_id}",
    response_model=DatasetSplitDetailResponse,
)
def get_dataset_split(
    path: DatasetSplitPathDTO = Depends(split_path),
    user: User = Depends(get_current_user),
    svc: DatasetSplitService = Depends(get_dataset_split_service),
) -> DatasetSplitDetailResponse:
    try:
        result = svc.get_split(
            project_id=path.project_id,
            split_id=path.dataset_split_id,
            user_id=user.id,
        )
    except DatasetSplitForbiddenError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden") from None
    except DatasetSplitNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="dataset_split_not_found") from None
    return _to_response(result)
