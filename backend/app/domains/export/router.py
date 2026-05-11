"""Export 도메인 라우터 (Phase 5 — MVP 이후 구현 예정).

현재는 구조만 정의하고, 실제 YOLO/COCO export 로직은
라벨링 MVP 안정화 후 app/tasks/export_tasks.py 와 함께 구현합니다.

계획된 API:
  POST /api/projects/{project_id}/exports      → export job 생성 (비동기)
  GET  /api/projects/{project_id}/exports/{id} → export 상태 조회
  GET  /api/projects/{project_id}/exports/{id}/download → 결과 ZIP 다운로드
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.domains.oAuth.deps import get_current_user
from app.models import User

export_router = APIRouter(prefix="/projects", tags=["export"])


@export_router.post(
    "/{project_id}/exports",
    status_code=status.HTTP_202_ACCEPTED,
)
def create_export(
    project_id: int = Path(..., ge=1),
    user: User = Depends(get_current_user),
) -> dict:
    """YOLO export job을 생성한다 (Phase 5에서 구현)."""
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        detail="export is planned for Phase 5 after labeling MVP",
    )


@export_router.get("/{project_id}/exports/{export_job_id}")
def get_export_status(
    project_id: int = Path(..., ge=1),
    export_job_id: str = Path(...),
    user: User = Depends(get_current_user),
) -> dict:
    """export job 상태를 조회한다 (Phase 5에서 구현)."""
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        detail="export is planned for Phase 5 after labeling MVP",
    )
