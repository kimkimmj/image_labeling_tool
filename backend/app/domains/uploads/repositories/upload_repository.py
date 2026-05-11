"""업로드·이미지·어노테이션 DB 접근."""

from __future__ import annotations

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.upload import Annotation, Image, ImageAssignment, UploadJob


class UploadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # UploadJob
    # ------------------------------------------------------------------

    def create_job(
        self,
        *,
        project_id: int,
        uploaded_by: int,
        original_file_name: str,
        original_file_path: str,
    ) -> UploadJob:
        job = UploadJob(
            project_id=project_id,
            uploaded_by=uploaded_by,
            upload_type="image_zip",
            status="pending",
            original_file_name=original_file_name,
            original_file_path=original_file_path,
        )
        self._session.add(job)
        self._session.flush()
        return job

    def get_job(self, job_id: int) -> UploadJob | None:
        return self._session.get(UploadJob, job_id)

    def delete_job(self, job_id: int) -> None:
        job = self.get_job(job_id)
        if job is not None:
            self._session.delete(job)

    def list_jobs(self, project_id: int) -> list[UploadJob]:
        stmt = (
            select(UploadJob)
            .where(UploadJob.project_id == project_id)
            .order_by(UploadJob.created_at.desc())
        )
        return list(self._session.scalars(stmt).all())

    def count_active_upload_jobs(self, project_id: int) -> int:
        """status 가 pending 또는 processing 인 upload_job 개수."""
        stmt = (
            select(func.count())
            .select_from(UploadJob)
            .where(
                UploadJob.project_id == project_id,
                UploadJob.status.in_(("pending", "processing")),
            )
        )
        return int(self._session.scalar(stmt) or 0)

    # ------------------------------------------------------------------
    # Image
    # ------------------------------------------------------------------

    def list_images_for_job(self, job_id: int) -> list[tuple[Image, int]]:
        """(Image, annotation_count) 튜플 목록을 반환한다.

        assignment는 joinedload, annotation 수는 서브쿼리로 N+1 없이 처리한다.
        """
        ann_count_subq = (
            select(
                Annotation.image_id,
                func.count(Annotation.id).label("ann_count"),
            )
            .where(Annotation.is_deleted.is_(False))
            .group_by(Annotation.image_id)
            .subquery()
        )

        stmt = (
            select(Image, func.coalesce(ann_count_subq.c.ann_count, 0).label("ann_count"))
            .options(joinedload(Image.assignment))
            .outerjoin(ann_count_subq, ann_count_subq.c.image_id == Image.id)
            .where(Image.upload_job_id == job_id)
            .order_by(Image.id.asc())
        )
        rows = self._session.execute(stmt).all()
        return [(row.Image, int(row.ann_count)) for row in rows]

    def get_job_label_stats(self, job_ids: list[int]) -> dict[int, tuple[int, int, int]]:
        """각 job의 (total_images, done_count, in_progress_count) 를 반환한다.

        done: done / submitted / review_assigned / approved (라벨링 완료·검토 파이프라인)
        in_progress: assigned / in_progress
        """
        if not job_ids:
            return {}
        stmt = (
            select(
                Image.upload_job_id,
                func.count(Image.id).label("total"),
                func.sum(
                    case(
                        (ImageAssignment.status.in_(["done", "submitted", "review_assigned", "approved"]), 1),
                        else_=0,
                    )
                ).label("done"),
                func.sum(
                    case(
                        (ImageAssignment.status.in_(["assigned", "in_progress"]), 1),
                        else_=0,
                    )
                ).label("in_prog"),
            )
            .outerjoin(ImageAssignment, ImageAssignment.image_id == Image.id)
            .where(Image.upload_job_id.in_(job_ids))
            .group_by(Image.upload_job_id)
        )
        return {
            row.upload_job_id: (int(row.total), int(row.done or 0), int(row.in_prog or 0))
            for row in self._session.execute(stmt).all()
        }

    def get_cover_image_ids(self, job_ids: list[int]) -> dict[int, int]:
        """각 job의 가장 id가 작은 이미지 id를 {job_id: image_id} 로 반환한다."""
        if not job_ids:
            return {}
        stmt = (
            select(Image.upload_job_id, func.min(Image.id).label("first_id"))
            .where(Image.upload_job_id.in_(job_ids))
            .group_by(Image.upload_job_id)
        )
        return {row.upload_job_id: row.first_id for row in self._session.execute(stmt).all()}

    def get_job_ids_for_user_annotate(self, project_id: int, user_id: int) -> list[int]:
        """어노테이터로 할당된 이미지가 하나라도 있는 upload_job id 목록 (승인 완료 제외)."""
        stmt = (
            select(Image.upload_job_id)
            .join(ImageAssignment, ImageAssignment.image_id == Image.id)
            .where(
                Image.project_id == project_id,
                ImageAssignment.assigned_to == user_id,
                ImageAssignment.status != "approved",
            )
            .distinct()
        )
        return list(self._session.scalars(stmt).all())

    def get_job_ids_for_user_review(self, project_id: int, user_id: int) -> list[int]:
        """리뷰어로 지정된 이미지가 하나라도 있는 upload_job id 목록."""
        stmt = (
            select(Image.upload_job_id)
            .join(ImageAssignment, ImageAssignment.image_id == Image.id)
            .where(
                Image.project_id == project_id,
                ImageAssignment.reviewer_id == user_id,
            )
            .distinct()
        )
        return list(self._session.scalars(stmt).all())

    def get_cover_image_ids_for_user_annotate(self, job_ids: list[int], user_id: int) -> dict[int, int]:
        """각 job에서 해당 유저에게 할당된 이미지 중 id가 가장 작은 것 (승인 완료 제외)."""
        if not job_ids:
            return {}
        stmt = (
            select(Image.upload_job_id, func.min(Image.id).label("first_id"))
            .join(ImageAssignment, ImageAssignment.image_id == Image.id)
            .where(
                Image.upload_job_id.in_(job_ids),
                ImageAssignment.assigned_to == user_id,
                ImageAssignment.status != "approved",
            )
            .group_by(Image.upload_job_id)
        )
        return {row.upload_job_id: row.first_id for row in self._session.execute(stmt).all()}

    def get_cover_image_ids_for_user_review(self, job_ids: list[int], user_id: int) -> dict[int, int]:
        """각 job에서 해당 유저에게 검토 배정된 이미지 중 id가 가장 작은 것."""
        if not job_ids:
            return {}
        stmt = (
            select(Image.upload_job_id, func.min(Image.id).label("first_id"))
            .join(ImageAssignment, ImageAssignment.image_id == Image.id)
            .where(
                Image.upload_job_id.in_(job_ids),
                ImageAssignment.reviewer_id == user_id,
            )
            .group_by(Image.upload_job_id)
        )
        return {row.upload_job_id: row.first_id for row in self._session.execute(stmt).all()}

    def get_job_annotate_stats_for_user(self, job_ids: list[int], user_id: int) -> dict[int, tuple[int, int, int, int, int]]:
        """각 job별 (
            승인 제외 할당 장수(image_count 큐),
            파이프라인 완료 뭉텅이,
            진행 중 뭉텅이,
            상세 페이지 탭합,
            내게 배정된 어노 슬롯 총(승인 포함),
        )."""
        if not job_ids:
            return {}
        non_approved = ImageAssignment.status != "approved"
        stmt = (
            select(
                Image.upload_job_id,
                func.sum(case((non_approved, 1), else_=0)).label("total_excl_approved"),
                func.sum(
                    case(
                        (
                            and_(
                                non_approved,
                                ImageAssignment.status.in_(["done", "submitted", "review_assigned"]),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("done_bucket"),
                func.sum(
                    case(
                        (
                            and_(
                                non_approved,
                                ImageAssignment.status.in_(["assigned", "in_progress", "reverted"]),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("wip"),
                func.sum(
                    case(
                        (
                            and_(
                                non_approved,
                                ImageAssignment.status.in_(["assigned", "in_progress", "done", "reverted"]),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("tab_union"),
                func.count(ImageAssignment.id).label("total_all_statuses"),
            )
            .join(ImageAssignment, ImageAssignment.image_id == Image.id)
            .where(
                Image.upload_job_id.in_(job_ids),
                ImageAssignment.assigned_to == user_id,
            )
            .group_by(Image.upload_job_id)
        )
        return {
            row.upload_job_id: (
                int(row.total_excl_approved or 0),
                int(row.done_bucket or 0),
                int(row.wip or 0),
                int(row.tab_union or 0),
                int(row.total_all_statuses),
            )
            for row in self._session.execute(stmt).all()
        }

    def get_job_review_stats_for_user(self, job_ids: list[int], user_id: int) -> dict[int, tuple[int, int, int]]:
        """각 job별 (내 리뷰 배정 총장, 승인 장수, 검토 대기 review_assigned 장수)."""
        if not job_ids:
            return {}
        stmt = (
            select(
                Image.upload_job_id,
                func.count(ImageAssignment.id).label("total"),
                func.sum(case((ImageAssignment.status == "approved", 1), else_=0)).label("approved"),
                func.sum(case((ImageAssignment.status == "review_assigned", 1), else_=0)).label("pending"),
            )
            .join(ImageAssignment, ImageAssignment.image_id == Image.id)
            .where(
                Image.upload_job_id.in_(job_ids),
                ImageAssignment.reviewer_id == user_id,
            )
            .group_by(Image.upload_job_id)
        )
        return {
            row.upload_job_id: (int(row.total), int(row.approved or 0), int(row.pending or 0))
            for row in self._session.execute(stmt).all()
        }

    def get_job_review_queue_breakdown_for_user(
        self, job_ids: list[int], user_id: int
    ) -> dict[int, tuple[int, int, int]]:
        """각 job별 (내게 배정된 검토 큐 합계, 최초 배정만, 반려 후 재요청).

        큐는 reviewer_id=user 이고 status in (submitted, review_assigned).
        최초 배정분은 reverted_by IS NULL, 반려 후 재요청은 reverted_by IS NOT NULL.
        """
        if not job_ids:
            return {}
        in_queue = and_(
            ImageAssignment.reviewer_id == user_id,
            ImageAssignment.status.in_(["submitted", "review_assigned"]),
        )
        stmt = (
            select(
                Image.upload_job_id,
                func.sum(case((in_queue, 1), else_=0)).label("total_q"),
                func.sum(
                    case(
                        (
                            and_(
                                in_queue,
                                ImageAssignment.reverted_by.is_(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("first_round"),
                func.sum(
                    case(
                        (
                            and_(in_queue, ImageAssignment.reverted_by.isnot(None)),
                            1,
                        ),
                        else_=0,
                    )
                ).label("after_reject"),
            )
            .join(ImageAssignment, ImageAssignment.image_id == Image.id)
            .where(Image.upload_job_id.in_(job_ids))
            .group_by(Image.upload_job_id)
        )
        return {
            row.upload_job_id: (
                int(row.total_q or 0),
                int(row.first_round or 0),
                int(row.after_reject or 0),
            )
            for row in self._session.execute(stmt).all()
        }

    def get_job_review_pipeline_stats(self, job_ids: list[int]) -> dict[int, tuple[int, int, int]]:
        """각 job별 (review_assigned 장수, approved 장수, submitted·리뷰어 미배정 장수)."""
        if not job_ids:
            return {}
        stmt = (
            select(
                Image.upload_job_id,
                func.sum(case((ImageAssignment.status == "review_assigned", 1), else_=0)).label("rp"),
                func.sum(case((ImageAssignment.status == "approved", 1), else_=0)).label("ap"),
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
                ).label("dn"),
            )
            .join(ImageAssignment, ImageAssignment.image_id == Image.id)
            .where(Image.upload_job_id.in_(job_ids))
            .group_by(Image.upload_job_id)
        )
        return {
            row.upload_job_id: (int(row.rp or 0), int(row.ap or 0), int(row.dn or 0))
            for row in self._session.execute(stmt).all()
        }

    def get_image_with_assignment(self, image_id: int) -> Image | None:
        stmt = (
            select(Image)
            .options(joinedload(Image.assignment))
            .where(Image.id == image_id)
        )
        return self._session.scalars(stmt).first()

    def get_image(self, image_id: int) -> Image | None:
        return self._session.get(Image, image_id)

    # ------------------------------------------------------------------
    # Annotation
    # ------------------------------------------------------------------

    def list_annotations_for_image(self, image_id: int) -> list[Annotation]:
        stmt = (
            select(Annotation)
            .where(
                Annotation.image_id == image_id,
                Annotation.is_deleted.is_(False),
            )
            .order_by(Annotation.id.asc())
        )
        return list(self._session.scalars(stmt).all())
