"""클래스 관리·모델 선택 유스케이스."""

from __future__ import annotations

import colorsys
import random
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.storage import StorageClient
from app.domains.projects.exceptions import (
    ClassDuplicateNameError,
    ClassHardDeleteNotAllowedError,
    ClassHasAnnotationsError,
    ClassNotFoundError,
    ModelForbiddenError,
    ModelNotFoundError,
    ProjectForbiddenError,
    ProjectNotFoundError,
)
from app.domains.projects.repositories.class_repository import ClassRepository
from app.domains.projects.repositories.project_repository import ProjectRepository
from app.models.enums import ProjectRole


@dataclass(frozen=True)
class MlModelDTO:
    id: int
    name: str
    version: str | None
    framework: str
    file_path: str
    created_at: datetime


@dataclass(frozen=True)
class ProjectClassDTO:
    id: int
    project_id: int
    export_index: int
    name: str
    color: str | None
    is_active: bool
    model_class_id: int | None
    created_at: datetime


def _random_hex_colors(count: int) -> list[str]:
    """모델에서 일괄 import되는 클래스마다 구분되는 색상 (#rrggbb).

    Hue는 황금각으로 퍼 뜨리고, 채도·명도는 랜덤으로 둔다.
    """
    if count <= 0:
        return []
    rng = random.Random()
    golden = 0.3819660112501051  # (sqrt(5) - 1) / 2
    out: list[str] = []
    for i in range(count):
        h = (i * golden + rng.uniform(0, 0.07)) % 1.0
        s = rng.uniform(0.52, 0.92)
        v = rng.uniform(0.74, 0.98)
        r_f, g_f, b_f = colorsys.hsv_to_rgb(h, s, v)
        out.append(f"#{int(r_f * 255):02x}{int(g_f * 255):02x}{int(b_f * 255):02x}")
    return out


class ClassService:
    def __init__(self, db: Session, storage: StorageClient) -> None:
        self._db = db
        self._projects = ProjectRepository(db)
        self._classes = ClassRepository(db)
        self._storage = storage

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _require_owner(self, project_id: int, user_id: int) -> None:
        m = self._projects.get_membership(project_id, user_id)
        if m is None:
            raise ProjectNotFoundError
        if m.role != ProjectRole.owner.value:
            raise ProjectForbiddenError

    # ------------------------------------------------------------------
    # 모델 목록 조회 (프로젝트 owner 소유 모델)
    # ------------------------------------------------------------------

    def list_available_models(self, *, project_id: int, user_id: int) -> list[MlModelDTO]:
        """프로젝트 멤버는 owner가 소유한 ML 모델만 볼 수 있다."""
        m = self._projects.get_membership(project_id, user_id)
        if m is None:
            raise ProjectNotFoundError
        project_owner_id = self._projects.get_owner_user_id(project_id)
        if project_owner_id is None:
            raise ProjectNotFoundError
        rows = self._classes.list_models_for_owner(project_owner_id)
        return [_to_model_dto(r) for r in rows]

    def get_selected_model(self, *, project_id: int, user_id: int) -> MlModelDTO | None:
        """프로젝트에 현재 선택된 모델을 반환한다. 없으면 None."""
        m = self._projects.get_membership(project_id, user_id)
        if m is None:
            raise ProjectNotFoundError
        row = self._classes.get_selected_model(project_id)
        if row is None:
            return None
        return _to_model_dto(row)

    # ------------------------------------------------------------------
    # 모델 선택 (owner 전용)
    # ------------------------------------------------------------------

    def select_model(
        self,
        *,
        project_id: int,
        model_id: int,
        owner_user_id: int,
    ) -> MlModelDTO:
        """프로젝트 owner 소유 모델 중 하나를 연결하고 project_classes를 자동 import한다.

        - 기존 selected_model_id만 변경
        - 기존 project_classes의 model_class_id는 ON DELETE SET NULL로 처리됨
        - 새 모델의 클래스는 비충돌 항목만 import
        """
        self._require_owner(project_id, owner_user_id)

        ml_model = self._classes.get_model(model_id)
        if ml_model is None:
            raise ModelNotFoundError

        project_owner_id = self._projects.get_owner_user_id(project_id)
        if project_owner_id is None:
            raise ProjectNotFoundError
        if ml_model.owner_id != project_owner_id:
            raise ModelForbiddenError

        model_classes = self._classes.list_model_classes(model_id)

        taken_indices = self._classes.get_taken_export_indices(project_id)
        taken_names = self._classes.get_taken_names(project_id)
        entries_core = [
            (mc.class_index, mc.name, mc.id)
            for mc in sorted(model_classes, key=lambda x: x.class_index)
            if mc.class_index not in taken_indices and mc.name not in taken_names
        ]
        if entries_core:
            colors = _random_hex_colors(len(entries_core))
            entries = [
                (idx, name, mc_id, colors[i])
                for i, (idx, name, mc_id) in enumerate(entries_core)
            ]
            self._classes.bulk_create_project_classes(
                project_id=project_id,
                created_by=owner_user_id,
                entries=entries,
            )

        self._classes.update_project_model(project_id, model_id)

        self._db.commit()
        self._db.refresh(ml_model)
        return _to_model_dto(ml_model)

    # ------------------------------------------------------------------
    # project_classes CRUD
    # ------------------------------------------------------------------

    def list_classes(self, *, project_id: int, user_id: int, include_inactive: bool = False) -> list[ProjectClassDTO]:
        m = self._projects.get_membership(project_id, user_id)
        if m is None:
            raise ProjectNotFoundError
        if include_inactive and m.role != ProjectRole.owner.value:
            raise ProjectForbiddenError
        rows = self._classes.list_project_classes(project_id, include_inactive=include_inactive)
        return [_to_class_dto(r) for r in rows]

    def add_class(
        self,
        *,
        project_id: int,
        owner_user_id: int,
        name: str,
        color: str | None,
    ) -> ProjectClassDTO:
        self._require_owner(project_id, owner_user_id)

        if self._classes.name_exists(project_id, name):
            raise ClassDuplicateNameError(name)

        row = self._classes.create_project_class(
            project_id=project_id,
            name=name,
            color=color,
            created_by=owner_user_id,
        )
        self._db.commit()
        self._db.refresh(row)
        return _to_class_dto(row)

    def rename_class(
        self,
        *,
        class_id: int,
        owner_user_id: int,
        name: str | None,
        color: str | None,
        is_active: bool | None = None,
        _sentinel: object = None,  # 변경 필드 구분용
    ) -> ProjectClassDTO:
        row = self._classes.get_project_class(class_id)
        if row is None:
            raise ClassNotFoundError
        self._require_owner(row.project_id, owner_user_id)

        if name is not None and name != row.name:
            if self._classes.name_exists(row.project_id, name, exclude_class_id=class_id):
                raise ClassDuplicateNameError(name)
            row.name = name

        if color is not None:
            row.color = color

        if is_active is not None:
            row.is_active = is_active

        self._db.commit()
        self._db.refresh(row)
        return _to_class_dto(row)

    def deactivate_class(self, *, class_id: int, owner_user_id: int) -> ProjectClassDTO:
        """soft delete: is_active = False."""
        row = self._classes.get_project_class(class_id)
        if row is None:
            raise ClassNotFoundError
        self._require_owner(row.project_id, owner_user_id)
        row.is_active = False
        self._db.commit()
        self._db.refresh(row)
        return _to_class_dto(row)

    def delete_class_permanent(self, *, class_id: int, owner_user_id: int) -> None:
        """owner 전용: 수동 추가 클래스(model_class_id 없음)만 project_classes 행을 제거한다.

        모델 연동 클래스는 비활성화만 가능. 어노테이션이 하나라도 있으면 FK 때문에 제거하지 않는다.
        """
        row = self._classes.get_project_class(class_id)
        if row is None:
            raise ClassNotFoundError
        self._require_owner(row.project_id, owner_user_id)
        if row.model_class_id is not None:
            raise ClassHardDeleteNotAllowedError
        if self._classes.count_annotations_for_class(class_id) > 0:
            raise ClassHasAnnotationsError
        self._classes.delete_project_class_row(class_id)
        self._db.commit()


def _to_model_dto(row: object) -> MlModelDTO:
    from app.models.ml_model import MlModel  # 순환 import 방지
    r: MlModel = row  # type: ignore[assignment]
    return MlModelDTO(
        id=r.id,
        name=r.name,
        version=r.version,
        framework=r.framework,
        file_path=r.file_path,
        created_at=r.created_at,
    )


def _to_class_dto(row: object) -> ProjectClassDTO:
    from app.models.ml_model import ProjectClass  # 순환 import 방지
    r: ProjectClass = row  # type: ignore[assignment]
    return ProjectClassDTO(
        id=r.id,
        project_id=r.project_id,
        export_index=r.export_index,
        name=r.name,
        color=r.color,
        is_active=r.is_active,
        model_class_id=r.model_class_id,
        created_at=r.created_at,
    )
