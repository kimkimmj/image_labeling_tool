"""Export Celery 태스크 (Phase 5 — MVP 이후 구현 예정).

계획:
1. project_id, format("yolo_v8" | "coco") 를 파라미터로 받는다.
2. DB에서 승인된(approved) annotation을 조회한다.
3. 이미지를 MinIO에서 스트리밍으로 읽으면서 ZIP에 묶는다.
4. YOLO v8 포맷:
   - images/{split}/{filename}
   - labels/{split}/{filename_stem}.txt  (class_index cx cy w h)
   - data.yaml (class 목록, train/val paths)
5. 결과 ZIP을 MinIO에 저장하고 presigned URL을 반환한다.

현재는 stub만 정의합니다.
"""

from __future__ import annotations

import logging

from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.export_tasks.run_export")
def run_export(self: object, export_job_id: str, project_id: int, fmt: str) -> None:  # noqa: ANN001
    """YOLO / COCO export 태스크 (Phase 5에서 구현)."""
    logger.info(
        "[Export %s] project_id=%d format=%s — Phase 5 구현 예정",
        export_job_id,
        project_id,
        fmt,
    )
    raise NotImplementedError("export_tasks.run_export is planned for Phase 5")
