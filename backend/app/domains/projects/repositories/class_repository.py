"""ml_models / model_classes / project_classes DB 접근."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.ml_model import MlModel, ModelClass, ProjectClass
from app.models.project import Project
from app.models.upload import Annotation


class ClassRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # MlModel
    # ------------------------------------------------------------------

    def create_model(
        self,
        *,
        owner_id: int,
        name: str,
        version: str | None,
        framework: str,
        file_path: str,
    ) -> MlModel:
        row = MlModel(
            owner_id=owner_id,
            name=name,
            version=version,
            framework=framework,
            file_path=file_path,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get_model(self, model_id: int) -> MlModel | None:
        return self._session.get(MlModel, model_id)

    def get_selected_model(self, project_id: int) -> MlModel | None:
        """프로젝트에 현재 연결된 모델을 반환한다. 없으면 None."""
        project = self._session.get(Project, project_id)
        if project is None or project.selected_model_id is None:
            return None
        return self._session.get(MlModel, project.selected_model_id)

    def delete_model(self, model_id: int) -> None:
        """ml_models 행을 삭제한다. model_classes 는 CASCADE 로 제거된다."""
        model = self._session.get(MlModel, model_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    def list_all_models(self) -> list[MlModel]:
        """시스템에 등록된 전체 ML 모델을 최신순으로 반환한다."""
        stmt = select(MlModel).order_by(MlModel.created_at.desc())
        return list(self._session.scalars(stmt).all())

    def list_models_for_owner(self, owner_id: int) -> list[MlModel]:
        """특정 사용자가 소유한 ML 모델을 최신순으로 반환한다."""
        stmt = (
            select(MlModel)
            .where(MlModel.owner_id == owner_id)
            .order_by(MlModel.created_at.desc())
        )
        return list(self._session.scalars(stmt).all())

    def update_project_model(self, project_id: int, model_id: int | None) -> None:
        project = self._session.get(Project, project_id)
        if project is not None:
            project.selected_model_id = model_id
            self._session.flush()

    # ------------------------------------------------------------------
    # ModelClass
    # ------------------------------------------------------------------

    def bulk_create_model_classes(
        self, model_id: int, class_names: dict[int, str]
    ) -> list[ModelClass]:
        rows = [
            ModelClass(model_id=model_id, class_index=idx, name=name)
            for idx, name in sorted(class_names.items())
        ]
        self._session.add_all(rows)
        self._session.flush()
        return rows

    def list_model_classes(self, model_id: int) -> list[ModelClass]:
        stmt = (
            select(ModelClass)
            .where(ModelClass.model_id == model_id)
            .order_by(ModelClass.class_index)
        )
        return list(self._session.scalars(stmt).all())

    # ------------------------------------------------------------------
    # ProjectClass
    # ------------------------------------------------------------------

    def bulk_create_project_classes(
        self,
        project_id: int,
        created_by: int,
        entries: list[tuple[int, str, int | None, str | None]],  # (export_index, name, model_class_id, color)
    ) -> list[ProjectClass]:
        rows = [
            ProjectClass(
                project_id=project_id,
                export_index=export_index,
                name=name,
                model_class_id=model_class_id,
                color=color,
                created_by=created_by,
            )
            for export_index, name, model_class_id, color in entries
        ]
        self._session.add_all(rows)
        self._session.flush()
        return rows

    def create_project_class(
        self,
        *,
        project_id: int,
        name: str,
        color: str | None,
        created_by: int,
        model_class_id: int | None = None,
    ) -> ProjectClass:
        export_index = self._next_export_index(project_id)
        row = ProjectClass(
            project_id=project_id,
            export_index=export_index,
            name=name,
            color=color,
            model_class_id=model_class_id,
            created_by=created_by,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get_project_class(self, class_id: int) -> ProjectClass | None:
        return self._session.get(ProjectClass, class_id)

    def count_annotations_for_class(self, class_id: int) -> int:
        """해당 project_class 를 참조하는 annotations 행 수 (삭제·비삭제 포함)."""
        stmt = select(func.count()).select_from(Annotation).where(Annotation.class_id == class_id)
        return int(self._session.scalar(stmt) or 0)

    def delete_project_class_row(self, class_id: int) -> None:
        row = self._session.get(ProjectClass, class_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    def list_project_classes(self, project_id: int, include_inactive: bool = False) -> list[ProjectClass]:
        stmt = select(ProjectClass).where(ProjectClass.project_id == project_id)
        if not include_inactive:
            stmt = stmt.where(ProjectClass.is_active.is_(True))
        stmt = stmt.order_by(ProjectClass.export_index)
        return list(self._session.scalars(stmt).all())

    def name_exists(self, project_id: int, name: str, exclude_class_id: int | None = None) -> bool:
        stmt = select(ProjectClass).where(
            ProjectClass.project_id == project_id,
            ProjectClass.name == name,
        )
        if exclude_class_id is not None:
            stmt = stmt.where(ProjectClass.id != exclude_class_id)
        return self._session.scalar(stmt) is not None

    def get_taken_export_indices(self, project_id: int) -> set[int]:
        """프로젝트 내 이미 사용 중인 export_index 집합을 반환한다."""
        stmt = select(ProjectClass.export_index).where(ProjectClass.project_id == project_id)
        return set(self._session.scalars(stmt).all())

    def get_taken_names(self, project_id: int) -> set[str]:
        """프로젝트 내 이미 사용 중인 class name 집합을 반환한다."""
        stmt = select(ProjectClass.name).where(ProjectClass.project_id == project_id)
        return set(self._session.scalars(stmt).all())

    def _next_export_index(self, project_id: int) -> int:
        """삭제된 index를 재사용하지 않고 max+1을 반환한다.

        클래스가 하나도 없을 때는 10을 반환해 0-9를 모델 클래스용으로 예약한다.
        """
        stmt = select(func.max(ProjectClass.export_index)).where(
            ProjectClass.project_id == project_id
        )
        current_max: int | None = self._session.scalar(stmt)
        if current_max is None:
            return 10  # 0-9 reserved for model-sourced classes
        return current_max + 1
