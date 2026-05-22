"""Dataset split business logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.split_algorithm import compute_split_assignments
from app.domains.dataset_splits.exceptions import (
    DatasetSplitForbiddenError,
    DatasetSplitInvalidRatiosError,
    DatasetSplitNotFoundError,
    DatasetSplitVersionNotFoundError,
)
from app.domains.dataset_splits.repositories.dataset_split_repository import (
    DatasetSplitRepository,
)
from app.domains.projects.repositories.project_repository import ProjectRepository


@dataclass(frozen=True)
class DatasetSplitDetailDTO:
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


class DatasetSplitService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._splits = DatasetSplitRepository(db)
        self._projects = ProjectRepository(db)

    def _membership_or_raise(self, project_id: int, user_id: int) -> None:
        if self._projects.get_membership(project_id, user_id) is None:
            raise DatasetSplitForbiddenError

    @staticmethod
    def _validate_ratios(train_ratio: float, val_ratio: float, test_ratio: float) -> None:
        total = train_ratio + val_ratio + test_ratio
        if abs(total - 100.0) > 1e-6:
            raise DatasetSplitInvalidRatiosError
        for r in (train_ratio, val_ratio, test_ratio):
            if r < 0:
                raise DatasetSplitInvalidRatiosError

    def create_split(
        self,
        *,
        project_id: int,
        user_id: int,
        dataset_version_id: int,
        name: str,
        train_ratio: float,
        val_ratio: float,
        test_ratio: float,
        random_seed: int,
    ) -> DatasetSplitDetailDTO:
        self._membership_or_raise(project_id, user_id)
        self._validate_ratios(train_ratio, val_ratio, test_ratio)

        version = self._splits.get_version_for_project(
            project_id=project_id,
            version_id=dataset_version_id,
        )
        if version is None:
            raise DatasetSplitVersionNotFoundError

        item_ids = self._splits.list_item_ids_for_version(dataset_version_id)
        assignments = compute_split_assignments(
            item_ids,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            random_seed=random_seed,
        )

        split = self._splits.create_split(
            dataset_version_id=dataset_version_id,
            name=name,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            random_seed=random_seed,
            created_by=user_id,
        )
        if assignments:
            self._splits.bulk_create_split_items(
                split_id=split.id,
                assignments=assignments,
            )
        self._db.commit()

        return self.get_split(
            project_id=project_id,
            split_id=split.id,
            user_id=user_id,
        )

    def list_splits_for_version(
        self,
        *,
        project_id: int,
        version_id: int,
        user_id: int,
    ) -> list[DatasetSplitDetailDTO]:
        self._membership_or_raise(project_id, user_id)
        version = self._splits.get_version_for_project(
            project_id=project_id,
            version_id=version_id,
        )
        if version is None:
            raise DatasetSplitVersionNotFoundError

        rows = self._splits.list_splits_for_version(
            project_id=project_id,
            version_id=version_id,
        )
        return [
            self._split_to_detail(split, project_id=project_id, user_id=user_id)
            for split in rows
        ]

    def _split_to_detail(
        self,
        split,
        *,
        project_id: int,
        user_id: int,
    ) -> DatasetSplitDetailDTO:  # noqa: ANN001
        counts = self._splits.count_split_items_by_type(split.id)
        total = counts["train"] + counts["val"] + counts["test"]
        return DatasetSplitDetailDTO(
            id=split.id,
            dataset_version_id=split.dataset_version_id,
            name=split.name,
            train_ratio=split.train_ratio,
            val_ratio=split.val_ratio,
            test_ratio=split.test_ratio,
            random_seed=split.random_seed,
            created_by=split.created_by,
            created_at=split.created_at,
            train_count=counts["train"],
            val_count=counts["val"],
            test_count=counts["test"],
            total_count=total,
        )

    def get_split(
        self,
        *,
        project_id: int,
        split_id: int,
        user_id: int,
    ) -> DatasetSplitDetailDTO:
        self._membership_or_raise(project_id, user_id)
        split = self._splits.get_split_for_project(project_id=project_id, split_id=split_id)
        if split is None:
            raise DatasetSplitNotFoundError

        return self._split_to_detail(split, project_id=project_id, user_id=user_id)
