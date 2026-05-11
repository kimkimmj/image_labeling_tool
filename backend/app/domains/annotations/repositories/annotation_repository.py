"""어노테이션 도메인 DB 접근."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, case, cast, func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.models.ml_model import ProjectClass
from app.models.upload import Annotation, Image, ImageAssignment, assignment_status_db


_EDITABLE_STATUSES = {"assigned", "in_progress"}
# 검토자가 에디터에서 박스 수정·승인/반려 가능한 상태 (Done 큐 또는 검토 중)
_REVIEW_EDITABLE_STATUSES = frozenset({"review_assigned"})


@dataclass
class UserAssignmentStat:
    user_id: int
    assigned: int
    annotate_done_only: int = 0  # status == done (승인 요청 전 완료 표시만)
    review_requested: int = 0  # 어노테이터 행: submitted | review_assigned. 리뷰어 행: 미사용(0).
    approved: int = 0
    reverted: int = 0
    review_pending: int = 0  # 리뷰어 행: 승인 대기 = review_assigned
    annotate_wip: int = 0  # 어노테이터 행: assigned|in_progress|done|reverted
    annotate_recallable: int = 0  # owner 회수 대상: assigned|in_progress (리뷰어 행은 0)


class AnnotationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Image / Assignment helpers
    # ------------------------------------------------------------------

    def get_image(self, image_id: int) -> Image | None:
        return self._session.get(Image, image_id)

    def get_image_with_assignment(self, image_id: int) -> Image | None:
        stmt = (
            select(Image)
            .options(joinedload(Image.assignment))
            .where(Image.id == image_id)
        )
        return self._session.scalars(stmt).first()

    def get_assignment(self, assignment_id: int) -> ImageAssignment | None:
        return self._session.get(ImageAssignment, assignment_id)

    def get_assignment_for_image(self, image_id: int) -> ImageAssignment | None:
        stmt = select(ImageAssignment).where(ImageAssignment.image_id == image_id)
        return self._session.scalars(stmt).first()

    def bulk_transition_done_to_submitted_for_user(
        self, job_id: int, user_id: int, now: datetime
    ) -> int:
        """해당 job 안에서 내 할당 중 done 만 검토 파이프라인으로 일괄 전환.

        - 이전 검토 반려 기록(`reverted_by`)이 있으면: 동일 사용자에게 즉시 `review_assigned`로 재배정
          (별도 리뷰어 배정 없음).
        - 그 외: `submitted` + 리뷰어 미정 (기존대로 owner 가 배정).
        """
        subq = select(Image.id).where(Image.upload_job_id == job_id).scalar_subquery()
        has_prev = ImageAssignment.reverted_by.isnot(None)
        status_expr = cast(
            case((has_prev, "review_assigned"), else_="submitted"),
            assignment_status_db,
        )
        stmt = (
            update(ImageAssignment)
            .where(
                ImageAssignment.image_id.in_(subq),
                ImageAssignment.assigned_to == user_id,
                ImageAssignment.status == "done",
            )
            .values(
                status=status_expr,
                reviewer_id=case(
                    (has_prev, ImageAssignment.reverted_by),
                    else_=ImageAssignment.reviewer_id,
                ),
                submitted_at=now,
            )
            .execution_options(synchronize_session="fetch")
        )
        result = self._session.execute(stmt)
        return result.rowcount

    def list_my_assignments(self, user_id: int) -> list[ImageAssignment]:
        stmt = (
            select(ImageAssignment)
            .options(joinedload(ImageAssignment.image))
            .where(
                ImageAssignment.assigned_to == user_id,
                ImageAssignment.status != "approved",
            )
            .order_by(ImageAssignment.created_at.desc())
        )
        return list(self._session.scalars(stmt).unique().all())

    # ------------------------------------------------------------------
    # ProjectClass validation
    # ------------------------------------------------------------------

    def get_active_class_ids(self, project_id: int) -> set[int]:
        stmt = select(ProjectClass.id).where(
            ProjectClass.project_id == project_id,
            ProjectClass.is_active.is_(True),
        )
        return set(self._session.scalars(stmt).all())

    # ------------------------------------------------------------------
    # Annotation READ
    # ------------------------------------------------------------------

    def list_annotations(self, image_id: int) -> list[Annotation]:
        stmt = (
            select(Annotation)
            .where(
                Annotation.image_id == image_id,
                Annotation.is_deleted.is_(False),
            )
            .order_by(Annotation.id.asc())
        )
        return list(self._session.scalars(stmt).all())

    def get_annotation(self, annotation_id: int) -> Annotation | None:
        return self._session.get(Annotation, annotation_id)

    # ------------------------------------------------------------------
    # PUT  — 전체 교체
    # ------------------------------------------------------------------

    def replace_all(
        self,
        *,
        image_id: int,
        assignment_id: int,
        items: list[dict],
        user_id: int,
        now: datetime,
    ) -> list[Annotation]:
        """기존 annotation을 모두 soft delete하고 새 목록을 insert한다."""
        self._session.execute(
            update(Annotation)
            .where(
                Annotation.image_id == image_id,
                Annotation.is_deleted.is_(False),
            )
            .values(is_deleted=True, updated_by=user_id, updated_at=now)
        )
        self._session.flush()

        rows = [
            Annotation(
                image_id=image_id,
                assignment_id=assignment_id,
                class_id=item["class_id"],
                x=item["x"],
                y=item["y"],
                width=item["width"],
                height=item["height"],
                confidence=None,
                source="manual",
                created_by=user_id,
                updated_by=user_id,
                updated_at=now,
            )
            for item in items
        ]
        if rows:
            self._session.add_all(rows)
            self._session.flush()
        return rows

    # ------------------------------------------------------------------
    # PATCH create
    # ------------------------------------------------------------------

    def create_annotations(
        self,
        *,
        image_id: int,
        assignment_id: int,
        items: list[dict],
        user_id: int,
        now: datetime,
    ) -> list[Annotation]:
        rows = [
            Annotation(
                image_id=image_id,
                assignment_id=assignment_id,
                class_id=item["class_id"],
                x=item["x"],
                y=item["y"],
                width=item["width"],
                height=item["height"],
                confidence=None,
                source="manual",
                created_by=user_id,
                updated_by=user_id,
                updated_at=now,
            )
            for item in items
        ]
        if rows:
            self._session.add_all(rows)
            self._session.flush()
        return rows

    # ------------------------------------------------------------------
    # PATCH update
    # ------------------------------------------------------------------

    def update_annotations(
        self,
        *,
        image_id: int,
        items: list[dict],
        user_id: int,
        now: datetime,
    ) -> list[Annotation]:
        """items 각각에서 id를 찾아 해당 annotation의 좌표/class를 수정한다."""
        updated: list[Annotation] = []
        for item in items:
            ann = self._session.get(Annotation, item["id"])
            if ann is None or ann.image_id != image_id or ann.is_deleted:
                continue
            ann.class_id = item["class_id"]
            ann.x = item["x"]
            ann.y = item["y"]
            ann.width = item["width"]
            ann.height = item["height"]
            ann.source = "manual"
            ann.updated_by = user_id
            ann.updated_at = now
            updated.append(ann)
        self._session.flush()
        return updated

    # ------------------------------------------------------------------
    # PATCH delete
    # ------------------------------------------------------------------

    def delete_annotations(
        self,
        *,
        image_id: int,
        annotation_ids: list[int],
        user_id: int,
        now: datetime,
    ) -> int:
        """annotation_ids 에 해당하는 row 를 soft delete한다."""
        if not annotation_ids:
            return 0
        result = self._session.execute(
            update(Annotation)
            .where(
                Annotation.id.in_(annotation_ids),
                Annotation.image_id == image_id,
                Annotation.is_deleted.is_(False),
            )
            .values(is_deleted=True, updated_by=user_id, updated_at=now)
        )
        self._session.flush()
        return result.rowcount

    # ------------------------------------------------------------------
    # Assignment status
    # ------------------------------------------------------------------

    def update_assignment_status(
        self,
        *,
        assignment_id: int,
        status: str,
        now: datetime,
    ) -> ImageAssignment | None:
        assignment = self._session.get(ImageAssignment, assignment_id)
        if assignment is None:
            return None
        assignment.status = status
        if status == "submitted":
            assignment.submitted_at = now
        elif status == "done":
            assignment.submitted_at = None
        self._session.flush()
        return assignment

    # ------------------------------------------------------------------
    # Owner: annotator 할당 / 회수
    # ------------------------------------------------------------------

    def get_unassigned_images_for_job(self, job_id: int, limit: int) -> list[ImageAssignment]:
        """미할당(unassigned) ImageAssignment 를 최대 limit 개 반환한다."""
        subq = select(Image.id).where(Image.upload_job_id == job_id).scalar_subquery()
        stmt = (
            select(ImageAssignment)
            .where(
                ImageAssignment.image_id.in_(subq),
                ImageAssignment.status == "unassigned",
            )
            .order_by(ImageAssignment.image_id.asc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def assign_to_annotator(
        self,
        *,
        assignments: list[ImageAssignment],
        user_id: int,
        assigned_by: int,
    ) -> int:
        for a in assignments:
            a.assigned_to = user_id
            a.assigned_by = assigned_by
            a.status = "assigned"
        self._session.flush()
        return len(assignments)

    def recall_annotator_assignments(
        self, job_id: int, user_id: int, limit: int | None = None
    ) -> int:
        """미완료(assigned/in_progress) 상태의 할당을 회수해 unassigned 풀로 되돌린다.

        ``limit`` 가 있으면 해당 장수만(오름차순 image_id 기준), 없으면 전량.
        """
        subq = select(Image.id).where(Image.upload_job_id == job_id).scalar_subquery()
        id_sel = (
            select(ImageAssignment.id)
            .where(
                ImageAssignment.image_id.in_(subq),
                ImageAssignment.assigned_to == user_id,
                ImageAssignment.status.in_(["assigned", "in_progress"]),
            )
            .order_by(ImageAssignment.image_id.asc())
        )
        if limit is not None:
            id_sel = id_sel.limit(limit)
        stmt = (
            update(ImageAssignment)
            .where(ImageAssignment.id.in_(id_sel))
            .values(assigned_to=None, status="unassigned")
            .execution_options(synchronize_session="fetch")
        )
        result = self._session.execute(stmt)
        return result.rowcount

    # ------------------------------------------------------------------
    # Owner: reviewer 할당 / 회수
    # ------------------------------------------------------------------

    def get_submitted_pending_reviewer_for_job(self, job_id: int, limit: int) -> list[ImageAssignment]:
        """검토 요청(submitted) 상태이고 reviewer 가 아직 없는 할당을 최대 limit 개 반환한다."""
        subq = select(Image.id).where(Image.upload_job_id == job_id).scalar_subquery()
        stmt = (
            select(ImageAssignment)
            .where(
                ImageAssignment.image_id.in_(subq),
                ImageAssignment.status == "submitted",
                ImageAssignment.reviewer_id.is_(None),
            )
            .order_by(ImageAssignment.image_id.asc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def assign_to_reviewer(
        self,
        *,
        assignments: list[ImageAssignment],
        reviewer_id: int,
    ) -> int:
        for a in assignments:
            a.reviewer_id = reviewer_id
            a.status = "review_assigned"
        self._session.flush()
        return len(assignments)

    def recall_reviewer_assignments(
        self, job_id: int, reviewer_id: int, limit: int | None = None
    ) -> int:
        """review_assigned 상태를 회수해 submitted 로 되돌린다 (재검토 배정 가능).

        ``limit`` 가 있으면 해당 장수만(오름차순 image_id 기준), 없으면 전량.
        """
        subq = select(Image.id).where(Image.upload_job_id == job_id).scalar_subquery()
        id_sel = (
            select(ImageAssignment.id)
            .where(
                ImageAssignment.image_id.in_(subq),
                ImageAssignment.reviewer_id == reviewer_id,
                ImageAssignment.status == "review_assigned",
            )
            .order_by(ImageAssignment.image_id.asc())
        )
        if limit is not None:
            id_sel = id_sel.limit(limit)
        stmt = (
            update(ImageAssignment)
            .where(ImageAssignment.id.in_(id_sel))
            .values(reviewer_id=None, status="submitted")
            .execution_options(synchronize_session="fetch")
        )
        result = self._session.execute(stmt)
        return result.rowcount

    def bulk_approve_review_queue(
        self,
        *,
        job_id: int,
        owner_id: int,
        scope: str,
        now: datetime,
    ) -> int:
        """Owner 일괄 승인: 검토 대기(submitted·미배정) 및 선택적으로 review_assigned.

        scope: ``submitted_unassigned`` | ``include_review_assigned``
        승인 시 ``approved_by``·``reviewer_id`` 를 owner_id 로 기록한다.
        """
        subq = select(Image.id).where(Image.upload_job_id == job_id).scalar_subquery()
        if scope == "submitted_unassigned":
            match = and_(
                ImageAssignment.status == "submitted",
                ImageAssignment.reviewer_id.is_(None),
            )
        elif scope == "include_review_assigned":
            match = or_(
                and_(
                    ImageAssignment.status == "submitted",
                    ImageAssignment.reviewer_id.is_(None),
                ),
                ImageAssignment.status == "review_assigned",
            )
        else:
            raise ValueError(f"invalid bulk approve scope: {scope}")

        stmt = (
            update(ImageAssignment)
            .where(
                ImageAssignment.image_id.in_(subq),
                match,
            )
            .values(
                status="approved",
                reviewer_id=owner_id,
                approved_by=owner_id,
                approved_at=now,
                reviewed_at=now,
            )
            .execution_options(synchronize_session="fetch")
        )
        result = self._session.execute(stmt)
        return result.rowcount

    # ------------------------------------------------------------------
    # Reviewer: reverted (자동 어노테이터 복귀 포함)
    # ------------------------------------------------------------------

    def revert_assignment(
        self,
        *,
        assignment: ImageAssignment,
        reviewer_id: int,
        reason: str | None,
        now: datetime,
    ) -> ImageAssignment:
        """review_assigned 상태에서 검토 반려 처리.

        - reviewer_id 해제.
        - 할당 상태는 항상 reverted 로 두어 “반려” 큐·탭과 일치시킴(assigned_to 유지 시에도 동일).
        - 어노테이터는 reverted → in_progress 전환 후 다시 편집.
        """
        assignment.reverted_by = reviewer_id
        assignment.reverted_at = now
        assignment.revert_reason = reason
        assignment.reviewer_id = None
        assignment.status = "reverted"
        self._session.flush()
        return assignment

    def approve_assignment(
        self,
        *,
        assignment: ImageAssignment,
        reviewer_id: int,
        now: datetime,
    ) -> ImageAssignment:
        """review_assigned → approved 전환."""
        assignment.status = "approved"
        assignment.approved_by = reviewer_id
        assignment.approved_at = now
        assignment.reviewed_at = now
        self._session.flush()
        return assignment

    # ------------------------------------------------------------------
    # Summary (Owner 대시보드용)
    # ------------------------------------------------------------------

    def get_annotator_summary(self, job_id: int) -> list[UserAssignmentStat]:
        """upload_job 내 어노테이터별 집계를 반환한다."""
        subq = select(Image.id).where(Image.upload_job_id == job_id).scalar_subquery()
        stmt = (
            select(
                ImageAssignment.assigned_to.label("user_id"),
                func.count(ImageAssignment.id).label("assigned"),
                func.sum(case((ImageAssignment.status == "done", 1), else_=0)).label("annotate_done_only"),
                func.sum(
                    case(
                        (
                            ImageAssignment.status.in_(["submitted", "review_assigned"]),
                            1,
                        ),
                        else_=0,
                    )
                ).label("review_requested"),
                func.sum(
                    case((ImageAssignment.status == "approved", 1), else_=0)
                ).label("approved"),
                func.sum(
                    case((ImageAssignment.status == "reverted", 1), else_=0)
                ).label("reverted"),
                func.sum(
                    case(
                        (
                            ImageAssignment.status.in_(
                                ["assigned", "in_progress", "done", "reverted"],
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("annotate_wip"),
                func.sum(
                    case(
                        (
                            ImageAssignment.status.in_(["assigned", "in_progress"]),
                            1,
                        ),
                        else_=0,
                    )
                ).label("annotate_recallable"),
            )
            .where(
                ImageAssignment.image_id.in_(subq),
                ImageAssignment.assigned_to.isnot(None),
            )
            .group_by(ImageAssignment.assigned_to)
        )
        rows = self._session.execute(stmt).all()
        return [
            UserAssignmentStat(
                user_id=row.user_id,
                assigned=int(row.assigned),
                annotate_done_only=int(row.annotate_done_only or 0),
                review_requested=int(row.review_requested or 0),
                approved=int(row.approved or 0),
                reverted=int(row.reverted or 0),
                review_pending=0,
                annotate_wip=int(row.annotate_wip or 0),
                annotate_recallable=int(row.annotate_recallable or 0),
            )
            for row in rows
        ]

    def get_reviewer_summary(self, job_id: int) -> list[UserAssignmentStat]:
        """upload_job 내 리뷰어별 집계를 반환한다."""
        subq = select(Image.id).where(Image.upload_job_id == job_id).scalar_subquery()
        stmt = (
            select(
                ImageAssignment.reviewer_id.label("user_id"),
                func.count(ImageAssignment.id).label("assigned"),
                func.sum(
                    case((ImageAssignment.status == "approved", 1), else_=0)
                ).label("approved"),
                func.sum(
                    case((ImageAssignment.status == "reverted", 1), else_=0)
                ).label("reverted"),
                func.sum(
                    case((ImageAssignment.status == "review_assigned", 1), else_=0)
                ).label("review_pending"),
            )
            .where(
                ImageAssignment.image_id.in_(subq),
                ImageAssignment.reviewer_id.isnot(None),
            )
            .group_by(ImageAssignment.reviewer_id)
        )
        rows = self._session.execute(stmt).all()
        return [
            UserAssignmentStat(
                user_id=row.user_id,
                assigned=int(row.assigned),
                annotate_done_only=0,
                review_requested=0,
                approved=int(row.approved or 0),
                reverted=int(row.reverted or 0),
                review_pending=int(row.review_pending or 0),
                annotate_wip=0,
                annotate_recallable=0,
            )
            for row in rows
        ]

    def get_pool_stats(self, job_id: int) -> dict[str, int]:
        """풀 통계.

        - in_progress: 승인 요청 전(assigned | in_progress | reverted | done)
        - submitted / review_assigned / approved: 검토 파이프라인 단계별 장수
        """
        subq = select(Image.id).where(Image.upload_job_id == job_id).scalar_subquery()
        stmt = (
            select(
                func.count(ImageAssignment.id).label("total"),
                func.sum(case((ImageAssignment.status == "unassigned", 1), else_=0)).label("unassigned"),
                func.sum(
                    case(
                        (
                            ImageAssignment.status.in_(
                                ["assigned", "in_progress", "reverted", "done"]
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("in_progress"),
                func.sum(case((ImageAssignment.status == "submitted", 1), else_=0)).label("submitted"),
                func.sum(case((ImageAssignment.status == "review_assigned", 1), else_=0)).label(
                    "review_assigned"
                ),
                func.sum(
                    case(
                        (
                            and_(
                                ImageAssignment.status == "submitted",
                                ImageAssignment.reviewer_id.is_(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("review_unassigned_done"),
                func.sum(case((ImageAssignment.status == "approved", 1), else_=0)).label("approved"),
            )
            .where(ImageAssignment.image_id.in_(subq))
        )
        row = self._session.execute(stmt).first()
        if row is None:
            return {
                "total": 0,
                "unassigned": 0,
                "in_progress": 0,
                "submitted": 0,
                "review_assigned": 0,
                "review_unassigned_done": 0,
                "approved": 0,
            }
        return {
            "total": int(row.total or 0),
            "unassigned": int(row.unassigned or 0),
            "in_progress": int(row.in_progress or 0),
            "submitted": int(row.submitted or 0),
            "review_assigned": int(row.review_assigned or 0),
            "review_unassigned_done": int(row.review_unassigned_done or 0),
            "approved": int(row.approved or 0),
        }
