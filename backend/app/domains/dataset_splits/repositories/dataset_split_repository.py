"""Dataset split DB access."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DatasetItem, DatasetSplit, DatasetVersion, SplitItem


class DatasetSplitRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

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

    def list_item_ids_for_version(self, dataset_version_id: int) -> list[int]:
        stmt = (
            select(DatasetItem.id)
            .where(DatasetItem.dataset_version_id == dataset_version_id)
            .order_by(DatasetItem.id.asc())
        )
        return list(self._session.scalars(stmt).all())

    def create_split(
        self,
        *,
        dataset_version_id: int,
        name: str,
        train_ratio: float,
        val_ratio: float,
        test_ratio: float,
        random_seed: int,
        created_by: int,
    ) -> DatasetSplit:
        row = DatasetSplit(
            dataset_version_id=dataset_version_id,
            name=name,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            random_seed=random_seed,
            created_by=created_by,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def bulk_create_split_items(
        self,
        *,
        split_id: int,
        assignments: list[tuple[int, str]],
    ) -> None:
        rows = [
            SplitItem(
                split_id=split_id,
                dataset_item_id=dataset_item_id,
                split_type=split_type,
            )
            for dataset_item_id, split_type in assignments
        ]
        self._session.add_all(rows)
        self._session.flush()

    def list_splits_for_version(
        self,
        *,
        project_id: int,
        version_id: int,
    ) -> list[DatasetSplit]:
        stmt = (
            select(DatasetSplit)
            .join(DatasetVersion, DatasetVersion.id == DatasetSplit.dataset_version_id)
            .where(
                DatasetSplit.dataset_version_id == version_id,
                DatasetVersion.project_id == project_id,
            )
            .order_by(DatasetSplit.created_at.desc())
        )
        return list(self._session.scalars(stmt).all())

    def get_split_for_project(
        self,
        *,
        project_id: int,
        split_id: int,
    ) -> DatasetSplit | None:
        stmt = (
            select(DatasetSplit)
            .join(DatasetVersion, DatasetVersion.id == DatasetSplit.dataset_version_id)
            .where(
                DatasetSplit.id == split_id,
                DatasetVersion.project_id == project_id,
            )
        )
        return self._session.scalar(stmt)

    def count_split_items_by_type(self, split_id: int) -> dict[str, int]:
        stmt = (
            select(SplitItem.split_type, func.count(SplitItem.id))
            .where(SplitItem.split_id == split_id)
            .group_by(SplitItem.split_type)
        )
        rows = self._session.execute(stmt).all()
        counts = {"train": 0, "val": 0, "test": 0}
        for split_type, count in rows:
            counts[split_type] = int(count)
        return counts
