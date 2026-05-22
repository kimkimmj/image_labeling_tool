"""Dataset version (freeze) API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domains.dataset_versions.exceptions import (
    DatasetVersionDuplicateNameError,
    DatasetVersionForbiddenError,
    DatasetVersionNotFoundError,
)
from app.domains.dataset_versions.schemas.dtos import (
    CreateDatasetVersionBodyDTO,
    DatasetItemResponse,
    DatasetVersionDetailResponse,
    DatasetVersionPathDTO,
    DatasetVersionSummaryResponse,
    ProjectPathDTO,
)
from app.domains.dataset_versions.services.dataset_version_service import (
    DatasetVersionDetailDTO,
    DatasetVersionService,
    DatasetVersionSummaryDTO,
)
from app.domains.oAuth.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/projects", tags=["dataset-versions"])


def project_path(project_id: Annotated[int, Path(ge=1)]) -> ProjectPathDTO:
    return ProjectPathDTO(project_id=project_id)


def version_path(
    project_id: Annotated[int, Path(ge=1)],
    dataset_version_id: Annotated[int, Path(ge=1)],
) -> DatasetVersionPathDTO:
    return DatasetVersionPathDTO(
        project_id=project_id,
        dataset_version_id=dataset_version_id,
    )


def get_dataset_version_service(db: Session = Depends(get_db)) -> DatasetVersionService:
    return DatasetVersionService(db)


def _summary_to_response(dto: DatasetVersionSummaryDTO) -> DatasetVersionSummaryResponse:
    return DatasetVersionSummaryResponse(
        id=dto.id,
        project_id=dto.project_id,
        name=dto.name,
        description=dto.description,
        created_by=dto.created_by,
        created_at=dto.created_at,
        item_count=dto.item_count,
    )


def _detail_to_response(dto: DatasetVersionDetailDTO) -> DatasetVersionDetailResponse:
    return DatasetVersionDetailResponse(
        id=dto.id,
        project_id=dto.project_id,
        name=dto.name,
        description=dto.description,
        created_by=dto.created_by,
        created_at=dto.created_at,
        items=[
            DatasetItemResponse(
                id=i.id,
                image_id=i.image_id,
                assignment_id=i.assignment_id,
                created_at=i.created_at,
            )
            for i in dto.items
        ],
    )


@router.post(
    "/{project_id}/dataset-versions",
    response_model=DatasetVersionDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dataset_version(
    path: ProjectPathDTO = Depends(project_path),
    body: CreateDatasetVersionBodyDTO = Body(...),
    user: User = Depends(get_current_user),
    svc: DatasetVersionService = Depends(get_dataset_version_service),
) -> DatasetVersionDetailResponse:
    try:
        result = svc.create_version(
            project_id=path.project_id,
            user_id=user.id,
            name=body.name,
            description=body.description,
        )
    except DatasetVersionForbiddenError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden") from None
    except DatasetVersionDuplicateNameError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="dataset_version_name_exists",
        ) from None
    return _detail_to_response(result)


@router.get(
    "/{project_id}/dataset-versions",
    response_model=list[DatasetVersionSummaryResponse],
)
def list_dataset_versions(
    path: ProjectPathDTO = Depends(project_path),
    user: User = Depends(get_current_user),
    svc: DatasetVersionService = Depends(get_dataset_version_service),
) -> list[DatasetVersionSummaryResponse]:
    try:
        rows = svc.list_versions(project_id=path.project_id, user_id=user.id)
    except DatasetVersionForbiddenError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden") from None
    return [_summary_to_response(r) for r in rows]


@router.get(
    "/{project_id}/dataset-versions/{dataset_version_id}",
    response_model=DatasetVersionDetailResponse,
)
def get_dataset_version(
    path: DatasetVersionPathDTO = Depends(version_path),
    user: User = Depends(get_current_user),
    svc: DatasetVersionService = Depends(get_dataset_version_service),
) -> DatasetVersionDetailResponse:
    try:
        result = svc.get_version(
            project_id=path.project_id,
            version_id=path.dataset_version_id,
            user_id=user.id,
        )
    except DatasetVersionForbiddenError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden") from None
    except DatasetVersionNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="dataset_version_not_found") from None
    return _detail_to_response(result)
