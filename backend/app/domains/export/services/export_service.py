"""Export job orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domains.export.exceptions import (
    ExportForbiddenError,
    ExportInvalidSplitError,
    ExportNotFoundError,
)
from app.domains.export.repositories.export_repository import ExportRepository
from app.domains.projects.repositories.project_repository import ProjectRepository
from app.tasks.export_tasks import run_export


@dataclass(frozen=True)
class ExportJobStatusDTO:
    id: int
    project_id: int
    dataset_version_id: int
    split_id: int
    format: str
    status: str
    export_path: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    download_url: str | None


class ExportService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._exports = ExportRepository(db)
        self._projects = ProjectRepository(db)

    def _membership_or_raise(self, project_id: int, user_id: int) -> None:
        if self._projects.get_membership(project_id, user_id) is None:
            raise ExportForbiddenError

    def create_export(
        self,
        *,
        project_id: int,
        user_id: int,
        dataset_version_id: int,
        dataset_split_id: int,
        export_format: str = "yolo",
    ) -> ExportJobStatusDTO:
        self._membership_or_raise(project_id, user_id)

        split = self._exports.get_split_with_version(
            project_id=project_id,
            split_id=dataset_split_id,
            dataset_version_id=dataset_version_id,
        )
        if split is None:
            raise ExportInvalidSplitError

        job = self._exports.create_job(
            project_id=project_id,
            dataset_version_id=dataset_version_id,
            split_id=dataset_split_id,
            requested_by=user_id,
            export_format=export_format,
        )
        self._db.commit()

        run_export.delay(job.id, project_id)

        return self._to_status_dto(job, download_url=None)

    def get_export(
        self,
        *,
        project_id: int,
        export_job_id: int,
        user_id: int,
        presign_download: bool = False,
    ) -> ExportJobStatusDTO:
        self._membership_or_raise(project_id, user_id)
        job = self._exports.get_job_for_project(project_id=project_id, job_id=export_job_id)
        if job is None:
            raise ExportNotFoundError

        download_url: str | None = None
        if presign_download and job.status == "completed" and job.export_path:
            from app.core.storage import StorageClient

            download_url = StorageClient().get_presigned_url(job.export_path)

        return self._to_status_dto(job, download_url=download_url)

    @staticmethod
    def _to_status_dto(job, download_url: str | None) -> ExportJobStatusDTO:  # noqa: ANN001
        return ExportJobStatusDTO(
            id=job.id,
            project_id=job.project_id,
            dataset_version_id=job.dataset_version_id,
            split_id=job.split_id,
            format=job.export_format,
            status=job.status,
            export_path=job.export_path,
            error_message=job.error_message,
            created_at=job.created_at,
            completed_at=job.completed_at,
            download_url=download_url,
        )
