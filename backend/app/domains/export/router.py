"""Export (YOLO ZIP) API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domains.export.exceptions import (
    ExportForbiddenError,
    ExportInvalidSplitError,
    ExportNotFoundError,
)
from app.domains.export.schemas import (
    CreateExportBodyDTO,
    ExportJobPathDTO,
    ExportJobResponse,
    ProjectPathDTO,
)
from app.domains.export.services.export_service import ExportJobStatusDTO, ExportService
from app.domains.oAuth.deps import get_current_user
from app.models import User

export_router = APIRouter(prefix="/projects", tags=["export"])


def project_path(project_id: Annotated[int, Path(ge=1)]) -> ProjectPathDTO:
    return ProjectPathDTO(project_id=project_id)


def export_job_path(
    project_id: Annotated[int, Path(ge=1)],
    export_job_id: Annotated[int, Path(ge=1)],
) -> ExportJobPathDTO:
    return ExportJobPathDTO(project_id=project_id, export_job_id=export_job_id)


def get_export_service(db: Session = Depends(get_db)) -> ExportService:
    return ExportService(db)


def _to_response(dto: ExportJobStatusDTO) -> ExportJobResponse:
    return ExportJobResponse(
        id=dto.id,
        project_id=dto.project_id,
        dataset_version_id=dto.dataset_version_id,
        split_id=dto.split_id,
        format=dto.format,
        status=dto.status,
        export_path=dto.export_path,
        error_message=dto.error_message,
        created_at=dto.created_at,
        completed_at=dto.completed_at,
        download_url=dto.download_url,
    )


@export_router.post(
    "/{project_id}/exports",
    response_model=ExportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_export(
    path: ProjectPathDTO = Depends(project_path),
    body: CreateExportBodyDTO = Body(...),
    user: User = Depends(get_current_user),
    svc: ExportService = Depends(get_export_service),
) -> ExportJobResponse:
    try:
        result = svc.create_export(
            project_id=path.project_id,
            user_id=user.id,
            dataset_version_id=body.dataset_version_id,
            dataset_split_id=body.dataset_split_id,
            export_format=body.format,
        )
    except ExportForbiddenError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden") from None
    except ExportInvalidSplitError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_split_or_version") from None
    return _to_response(result)


@export_router.get(
    "/{project_id}/exports/{export_job_id}",
    response_model=ExportJobResponse,
)
def get_export_status(
    path: ExportJobPathDTO = Depends(export_job_path),
    user: User = Depends(get_current_user),
    svc: ExportService = Depends(get_export_service),
) -> ExportJobResponse:
    try:
        result = svc.get_export(
            project_id=path.project_id,
            export_job_id=path.export_job_id,
            user_id=user.id,
            presign_download=True,
        )
    except ExportForbiddenError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden") from None
    except ExportNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="export_job_not_found") from None
    return _to_response(result)
