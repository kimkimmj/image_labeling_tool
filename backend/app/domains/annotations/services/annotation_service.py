"""어노테이션 도메인 비즈니스 로직."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.domains.annotations.exceptions import (
    AnnotationForbiddenError,
    AnnotationImmutableError,
    AnnotationNotFoundError,
    InvalidClassError,
)
from app.domains.annotations.repositories.annotation_repository import (
    AnnotationRepository,
    UserAssignmentStat,
    _EDITABLE_STATUSES,
    _REVIEW_EDITABLE_STATUSES,
)
from app.domains.annotations.schemas.dtos import (
    VALID_STATUS_TRANSITIONS,
    AnnotationPatchRequest,
    AnnotationPutRequest,
    AssignmentStatusPatchRequest,
    PatchCreateItem,
    PatchDeleteItem,
    PatchUpdateItem,
)
from app.domains.projects.repositories.project_repository import ProjectRepository
from app.models.upload import Annotation, Image, ImageAssignment

# 업로드 서비스와 동일: 리뷰 탭·리뷰 스코프에서 검토자에게 보이는 할당 상태
_REVIEW_SCOPE_VISIBLE_STATUSES = frozenset({"submitted", "review_assigned"})


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnnotationDTO:
    id: int
    image_id: int
    assignment_id: int
    class_id: int
    x: float
    y: float
    width: float
    height: float
    confidence: float | None
    source: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AssignmentDTO:
    id: int
    image_id: int
    assigned_to: int | None
    reviewer_id: int | None
    status: str
    can_edit: bool
    review_mode: bool  # reviewer_id 일치 시 에디터에서 승인/반려 활성화
    submitted_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class AssignmentSummaryDTO:
    annotator_stats: list[UserAssignmentStat]
    reviewer_stats: list[UserAssignmentStat]
    pool_stats: dict[str, int]


@dataclass(frozen=True)
class MyAssignmentDTO:
    assignment_id: int
    image_id: int
    project_id: int
    file_name: str
    width: int
    height: int
    status: str
    can_edit: bool


def _to_ann_dto(ann: Annotation) -> AnnotationDTO:
    return AnnotationDTO(
        id=ann.id,
        image_id=ann.image_id,
        assignment_id=ann.assignment_id,
        class_id=ann.class_id,
        x=ann.x,
        y=ann.y,
        width=ann.width,
        height=ann.height,
        confidence=ann.confidence,
        source=ann.source,
        created_at=ann.created_at,
        updated_at=ann.updated_at,
    )


def _to_assignment_dto(a: ImageAssignment, current_user_id: int | None = None) -> AssignmentDTO:
    review_mode = (
        current_user_id is not None
        and a.reviewer_id == current_user_id
        and a.status in _REVIEW_EDITABLE_STATUSES
    )
    # 검토 단계에서도 리뷰어는 박스 편집 가능(저장 경로는 _require_edit_permission과 동일 규약)
    can_edit = bool(a.status in _EDITABLE_STATUSES or review_mode)
    return AssignmentDTO(
        id=a.id,
        image_id=a.image_id,
        assigned_to=a.assigned_to,
        reviewer_id=a.reviewer_id,
        status=a.status,
        can_edit=can_edit,
        review_mode=review_mode,
        submitted_at=a.submitted_at,
        created_at=a.created_at,
    )


def _to_my_dto(a: ImageAssignment) -> MyAssignmentDTO:
    img: Image = a.image
    return MyAssignmentDTO(
        assignment_id=a.id,
        image_id=img.id,
        project_id=img.project_id,
        file_name=img.file_name,
        width=img.width,
        height=img.height,
        status=a.status,
        can_edit=a.status in _EDITABLE_STATUSES,
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AnnotationService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = AnnotationRepository(db)
        self._projects = ProjectRepository(db)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_member(self, project_id: int, user_id: int) -> str:
        """멤버인지 확인하고 role을 반환한다."""
        m = self._projects.get_membership(project_id, user_id)
        if m is None:
            raise AnnotationForbiddenError("not a project member")
        return m.role

    def _get_image_or_raise(self, image_id: int) -> Image:
        img = self._repo.get_image_with_assignment(image_id)
        if img is None:
            raise AnnotationNotFoundError(f"image {image_id} not found")
        return img

    def _require_edit_permission(
        self,
        image: Image,
        user_id: int,
        role: str,
        *,
        for_participant: bool = False,
        participant_scope: str | None = None,
    ) -> ImageAssignment:
        """수정 권한을 검증하고 assignment를 반환한다.

        규칙:
        - owner: approved 제외 모두 가능 (for_participant 이면 annotate 또는 review 스코프에 따라 제한)
        - reviewer: annotate 스코프면 어노테이터와 동일; review 스코프면 reviewer_id 일치 + review_assigned 일 때 편집
        - annotator: assigned_to 일치 + 편집 가능 상태
        """
        assignment = image.assignment
        if assignment is None:
            raise AnnotationForbiddenError("image has no assignment")

        if assignment.status == "approved":
            raise AnnotationImmutableError("approved annotations cannot be modified")

        if role == "owner":
            if not for_participant:
                return assignment
            scope = participant_scope or "annotate"
            if scope == "review":
                if assignment.reviewer_id != user_id:
                    raise AnnotationForbiddenError("not assigned to review this image")
                if assignment.status not in _REVIEW_EDITABLE_STATUSES:
                    raise AnnotationForbiddenError(
                        f"assignment status '{assignment.status}' does not allow review editing"
                    )
                return assignment
            if assignment.assigned_to != user_id:
                raise AnnotationForbiddenError("not assigned to this image")
            if assignment.status not in _EDITABLE_STATUSES:
                raise AnnotationForbiddenError(
                    f"assignment status '{assignment.status}' does not allow editing"
                )
            return assignment

        if role == "reviewer":
            scope = participant_scope or "annotate"
            if scope == "review":
                if assignment.reviewer_id != user_id:
                    raise AnnotationForbiddenError("not assigned to review this image")
                if assignment.status not in _REVIEW_EDITABLE_STATUSES:
                    raise AnnotationForbiddenError(
                        f"assignment status '{assignment.status}' does not allow review editing"
                    )
                return assignment
            if assignment.assigned_to != user_id:
                raise AnnotationForbiddenError("not assigned to this image")
            if assignment.status not in _EDITABLE_STATUSES:
                raise AnnotationForbiddenError(
                    f"assignment status '{assignment.status}' does not allow editing"
                )
            return assignment

        # annotator
        if assignment.assigned_to != user_id:
            raise AnnotationForbiddenError("not assigned to this image")
        if assignment.status not in _EDITABLE_STATUSES:
            raise AnnotationForbiddenError(
                f"assignment status '{assignment.status}' does not allow editing"
            )
        return assignment

    def _validate_class_ids(self, class_ids: set[int], project_id: int) -> None:
        active_ids = self._repo.get_active_class_ids(project_id)
        invalid = class_ids - active_ids
        if invalid:
            raise InvalidClassError(f"invalid or inactive class_id(s): {invalid}")

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------

    def list_annotations(self, *, image_id: int, user_id: int) -> list[AnnotationDTO]:
        image = self._get_image_or_raise(image_id)
        self._require_member(image.project_id, user_id)
        anns = self._repo.list_annotations(image_id)
        return [_to_ann_dto(a) for a in anns]

    # ------------------------------------------------------------------
    # PUT — 전체 교체
    # ------------------------------------------------------------------

    def replace_annotations(
        self,
        *,
        image_id: int,
        user_id: int,
        body: AnnotationPutRequest,
        for_participant: bool = False,
        participant_scope: str | None = None,
    ) -> list[AnnotationDTO]:
        image = self._get_image_or_raise(image_id)
        role = self._require_member(image.project_id, user_id)
        assignment = self._require_edit_permission(
            image,
            user_id,
            role,
            for_participant=for_participant,
            participant_scope=participant_scope,
        )

        # class_id 검증
        if body.annotations:
            self._validate_class_ids(
                {item.class_id for item in body.annotations},
                image.project_id,
            )

        now = datetime.utcnow()
        rows = self._repo.replace_all(
            image_id=image_id,
            assignment_id=assignment.id,
            items=[item.model_dump() for item in body.annotations],
            user_id=user_id,
            now=now,
        )
        self._db.commit()
        return [_to_ann_dto(r) for r in rows]

    # ------------------------------------------------------------------
    # PATCH — 증분 저장
    # ------------------------------------------------------------------

    def patch_annotations(
        self,
        *,
        image_id: int,
        user_id: int,
        action: str,
        body: AnnotationPatchRequest,
        for_participant: bool = False,
        participant_scope: str | None = None,
    ) -> list[AnnotationDTO]:
        if action not in ("create", "update", "delete"):
            raise ValueError(f"unknown action: {action}")

        image = self._get_image_or_raise(image_id)
        role = self._require_member(image.project_id, user_id)
        assignment = self._require_edit_permission(
            image,
            user_id,
            role,
            for_participant=for_participant,
            participant_scope=participant_scope,
        )

        now = datetime.utcnow()

        if action == "create":
            items = [
                i.model_dump()
                for i in body.items
                if isinstance(i, PatchCreateItem)
            ]
            if items:
                self._validate_class_ids(
                    {item["class_id"] for item in items},
                    image.project_id,
                )
            rows = self._repo.create_annotations(
                image_id=image_id,
                assignment_id=assignment.id,
                items=items,
                user_id=user_id,
                now=now,
            )
            self._db.commit()
            return [_to_ann_dto(r) for r in rows]

        elif action == "update":
            items = [
                i.model_dump()
                for i in body.items
                if isinstance(i, PatchUpdateItem)
            ]
            if items:
                self._validate_class_ids(
                    {item["class_id"] for item in items},
                    image.project_id,
                )
            rows = self._repo.update_annotations(
                image_id=image_id,
                items=items,
                user_id=user_id,
                now=now,
            )
            self._db.commit()
            return [_to_ann_dto(r) for r in rows]

        else:  # delete
            ids = [
                i.id
                for i in body.items
                if isinstance(i, PatchDeleteItem)
            ]
            self._repo.delete_annotations(
                image_id=image_id,
                annotation_ids=ids,
                user_id=user_id,
                now=now,
            )
            self._db.commit()
            return []

    # ------------------------------------------------------------------
    # Assignment — GET my queue
    # ------------------------------------------------------------------

    def list_my_assignments(self, *, user_id: int) -> list[MyAssignmentDTO]:
        assignments = self._repo.list_my_assignments(user_id)
        return [_to_my_dto(a) for a in assignments]

    def get_assignment_for_image(
        self,
        *,
        image_id: int,
        user_id: int,
        for_participant: bool = False,
        participant_scope: str | None = None,
    ) -> AssignmentDTO:
        img = self._repo.get_image(image_id)
        if img is None:
            raise AnnotationNotFoundError(f"image {image_id} not found")
        role = self._require_member(img.project_id, user_id)
        assignment = self._repo.get_assignment_for_image(image_id)
        if assignment is None:
            raise AnnotationNotFoundError(f"assignment for image {image_id} not found")
        if role == "owner" and for_participant:
            scope = participant_scope or "annotate"
            if scope == "review":
                if assignment.reviewer_id != user_id:
                    raise AnnotationForbiddenError("not assigned to review this image")
            elif assignment.assigned_to != user_id:
                raise AnnotationForbiddenError("not assigned to this image")
        elif role == "reviewer":
            scope = participant_scope or "annotate"
            if scope == "review":
                if (
                    assignment.reviewer_id != user_id
                    or assignment.status not in _REVIEW_SCOPE_VISIBLE_STATUSES
                ):
                    raise AnnotationForbiddenError("not assigned to review this image")
            elif assignment.assigned_to != user_id:
                raise AnnotationForbiddenError("not assigned to this image")
        elif role == "annotator":
            if assignment.assigned_to != user_id:
                raise AnnotationForbiddenError("not assigned to this image")
        # 어노테이션 작업 큐: 승인 완료 분은 목록과 동일하게 조회 불가
        _scope = participant_scope or "annotate"
        if (
            assignment.status == "approved"
            and (
                role == "annotator"
                or (
                    role == "reviewer"
                    and _scope == "annotate"
                )
                or (
                    role == "owner"
                    and for_participant
                    and _scope == "annotate"
                )
            )
        ):
            raise AnnotationForbiddenError("assignment is approved")
        return _to_assignment_dto(assignment, current_user_id=user_id)

    def get_assignment(self, *, assignment_id: int, user_id: int) -> AssignmentDTO:
        assignment = self._repo.get_assignment(assignment_id)
        if assignment is None:
            raise AnnotationNotFoundError(f"assignment {assignment_id} not found")
        img = self._repo.get_image(assignment.image_id)
        if img is None:
            raise AnnotationNotFoundError("image not found")
        self._require_member(img.project_id, user_id)
        return _to_assignment_dto(assignment, current_user_id=user_id)

    # ------------------------------------------------------------------
    # Assignment — status transition (annotator용)
    # ------------------------------------------------------------------

    def transition_assignment_status(
        self,
        *,
        assignment_id: int,
        user_id: int,
        body: AssignmentStatusPatchRequest,
        for_participant: bool = False,
        participant_scope: str | None = None,
    ) -> AssignmentDTO:
        assignment = self._repo.get_assignment(assignment_id)
        if assignment is None:
            raise AnnotationNotFoundError(f"assignment {assignment_id} not found")

        img = self._repo.get_image(assignment.image_id)
        if img is None:
            raise AnnotationNotFoundError("image not found")

        role = self._require_member(img.project_id, user_id)

        p_scope = participant_scope or "annotate"

        if role == "owner" and for_participant:
            if p_scope == "review":
                if assignment.reviewer_id != user_id:
                    raise AnnotationForbiddenError("not assigned to review this image")
                if body.status in ("approved", "reverted") and assignment.status != "review_assigned":
                    raise AnnotationForbiddenError(
                        "can only approve/revert images assigned for review"
                    )
            elif assignment.assigned_to != user_id:
                raise AnnotationForbiddenError("not your assignment")

        # reviewer: 스코프에 따라 검토 승인/반려 vs 어노테이션 작업 전환 분리
        if role == "reviewer":
            rs = participant_scope or "annotate"
            if rs == "review":
                if assignment.reviewer_id != user_id:
                    raise AnnotationForbiddenError("not your review assignment")
                if body.status in ("approved", "reverted") and assignment.status != "review_assigned":
                    raise AnnotationForbiddenError(
                        "can only approve/revert images assigned for review"
                    )
            else:
                if assignment.assigned_to != user_id:
                    raise AnnotationForbiddenError("not your assignment")
                if body.status in ("approved", "reverted"):
                    raise AnnotationForbiddenError(
                        "approve and revert are only allowed in review scope"
                    )

        # annotator는 자신의 assignment만 전환 가능
        if role == "annotator" and assignment.assigned_to != user_id:
            raise AnnotationForbiddenError("not your assignment")

        allowed_next = VALID_STATUS_TRANSITIONS.get(assignment.status, set())
        if body.status not in allowed_next:
            raise AnnotationForbiddenError(
                f"cannot transition from '{assignment.status}' to '{body.status}'"
            )

        now = datetime.utcnow()

        # reverted: 검토 반려(리뷰어 회수 · 어노테이터 쪽은 상태 reverted 로 통일)
        if body.status == "reverted":
            updated = self._repo.revert_assignment(
                assignment=assignment,
                reviewer_id=user_id,
                reason=getattr(body, "reason", None),
                now=now,
            )
        elif body.status == "approved":
            updated = self._repo.approve_assignment(
                assignment=assignment,
                reviewer_id=user_id,
                now=now,
            )
        else:
            updated = self._repo.update_assignment_status(
                assignment_id=assignment_id,
                status=body.status,
                now=now,
            )
        self._db.commit()
        return _to_assignment_dto(updated, current_user_id=user_id)

    # ------------------------------------------------------------------
    # Owner: 어노테이터 할당 / 회수
    # ------------------------------------------------------------------

    def _require_owner(self, project_id: int, user_id: int) -> None:
        role = self._require_member(project_id, user_id)
        if role != "owner":
            raise AnnotationForbiddenError("owner only")

    def _get_job_project(self, job_id: int) -> int:
        from app.domains.uploads.repositories.upload_repository import UploadRepository
        job = UploadRepository(self._db).get_job(job_id)
        if job is None:
            raise AnnotationNotFoundError(f"upload job {job_id} not found")
        return job.project_id

    def assign_annotator(
        self, *, job_id: int, user_id: int, annotator_id: int, count: int
    ) -> int:
        project_id = self._get_job_project(job_id)
        self._require_owner(project_id, user_id)
        candidates = self._repo.get_unassigned_images_for_job(job_id, count)
        assigned = self._repo.assign_to_annotator(
            assignments=candidates,
            user_id=annotator_id,
            assigned_by=user_id,
        )
        self._db.commit()
        return assigned

    def recall_annotator(
        self,
        *,
        job_id: int,
        user_id: int,
        annotator_id: int,
        count: int | None = None,
    ) -> int:
        project_id = self._get_job_project(job_id)
        self._require_owner(project_id, user_id)
        recalled = self._repo.recall_annotator_assignments(
            job_id, annotator_id, limit=count,
        )
        self._db.commit()
        return recalled

    # ------------------------------------------------------------------
    # Owner: 리뷰어 할당 / 회수
    # ------------------------------------------------------------------

    def assign_reviewer(
        self, *, job_id: int, user_id: int, reviewer_id: int, count: int
    ) -> int:
        project_id = self._get_job_project(job_id)
        self._require_owner(project_id, user_id)
        candidates = self._repo.get_submitted_pending_reviewer_for_job(job_id, count)
        assigned = self._repo.assign_to_reviewer(
            assignments=candidates,
            reviewer_id=reviewer_id,
        )
        self._db.commit()
        return assigned

    def recall_reviewer(
        self,
        *,
        job_id: int,
        user_id: int,
        reviewer_id: int,
        count: int | None = None,
    ) -> int:
        project_id = self._get_job_project(job_id)
        self._require_owner(project_id, user_id)
        recalled = self._repo.recall_reviewer_assignments(
            job_id, reviewer_id, limit=count,
        )
        self._db.commit()
        return recalled

    def bulk_approve_review_queue(
        self, *, job_id: int, user_id: int, scope: str
    ) -> int:
        project_id = self._get_job_project(job_id)
        self._require_owner(project_id, user_id)
        now = datetime.utcnow()
        count = self._repo.bulk_approve_review_queue(
            job_id=job_id, owner_id=user_id, scope=scope, now=now
        )
        self._db.commit()
        return count

    # ------------------------------------------------------------------
    # Owner: 집계 (summary)
    # ------------------------------------------------------------------

    def get_assignment_summary(self, *, job_id: int, user_id: int) -> AssignmentSummaryDTO:
        project_id = self._get_job_project(job_id)
        self._require_owner(project_id, user_id)
        annotator_stats = self._repo.get_annotator_summary(job_id)
        reviewer_stats = self._repo.get_reviewer_summary(job_id)
        pool_stats = self._repo.get_pool_stats(job_id)
        return AssignmentSummaryDTO(
            annotator_stats=annotator_stats,
            reviewer_stats=reviewer_stats,
            pool_stats=pool_stats,
        )

    # ------------------------------------------------------------------
    # Upload job — 검토 요청 (내 할당 중 done → submitted 일괄)
    # ------------------------------------------------------------------

    def request_review_for_job(self, *, job_id: int, user_id: int) -> int:
        """이 업로드 작업 단위에서, 현재 사용자에게 할당된 done 상태만 검토 단계로 일괄 전환.

        - 이전 검토 반려(`reverted_by`)가 있으면: 동일 검토자에게 곧바로 ``review_assigned``.
        - 그 외: ``submitted``(리뷰어 미정) 후 owner 배정 필요.
        """
        from app.domains.uploads.repositories.upload_repository import UploadRepository

        upload_repo = UploadRepository(self._db)
        job = upload_repo.get_job(job_id)
        if job is None:
            raise AnnotationNotFoundError(f"upload job {job_id} not found")
        role = self._require_member(job.project_id, user_id)
        if role == "reviewer":
            raise AnnotationForbiddenError("reviewers cannot submit annotation jobs for review")
        if role not in ("annotator", "owner"):
            raise AnnotationForbiddenError("only annotators or owners can request review")
        now = datetime.utcnow()
        count = self._repo.bulk_transition_done_to_submitted_for_user(job_id, user_id, now)
        self._db.commit()
        return count
