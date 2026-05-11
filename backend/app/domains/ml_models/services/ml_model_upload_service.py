"""YOLO .pt 업로드·저장·내 모델 목록 (owner_id = 현재 사용자)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.storage import StorageClient
from app.core.yolo_parser import YoloModelInfo, parse_yolo_pt
from app.domains.projects.repositories.class_repository import ClassRepository


@dataclass(frozen=True)
class MlModelUploadResultDTO:
    id: int
    name: str
    version: str | None
    framework: str
    file_path: str
    created_at: datetime


def _safe_filename(filename: str) -> str:
    name = re.sub(r"[^\w.\-]", "_", filename.replace("/", "_").replace("\\", "_"))
    return name[:200]


class MlModelUploadService:
    def __init__(self, db: Session, storage: StorageClient) -> None:
        self._db = db
        self._classes = ClassRepository(db)
        self._storage = storage

    def upload_model(
        self,
        *,
        owner_user_id: int,
        filename: str,
        file_bytes: bytes,
        model_name: str,
    ) -> MlModelUploadResultDTO:
        """YOLO .pt를 파싱해 저장하고 ml_models·model_classes 행을 생성한다."""
        info: YoloModelInfo = parse_yolo_pt(file_bytes, filename)

        ml_model = self._classes.create_model(
            owner_id=owner_user_id,
            name=model_name,
            version=info.version,
            framework=info.framework,
            file_path="",
        )

        safe_name = _safe_filename(filename)
        object_key = f"users/{owner_user_id}/models/{ml_model.id}/original/{safe_name}"
        ml_model.file_path = object_key

        try:
            self._storage.upload_bytes(object_key, file_bytes, content_type="application/octet-stream")
        except Exception as exc:
            self._db.rollback()
            raise RuntimeError(f"모델 파일 업로드 실패: {exc}") from exc

        self._classes.bulk_create_model_classes(ml_model.id, info.class_names)

        try:
            self._db.commit()
        except Exception as exc:
            self._storage.delete_object(object_key)
            raise RuntimeError(f"DB 커밋 실패: {exc}") from exc

        self._db.refresh(ml_model)
        return MlModelUploadResultDTO(
            id=ml_model.id,
            name=ml_model.name,
            version=ml_model.version,
            framework=ml_model.framework,
            file_path=ml_model.file_path,
            created_at=ml_model.created_at,
        )

    def list_my_models(self, *, owner_user_id: int) -> list[MlModelUploadResultDTO]:
        rows = self._classes.list_models_for_owner(owner_user_id)
        return [
            MlModelUploadResultDTO(
                id=r.id,
                name=r.name,
                version=r.version,
                framework=r.framework,
                file_path=r.file_path,
                created_at=r.created_at,
            )
            for r in rows
        ]
