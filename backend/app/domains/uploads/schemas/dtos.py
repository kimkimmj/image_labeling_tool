"""업로드 도메인 요청/응답 Pydantic 스키마."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Path DTOs
# ---------------------------------------------------------------------------


class ProjectPathDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(..., ge=1)


class UploadJobPathDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: int = Field(..., ge=1)


class ImagePathDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: int = Field(..., ge=1)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class UploadJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    uploaded_by: int
    upload_type: str
    status: str
    original_file_name: str
    total_count: int | None = None
    processed_count: int | None = None
    skipped_count: int | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    # Phase 4 — 자동 라벨링 상태
    auto_label_status: str | None = None
    auto_label_error: str | None = None
    cover_image_id: int | None = None
    image_count: int = 0
    done_count: int = 0
    in_progress_count: int = 0
    # 목록 상세의 전체·작업중·완료(Done)·반려 탭 범위 합과 동일(submitted 제외); annotate 스코프에서만 채워짐
    annotate_tab_total_count: int = 0
    # 내게 배정된 어노 슬롯 총(승인 포함); annotate 스코프에서만 채움
    annotate_assignment_total_count: int = 0
    # 최종 승인(assignment status approved) 장수; annotate 스코프에서만 채움
    annotate_approved_count: int = 0
    review_pending_count: int | None = None
    review_approved_count: int | None = None
    done_without_reviewer_count: int | None = None
    # reviewer · scope=review 및 상세 for_participant+review 시 내 검토 큐 분해
    review_queue_total: int = 0
    review_queue_first_round: int = 0
    review_queue_after_reject: int = 0

class ImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    upload_job_id: int
    file_name: str
    width: int
    height: int
    created_at: datetime
    assignment_id: int | None = None
    assignment_status: str | None = None
    assignment_reverted_by: int | None = None
    annotation_count: int = 0


class AnnotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_id: int
    assignment_id: int
    class_id: int
    x: float
    y: float
    width: float
    height: float
    confidence: float | None = None
    source: str
    created_at: datetime
    updated_at: datetime


class AnnotationListResponse(BaseModel):
    annotations: list[AnnotationResponse]
