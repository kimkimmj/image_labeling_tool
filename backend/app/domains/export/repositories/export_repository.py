"""Export job DB access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Annotation,
    DatasetItem,
    DatasetSplit,
    DatasetVersion,
    ExportJob,
    Image,
    ProjectClass,
    SplitItem,
)


@dataclass(frozen=True)
class ExportSplitRow:
    split_type: str
    image_id: int
    assignment_id: int
    file_name: str
    file_path: str
    width: int
    height: int


@dataclass(frozen=True)
class ExportAnnotationRow:
    assignment_id: int
    export_index: int
    x: float
    y: float
    width: float
    height: float


class ExportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_job(
        self,
        *,
        project_id: int,
        dataset_version_id: int,
        split_id: int,
        requested_by: int,
        export_format: str = "yolo",
    ) -> ExportJob:
        job = ExportJob(
            project_id=project_id,
            dataset_version_id=dataset_version_id,
            split_id=split_id,
            requested_by=requested_by,
            status="pending",
            export_format=export_format,
        )
        self._session.add(job)
        self._session.flush()
        return job

    def get_job_for_project(self, *, project_id: int, job_id: int) -> ExportJob | None:
        stmt = select(ExportJob).where(
            ExportJob.id == job_id,
            ExportJob.project_id == project_id,
        )
        return self._session.scalar(stmt)

    def update_job_status(
        self,
        job_id: int,
        *,
        status: str,
        export_path: str | None = None,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        job = self._session.get(ExportJob, job_id)
        if job is None:
            return
        job.status = status
        if export_path is not None:
            job.export_path = export_path
        if error_message is not None:
            job.error_message = error_message
        if completed_at is not None:
            job.completed_at = completed_at
        self._session.flush()

    def get_split_with_version(
        self,
        *,
        project_id: int,
        split_id: int,
        dataset_version_id: int,
    ) -> DatasetSplit | None:
        stmt = (
            select(DatasetSplit)
            .join(DatasetVersion, DatasetVersion.id == DatasetSplit.dataset_version_id)
            .where(
                DatasetSplit.id == split_id,
                DatasetSplit.dataset_version_id == dataset_version_id,
                DatasetVersion.project_id == project_id,
            )
        )
        return self._session.scalar(stmt)

    def list_split_export_rows(self, split_id: int) -> list[ExportSplitRow]:
        stmt = (
            select(
                SplitItem.split_type,
                DatasetItem.image_id,
                DatasetItem.assignment_id,
                Image.file_name,
                Image.file_path,
                Image.width,
                Image.height,
            )
            .join(DatasetItem, DatasetItem.id == SplitItem.dataset_item_id)
            .join(Image, Image.id == DatasetItem.image_id)
            .where(SplitItem.split_id == split_id)
            .order_by(SplitItem.id.asc())
        )
        return [
            ExportSplitRow(
                split_type=row[0],
                image_id=row[1],
                assignment_id=row[2],
                file_name=row[3],
                file_path=row[4],
                width=row[5],
                height=row[6],
            )
            for row in self._session.execute(stmt).all()
        ]

    def list_annotations_for_assignments(
        self,
        assignment_ids: list[int],
    ) -> list[ExportAnnotationRow]:
        if not assignment_ids:
            return []
        stmt = (
            select(
                Annotation.assignment_id,
                ProjectClass.export_index,
                Annotation.x,
                Annotation.y,
                Annotation.width,
                Annotation.height,
            )
            .join(ProjectClass, ProjectClass.id == Annotation.class_id)
            .where(
                Annotation.assignment_id.in_(assignment_ids),
                Annotation.is_deleted.is_(False),
                ProjectClass.is_active.is_(True),
            )
        )
        return [
            ExportAnnotationRow(
                assignment_id=row[0],
                export_index=row[1],
                x=row[2],
                y=row[3],
                width=row[4],
                height=row[5],
            )
            for row in self._session.execute(stmt).all()
        ]

    def list_active_project_classes(self, project_id: int) -> list[ProjectClass]:
        stmt = (
            select(ProjectClass)
            .where(
                ProjectClass.project_id == project_id,
                ProjectClass.is_active.is_(True),
            )
            .order_by(ProjectClass.export_index.asc())
        )
        return list(self._session.scalars(stmt).all())
