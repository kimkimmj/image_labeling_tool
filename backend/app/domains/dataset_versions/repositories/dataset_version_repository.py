"""Dataset version and item DB access."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import DatasetItem, DatasetVersion, Image, ImageAssignment


class DatasetVersionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_version(
        self,
        *,
        project_id: int,
        name: str,
        description: str | None,
        created_by: int,
    ) -> DatasetVersion:
        row = DatasetVersion(
            project_id=project_id,
            name=name,
            description=description,
            created_by=created_by,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get_version(self, version_id: int) -> DatasetVersion | None:
        return self._session.get(DatasetVersion, version_id)

    def get_version_for_project(
        self,
        *,
        project_id: int,
        version_id: int,
    ) -> DatasetVersion | None:
        stmt = select(DatasetVersion).where(
            DatasetVersion.id == version_id,
            DatasetVersion.project_id == project_id,
        )
        return self._session.scalar(stmt)

    def get_version_with_items(
        self,
        *,
        project_id: int,
        version_id: int,
    ) -> DatasetVersion | None:
        stmt = (
            select(DatasetVersion)
            .options(joinedload(DatasetVersion.items))
            .where(
                DatasetVersion.id == version_id,
                DatasetVersion.project_id == project_id,
            )
        )
        return self._session.scalar(stmt)

    def list_versions_with_item_counts(self, project_id: int) -> list[tuple[DatasetVersion, int]]:
        item_count = func.count(DatasetItem.id).label("item_count")
        stmt = (
            select(DatasetVersion, item_count)
            .outerjoin(DatasetItem, DatasetItem.dataset_version_id == DatasetVersion.id)
            .where(DatasetVersion.project_id == project_id)
            .group_by(DatasetVersion.id)
            .order_by(DatasetVersion.created_at.desc())
        )
        return list(self._session.execute(stmt).all())

    def list_approved_assignments_for_project(self, project_id: int) -> list[ImageAssignment]:
        stmt = (
            select(ImageAssignment)
            .join(Image, Image.id == ImageAssignment.image_id)
            .where(
                Image.project_id == project_id,
                ImageAssignment.status == "approved",
            )
        )
        return list(self._session.scalars(stmt).all())

    def bulk_create_items(
        self,
        *,
        dataset_version_id: int,
        pairs: list[tuple[int, int]],
    ) -> list[DatasetItem]:
        rows = [
            DatasetItem(
                dataset_version_id=dataset_version_id,
                image_id=image_id,
                assignment_id=assignment_id,
            )
            for image_id, assignment_id in pairs
        ]
        self._session.add_all(rows)
        self._session.flush()
        return rows
