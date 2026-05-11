"""어노테이션 도메인 요청/응답 Pydantic 스키마."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Path DTOs
# ---------------------------------------------------------------------------


class ImagePathDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: int = Field(..., ge=1)


class AssignmentPathDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_id: int = Field(..., ge=1)


# ---------------------------------------------------------------------------
# Bbox item  (공통 – 요청/응답에서 재사용)
# ---------------------------------------------------------------------------


class BboxItem(BaseModel):
    """정규화 좌표 bbox 공통 스키마 (0 ~ 1 범위 검증 포함)."""

    class_id: int = Field(..., ge=1)
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., gt=0.0, le=1.0)
    height: float = Field(..., gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_bounds(self) -> "BboxItem":
        if self.x + self.width > 1.0 + 1e-6:
            raise ValueError("x + width must not exceed 1.0")
        if self.y + self.height > 1.0 + 1e-6:
            raise ValueError("y + height must not exceed 1.0")
        return self


# ---------------------------------------------------------------------------
# PUT  — 전체 교체
# ---------------------------------------------------------------------------


class AnnotationPutRequest(BaseModel):
    """이미지 한 장의 어노테이션 전체를 교체한다 (CVAT PUT /annotations 패턴)."""

    annotations: list[BboxItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# PATCH  — 증분 저장  (CVAT PATCH ?action= 패턴)
# ---------------------------------------------------------------------------


class PatchCreateItem(BboxItem):
    """새로 생성할 bbox."""
    pass


class PatchUpdateItem(BboxItem):
    """수정할 bbox (id 필수)."""
    id: int = Field(..., ge=1)


class PatchDeleteItem(BaseModel):
    """soft delete 할 bbox (id 필수)."""
    id: int = Field(..., ge=1)


class AnnotationPatchRequest(BaseModel):
    """증분 저장 요청. action 쿼리 파라미터에 따라 items 의미가 달라진다."""

    items: list[PatchCreateItem | PatchUpdateItem | PatchDeleteItem] = Field(
        default_factory=list
    )


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Assignment status
# ---------------------------------------------------------------------------

VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "unassigned": {"assigned"},
    "assigned": {"in_progress"},
    "in_progress": {"done"},
    # done: 어노테이터 완료 표시만. 검토 요청은 POST …/request-review (done→submitted 일괄)
    "done": {"in_progress", "submitted"},
    "submitted": set(),
    "review_assigned": {"approved", "reverted"},
    "reverted": {"in_progress"},
}


class AssignmentStatusPatchRequest(BaseModel):
    status: str
    reason: str | None = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        allowed = {"in_progress", "done", "submitted", "approved", "reverted"}
        if v not in allowed:
            raise ValueError(f"cannot transition to '{v}'")
        return v


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_id: int
    assigned_to: int | None = None
    reviewer_id: int | None = None
    status: str
    can_edit: bool
    review_mode: bool = False
    submitted_at: datetime | None = None
    created_at: datetime


class MyAssignmentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assignment_id: int
    image_id: int
    project_id: int
    file_name: str
    width: int
    height: int
    status: str
    can_edit: bool


# ---------------------------------------------------------------------------
# Owner assignment management
# ---------------------------------------------------------------------------


class AssignAnnotatorRequest(BaseModel):
    user_id: int = Field(..., ge=1, description="어노테이터 user_id")
    count: int = Field(..., ge=1, description="할당할 이미지 수")


class AssignReviewerRequest(BaseModel):
    reviewer_id: int = Field(..., ge=1, description="리뷰어 user_id")
    count: int = Field(..., ge=1, description="할당할 이미지 수")


class RecallAnnotatorRequest(BaseModel):
    user_id: int = Field(..., ge=1, description="회수할 어노테이터 user_id")
    count: int | None = Field(
        default=None,
        ge=1,
        description="회수할 최대 장수(assigned/in_progress). 생략 시 가능한 전량 회수.",
    )


class RecallReviewerRequest(BaseModel):
    reviewer_id: int = Field(..., ge=1, description="회수할 리뷰어 user_id")
    count: int | None = Field(
        default=None,
        ge=1,
        description="회수할 최대 장수(review_assigned). 생략 시 가능한 전량 회수.",
    )


class BulkApproveReviewQueueRequest(BaseModel):
    scope: Literal["submitted_unassigned", "include_review_assigned"] = Field(
        ...,
        description=(
            "submitted_unassigned: submitted 이고 reviewer 미배정만 승인; "
            "include_review_assigned: 위에 더해 review_assigned 전부 승인"
        ),
    )


class UserStatItem(BaseModel):
    user_id: int
    assigned: int = Field(0, description="어노: 총 배정 장수. 리뷰어: 내게 검토 배정된 장수(전 상태 합)")
    annotate_done_only: int = Field(
        0, description="어노테이터 기준 status==done (승인 요청 전 완료 표시만)"
    )
    review_requested: int = Field(
        0,
        description=(
            "어노테이터 기준 검토 단계에 있는 장수: submitted(리뷰 미배정)·review_assigned(검토 배정 후 대기)"
        ),
    )
    approved: int = Field(0, description="어노테이터 기준 최종 승인(assignment approved) 장수")
    reverted: int = 0
    review_pending: int = Field(
        0,
        description="리뷰어 기준 승인 대기 장수(review_assigned)",
    )
    annotate_wip: int = Field(
        0,
        description=(
            "어노테이터 기준 승인 요청 전 파이프라인(할당만·작업중·완료 표시·반려 복귀;"
            " assigned+in_progress+done+reverted)"
        ),
    )
    annotate_recallable: int = Field(
        0,
        description="어노테이터 기준 owner 회수 가능 장수(assigned+in_progress); 리뷰어 행은 0",
    )


class AssignmentSummaryResponse(BaseModel):
    pool_stats: dict[str, int]
    annotator_stats: list[UserStatItem]
    reviewer_stats: list[UserStatItem]
