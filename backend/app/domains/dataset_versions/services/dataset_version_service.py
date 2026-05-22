"""Dataset version (freeze snapshot) business logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.dataset_versions.exceptions import (
    DatasetVersionDuplicateNameError,
    DatasetVersionForbiddenError,
    DatasetVersionNotFoundError,
)
from app.domains.dataset_versions.repositories.dataset_version_repository import (
    DatasetVersionRepository,
)
from app.domains.projects.repositories.project_repository import ProjectRepository
from app.models import DatasetItem, DatasetVersion


@dataclass(frozen=True)
class DatasetVersionSummaryDTO:
    id: int
    project_id: int
    name: str
    description: str | None
    created_by: int
    created_at: datetime
    item_count: int


@dataclass(frozen=True)
class DatasetItemDTO:
    id: int
    image_id: int
    assignment_id: int
    created_at: datetime


@dataclass(frozen=True)
class DatasetVersionDetailDTO:
    id: int
    project_id: int
    name: str
    description: str | None
    created_by: int
    created_at: datetime
    items: list[DatasetItemDTO]


class DatasetVersionService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._versions = DatasetVersionRepository(db)
        self._projects = ProjectRepository(db)

    def _membership_or_raise(self, project_id: int, user_id: int) -> None:
        if self._projects.get_membership(project_id, user_id) is None:
            raise DatasetVersionForbiddenError

    @staticmethod
    def _to_summary(row: DatasetVersion, item_count: int) -> DatasetVersionSummaryDTO:
        return DatasetVersionSummaryDTO(
            id=row.id,
            project_id=row.project_id,
            name=row.name,
            description=row.description,
            created_by=row.created_by,
            created_at=row.created_at,
            item_count=item_count,
        )

    @staticmethod
    def _to_detail(row: DatasetVersion) -> DatasetVersionDetailDTO:
        items = [
            DatasetItemDTO(
                id=item.id,
                image_id=item.image_id,
                assignment_id=item.assignment_id,
                created_at=item.created_at,
            )
            for item in sorted(row.items, key=lambda i: i.id)
        ]
        return DatasetVersionDetailDTO(
            id=row.id,
            project_id=row.project_id,
            name=row.name,
            description=row.description,
            created_by=row.created_by,
            created_at=row.created_at,
            items=items,
        )

    def create_version(
        self,
        *,
        project_id: int,
        user_id: int,
        name: str,
        description: str | None,
    ) -> DatasetVersionDetailDTO:
        self._membership_or_raise(project_id, user_id)
        approved = self._versions.list_approved_assignments_for_project(project_id)
        pairs = [(a.image_id, a.id) for a in approved]

        try:
            version = self._versions.create_version(
                project_id=project_id,
                name=name,
                description=description,
                created_by=user_id,
            )
            if pairs:
                self._versions.bulk_create_items(
                    dataset_version_id=version.id,
                    pairs=pairs,
                )
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise DatasetVersionDuplicateNameError from exc

        row = self._versions.get_version_with_items(
            project_id=project_id,
            version_id=version.id,
        )
        assert row is not None
        return self._to_detail(row)

    def list_versions(self, *, project_id: int, user_id: int) -> list[DatasetVersionSummaryDTO]:
        self._membership_or_raise(project_id, user_id)
        rows = self._versions.list_versions_with_item_counts(project_id)
        return [self._to_summary(v, int(count)) for v, count in rows]

    def get_version(
        self,
        *,
        project_id: int,
        version_id: int,
        user_id: int,
    ) -> DatasetVersionDetailDTO:
        self._membership_or_raise(project_id, user_id)
        row = self._versions.get_version_with_items(
            project_id=project_id,
            version_id=version_id,
        )
        if row is None:
            raise DatasetVersionNotFoundError
        return self._to_detail(row)
