"""어노테이션 도메인 라우터.

CVAT 패턴 참고:
  - PUT    /images/{id}/annotations           → 전체 교체
  - PATCH  /images/{id}/annotations?action=   → 증분 저장 (create | update | delete)
  - GET    /assignments/me                    → 내 작업 목록
  - GET    /assignments/{id}                  → 단일 assignment 조회
  - PATCH  /assignments/{id}/status           → 상태 전환

Note: GET /images/{id}/annotations 는 uploads 라우터가 담당한다 (중복 방지).
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domains.annotations.exceptions import (
    AnnotationForbiddenError,
    AnnotationImmutableError,
    AnnotationNotFoundError,
    InvalidClassError,
)
from app.domains.annotations.schemas.dtos import (
    AnnotationListResponse,
    AnnotationPatchRequest,
    AnnotationPutRequest,
    AnnotationResponse,
    AssignAnnotatorRequest,
    AssignmentPathDTO,
    AssignmentResponse,
    AssignmentStatusPatchRequest,
    AssignmentSummaryResponse,
    ImagePathDTO,
    MyAssignmentItem,
    RecallAnnotatorRequest,
    RecallReviewerRequest,
    AssignReviewerRequest,
    BulkApproveReviewQueueRequest,
    UserStatItem,
)
from app.domains.annotations.services.annotation_service import (
    AnnotationService,
    AssignmentSummaryDTO,
)
from app.domains.oAuth.deps import get_current_user
from app.models import User

images_anno_router = APIRouter(prefix="/images", tags=["annotations"])
assignments_router = APIRouter(prefix="/assignments", tags=["assignments"])
upload_jobs_anno_router = APIRouter(prefix="/upload-jobs", tags=["annotations"])


# ------------------------------------------------------------------
# Dependency factories
# ------------------------------------------------------------------


def _job_path(job_id: Annotated[int, Path(ge=1)]) -> int:
    return job_id


def _image_path(image_id: Annotated[int, Path(ge=1)]) -> ImagePathDTO:
    return ImagePathDTO(image_id=image_id)


def _assignment_path(assignment_id: Annotated[int, Path(ge=1)]) -> AssignmentPathDTO:
    return AssignmentPathDTO(assignment_id=assignment_id)


def get_annotation_service(db: Session = Depends(get_db)) -> AnnotationService:
    return AnnotationService(db)


# ------------------------------------------------------------------
# HTTP exception helpers
# ------------------------------------------------------------------


def _forbidden(detail: str = "forbidden") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail=detail)


def _not_found(detail: str = "not_found") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=detail)


def _immutable() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail="annotations are immutable for approved assignments",
    )


def _bad_class() -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_class_id")


# ------------------------------------------------------------------
# PUT /images/{image_id}/annotations  — 전체 교체
# ------------------------------------------------------------------


@images_anno_router.put("/{image_id}/annotations", response_model=AnnotationListResponse)
def replace_annotations(
    body: AnnotationPutRequest,
    path: ImagePathDTO = Depends(_image_path),
    for_participant: Annotated[bool, Query(description="owner 참여 모드")] = False,
    participant_scope: Annotated[
        Literal["annotate", "review"] | None,
        Query(description="owner+for_participant: annotate|review"),
    ] = None,
    user: User = Depends(get_current_user),
    svc: AnnotationService = Depends(get_annotation_service),
) -> AnnotationListResponse:
    try:
        anns = svc.replace_annotations(
            image_id=path.image_id,
            user_id=user.id,
            body=body,
            for_participant=for_participant,
            participant_scope=participant_scope,
        )
    except AnnotationNotFoundError as exc:
        raise _not_found("image_not_found") from exc
    except AnnotationForbiddenError as exc:
        raise _forbidden(str(exc)) from exc
    except AnnotationImmutableError as exc:
        raise _immutable() from exc
    except InvalidClassError as exc:
        raise _bad_class() from exc
    return AnnotationListResponse(
        annotations=[
            AnnotationResponse(
                id=a.id,
                image_id=a.image_id,
                assignment_id=a.assignment_id,
                class_id=a.class_id,
                x=a.x,
                y=a.y,
                width=a.width,
                height=a.height,
                confidence=a.confidence,
                source=a.source,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in anns
        ]
    )


# ------------------------------------------------------------------
# PATCH /images/{image_id}/annotations?action=create|update|delete
# ------------------------------------------------------------------


@images_anno_router.patch("/{image_id}/annotations", response_model=AnnotationListResponse)
def patch_annotations(
    body: AnnotationPatchRequest,
    path: ImagePathDTO = Depends(_image_path),
    action: Literal["create", "update", "delete"] = Query(...),
    for_participant: Annotated[bool, Query(description="owner 참여 모드")] = False,
    participant_scope: Annotated[
        Literal["annotate", "review"] | None,
        Query(description="owner+for_participant: annotate|review"),
    ] = None,
    user: User = Depends(get_current_user),
    svc: AnnotationService = Depends(get_annotation_service),
) -> AnnotationListResponse:
    try:
        anns = svc.patch_annotations(
            image_id=path.image_id,
            user_id=user.id,
            action=action,
            body=body,
            for_participant=for_participant,
            participant_scope=participant_scope,
        )
    except AnnotationNotFoundError as exc:
        raise _not_found("image_not_found") from exc
    except AnnotationForbiddenError as exc:
        raise _forbidden(str(exc)) from exc
    except AnnotationImmutableError as exc:
        raise _immutable() from exc
    except InvalidClassError as exc:
        raise _bad_class() from exc
    return AnnotationListResponse(
        annotations=[
            AnnotationResponse(
                id=a.id,
                image_id=a.image_id,
                assignment_id=a.assignment_id,
                class_id=a.class_id,
                x=a.x,
                y=a.y,
                width=a.width,
                height=a.height,
                confidence=a.confidence,
                source=a.source,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in anns
        ]
    )


# ------------------------------------------------------------------
# POST /upload-jobs/{job_id}/request-review  — 내 할당 중 done → submitted 일괄 (검토 요청)
# ------------------------------------------------------------------


@upload_jobs_anno_router.post("/{job_id}/request-review")
def request_review(
    job_id: int = Depends(_job_path),
    user: User = Depends(get_current_user),
    svc: AnnotationService = Depends(get_annotation_service),
) -> dict:
    try:
        count = svc.request_review_for_job(job_id=job_id, user_id=user.id)
    except AnnotationNotFoundError as exc:
        raise _not_found("job_not_found") from exc
    except AnnotationForbiddenError as exc:
        raise _forbidden() from exc
    return {"transitioned": count}


# ------------------------------------------------------------------
# GET /images/{image_id}/assignment  — 이미지의 assignment 조회
# ------------------------------------------------------------------


@images_anno_router.get("/{image_id}/assignment", response_model=AssignmentResponse)
def get_image_assignment(
    path: ImagePathDTO = Depends(_image_path),
    for_participant: Annotated[bool, Query(description="owner 참여 모드")] = False,
    participant_scope: Annotated[
        Literal["annotate", "review"] | None,
        Query(description="owner+for_participant: annotate|review"),
    ] = None,
    user: User = Depends(get_current_user),
    svc: AnnotationService = Depends(get_annotation_service),
) -> AssignmentResponse:
    try:
        a = svc.get_assignment_for_image(
            image_id=path.image_id,
            user_id=user.id,
            for_participant=for_participant,
            participant_scope=participant_scope,
        )
    except AnnotationNotFoundError as exc:
        raise _not_found("assignment_not_found") from exc
    except AnnotationForbiddenError as exc:
        raise _forbidden() from exc
    return AssignmentResponse(
        id=a.id,
        image_id=a.image_id,
        assigned_to=a.assigned_to,
        reviewer_id=a.reviewer_id,
        status=a.status,
        can_edit=a.can_edit,
        review_mode=a.review_mode,
        submitted_at=a.submitted_at,
        created_at=a.created_at,
    )


# ------------------------------------------------------------------
# GET /assignments/me  — 내 작업 목록
# ------------------------------------------------------------------


@assignments_router.get("/me", response_model=list[MyAssignmentItem])
def list_my_assignments(
    user: User = Depends(get_current_user),
    svc: AnnotationService = Depends(get_annotation_service),
) -> list[MyAssignmentItem]:
    items = svc.list_my_assignments(user_id=user.id)
    return [
        MyAssignmentItem(
            assignment_id=i.assignment_id,
            image_id=i.image_id,
            project_id=i.project_id,
            file_name=i.file_name,
            width=i.width,
            height=i.height,
            status=i.status,
            can_edit=i.can_edit,
        )
        for i in items
    ]


# ------------------------------------------------------------------
# GET /assignments/{assignment_id}
# ------------------------------------------------------------------


@assignments_router.get("/{assignment_id}", response_model=AssignmentResponse)
def get_assignment(
    path: AssignmentPathDTO = Depends(_assignment_path),
    user: User = Depends(get_current_user),
    svc: AnnotationService = Depends(get_annotation_service),
) -> AssignmentResponse:
    try:
        a = svc.get_assignment(assignment_id=path.assignment_id, user_id=user.id)
    except AnnotationNotFoundError as exc:
        raise _not_found("assignment_not_found") from exc
    except AnnotationForbiddenError as exc:
        raise _forbidden() from exc
    return AssignmentResponse(
        id=a.id,
        image_id=a.image_id,
        assigned_to=a.assigned_to,
        reviewer_id=a.reviewer_id,
        status=a.status,
        can_edit=a.can_edit,
        review_mode=a.review_mode,
        submitted_at=a.submitted_at,
        created_at=a.created_at,
    )


# ------------------------------------------------------------------
# PATCH /assignments/{assignment_id}/status
# ------------------------------------------------------------------


@assignments_router.patch("/{assignment_id}/status", response_model=AssignmentResponse)
def transition_status(
    body: AssignmentStatusPatchRequest,
    path: AssignmentPathDTO = Depends(_assignment_path),
    for_participant: Annotated[bool, Query(description="owner 참여 모드")] = False,
    participant_scope: Annotated[
        Literal["annotate", "review"] | None,
        Query(description="owner+for_participant: annotate|review"),
    ] = None,
    user: User = Depends(get_current_user),
    svc: AnnotationService = Depends(get_annotation_service),
) -> AssignmentResponse:
    try:
        a = svc.transition_assignment_status(
            assignment_id=path.assignment_id,
            user_id=user.id,
            body=body,
            for_participant=for_participant,
            participant_scope=participant_scope,
        )
    except AnnotationNotFoundError as exc:
        raise _not_found("assignment_not_found") from exc
    except AnnotationForbiddenError as exc:
        raise _forbidden(str(exc)) from exc
    return AssignmentResponse(
        id=a.id,
        image_id=a.image_id,
        assigned_to=a.assigned_to,
        reviewer_id=a.reviewer_id,
        status=a.status,
        can_edit=a.can_edit,
        review_mode=a.review_mode,
        submitted_at=a.submitted_at,
        created_at=a.created_at,
    )


# ------------------------------------------------------------------
# Owner: 어노테이터 할당 POST /upload-jobs/{job_id}/assignments/annotate
# ------------------------------------------------------------------


@upload_jobs_anno_router.post("/{job_id}/assignments/annotate")
def assign_annotator(
    body: AssignAnnotatorRequest,
    job_id: int = Depends(_job_path),
    user: User = Depends(get_current_user),
    svc: AnnotationService = Depends(get_annotation_service),
) -> dict:
    try:
        count = svc.assign_annotator(
            job_id=job_id, user_id=user.id,
            annotator_id=body.user_id, count=body.count,
        )
    except AnnotationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except AnnotationForbiddenError as exc:
        raise _forbidden(str(exc)) from exc
    return {"assigned": count}


# ------------------------------------------------------------------
# Owner: 어노테이터 회수 POST /upload-jobs/{job_id}/assignments/recall-annotate
# ------------------------------------------------------------------


@upload_jobs_anno_router.post("/{job_id}/assignments/recall-annotate")
def recall_annotator(
    body: RecallAnnotatorRequest,
    job_id: int = Depends(_job_path),
    user: User = Depends(get_current_user),
    svc: AnnotationService = Depends(get_annotation_service),
) -> dict:
    try:
        count = svc.recall_annotator(
            job_id=job_id,
            user_id=user.id,
            annotator_id=body.user_id,
            count=body.count,
        )
    except AnnotationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except AnnotationForbiddenError as exc:
        raise _forbidden(str(exc)) from exc
    return {"recalled": count}


# ------------------------------------------------------------------
# Owner: 리뷰어 할당 POST /upload-jobs/{job_id}/assignments/review
# ------------------------------------------------------------------


@upload_jobs_anno_router.post("/{job_id}/assignments/review")
def assign_reviewer(
    body: AssignReviewerRequest,
    job_id: int = Depends(_job_path),
    user: User = Depends(get_current_user),
    svc: AnnotationService = Depends(get_annotation_service),
) -> dict:
    try:
        count = svc.assign_reviewer(
            job_id=job_id, user_id=user.id,
            reviewer_id=body.reviewer_id, count=body.count,
        )
    except AnnotationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except AnnotationForbiddenError as exc:
        raise _forbidden(str(exc)) from exc
    return {"assigned": count}


# ------------------------------------------------------------------
# Owner: 리뷰어 회수 POST /upload-jobs/{job_id}/assignments/recall-review
# ------------------------------------------------------------------


@upload_jobs_anno_router.post("/{job_id}/assignments/recall-review")
def recall_reviewer(
    body: RecallReviewerRequest,
    job_id: int = Depends(_job_path),
    user: User = Depends(get_current_user),
    svc: AnnotationService = Depends(get_annotation_service),
) -> dict:
    try:
        count = svc.recall_reviewer(
            job_id=job_id,
            user_id=user.id,
            reviewer_id=body.reviewer_id,
            count=body.count,
        )
    except AnnotationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except AnnotationForbiddenError as exc:
        raise _forbidden(str(exc)) from exc
    return {"recalled": count}


# ------------------------------------------------------------------
# Owner: 검토 대기 일괄 승인 POST /upload-jobs/{job_id}/assignments/bulk-approve-review-queue
# ------------------------------------------------------------------


@upload_jobs_anno_router.post("/{job_id}/assignments/bulk-approve-review-queue")
def bulk_approve_review_queue(
    body: BulkApproveReviewQueueRequest,
    job_id: int = Depends(_job_path),
    user: User = Depends(get_current_user),
    svc: AnnotationService = Depends(get_annotation_service),
) -> dict:
    try:
        count = svc.bulk_approve_review_queue(
            job_id=job_id, user_id=user.id, scope=body.scope,
        )
    except AnnotationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except AnnotationForbiddenError as exc:
        raise _forbidden(str(exc)) from exc
    return {"approved": count}


# ------------------------------------------------------------------
# Owner: 집계 GET /upload-jobs/{job_id}/assignment-summary
# ------------------------------------------------------------------


@upload_jobs_anno_router.get(
    "/{job_id}/assignment-summary", response_model=AssignmentSummaryResponse
)
def get_assignment_summary(
    job_id: int = Depends(_job_path),
    user: User = Depends(get_current_user),
    svc: AnnotationService = Depends(get_annotation_service),
) -> AssignmentSummaryResponse:
    try:
        summary: AssignmentSummaryDTO = svc.get_assignment_summary(
            job_id=job_id, user_id=user.id,
        )
    except AnnotationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except AnnotationForbiddenError as exc:
        raise _forbidden(str(exc)) from exc
    return AssignmentSummaryResponse(
        pool_stats=summary.pool_stats,
        annotator_stats=[
            UserStatItem(
                user_id=s.user_id,
                assigned=s.assigned,
                annotate_done_only=s.annotate_done_only,
                review_requested=s.review_requested,
                approved=s.approved,
                reverted=s.reverted,
                review_pending=s.review_pending,
                annotate_wip=s.annotate_wip,
                annotate_recallable=s.annotate_recallable,
            )
            for s in summary.annotator_stats
        ],
        reviewer_stats=[
            UserStatItem(
                user_id=s.user_id,
                assigned=s.assigned,
                annotate_done_only=s.annotate_done_only,
                review_requested=s.review_requested,
                approved=s.approved,
                reverted=s.reverted,
                review_pending=s.review_pending,
                annotate_wip=s.annotate_wip,
                annotate_recallable=s.annotate_recallable,
            )
            for s in summary.reviewer_stats
        ],
    )
