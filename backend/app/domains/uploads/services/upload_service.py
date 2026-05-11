"""업로드 도메인 비즈니스 로직."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.storage import StorageClient
from app.domains.projects.repositories.project_repository import ProjectRepository
from app.domains.uploads.exceptions import (
    ImageNotFoundError,
    InvalidZipFileError,
    UploadForbiddenError,
    UploadJobNotFoundError,
    UploadJobStoragePurgeError,
)
from app.domains.uploads.repositories.upload_repository import UploadRepository
from app.models.upload import Annotation, Image, UploadJob

_MAX_ZIP_BYTES = 500 * 1024 * 1024  # 500 MB

# 리뷰 스코프: 나에게 검토가 배정된 할당만 (검토 요청 submitted·리뷰 배정 review_assigned)
_REVIEW_SCOPE_VISIBLE_STATUSES = frozenset({"submitted", "review_assigned"})


def _safe_filename(filename: str) -> str:
    name = re.sub(r"[^\w.\-]", "_", filename.replace("/", "_").replace("\\", "_"))
    return name[:200] or "upload.zip"


@dataclass(frozen=True)
class UploadJobDTO:
    id: int
    project_id: int
    uploaded_by: int
    upload_type: str
    status: str
    original_file_name: str
    total_count: int | None
    processed_count: int | None
    skipped_count: int | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    auto_label_status: str | None = None
    auto_label_error: str | None = None
    cover_image_id: int | None = None
    image_count: int = 0  # 내 할당(approved 제외) 총장
    done_count: int = 0  # done+submitted+review_assigned
    in_progress_count: int = 0  # assigned+in_progress+reverted
    # 업로드 상세 필터「전체」와 동일: assigned|in_progress|done|reverted (submitted·review_assigned 제외)
    annotate_tab_total_count: int = 0
    # 내게 배정된 어노 슬롯 총(승인 포함); annotate 스코프에서만 채움
    annotate_assignment_total_count: int = 0
    # 최종 승인(approved) 할당 장수; annotate 스코프에서만 채움
    annotate_approved_count: int = 0
    # owner · scope=review 일 때만 채움
    review_pending_count: int | None = None
    review_approved_count: int | None = None
    done_without_reviewer_count: int | None = None
    # reviewer 참여 목록·상세(for_participant+review): 내 검토 큐 분해
    review_queue_total: int = 0
    review_queue_first_round: int = 0
    review_queue_after_reject: int = 0


@dataclass(frozen=True)
class ImageDTO:
    id: int
    project_id: int
    upload_job_id: int
    file_name: str
    file_path: str
    width: int
    height: int
    created_at: datetime
    assignment_id: int | None = None
    assignment_status: str | None = None
    # 반려자 id; 리뷰 큐 「최초 배정 vs 반려 후 재요청」 프론트 필터용 (없음이면 신규 경로 미적용 가능)
    assignment_reverted_by: int | None = None
    annotation_count: int = 0


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


def _to_job_dto(
    job: UploadJob,
    cover_image_id: int | None = None,
    label_stats: tuple[int, ...] | None = None,
    *,
    review_pending_count: int | None = None,
    review_approved_count: int | None = None,
    done_without_reviewer_count: int | None = None,
    review_queue_total: int = 0,
    review_queue_first_round: int = 0,
    review_queue_after_reject: int = 0,
) -> UploadJobDTO:
    skipped: int | None = None
    if job.total_count is not None and job.processed_count is not None:
        skipped = job.total_count - job.processed_count
    annotate_tab_total = (
        label_stats[3] if label_stats is not None and len(label_stats) >= 4 else 0
    )
    annotate_total_all = (
        label_stats[4] if label_stats is not None and len(label_stats) >= 5 else 0
    )
    annotate_approved = (
        max(0, annotate_total_all - int(label_stats[0]))
        if label_stats is not None and len(label_stats) >= 5
        else 0
    )
    return UploadJobDTO(
        id=job.id,
        project_id=job.project_id,
        uploaded_by=job.uploaded_by,
        upload_type=job.upload_type,
        status=job.status,
        original_file_name=job.original_file_name,
        total_count=job.total_count,
        processed_count=job.processed_count,
        skipped_count=skipped,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
        auto_label_status=job.auto_label_status,
        auto_label_error=job.auto_label_error,
        cover_image_id=cover_image_id,
        image_count=label_stats[0] if label_stats else 0,
        done_count=label_stats[1] if label_stats else 0,
        in_progress_count=label_stats[2] if label_stats else 0,
        annotate_tab_total_count=annotate_tab_total,
        annotate_assignment_total_count=annotate_total_all,
        annotate_approved_count=annotate_approved,
        review_pending_count=review_pending_count,
        review_approved_count=review_approved_count,
        done_without_reviewer_count=done_without_reviewer_count,
        review_queue_total=review_queue_total,
        review_queue_first_round=review_queue_first_round,
        review_queue_after_reject=review_queue_after_reject,
    )


def _to_image_dto(img: Image, annotation_count: int = 0) -> ImageDTO:
    assignment = img.assignment
    return ImageDTO(
        id=img.id,
        project_id=img.project_id,
        upload_job_id=img.upload_job_id,
        file_name=img.file_name,
        file_path=img.file_path,
        width=img.width,
        height=img.height,
        created_at=img.created_at,
        assignment_id=assignment.id if assignment else None,
        assignment_status=assignment.status if assignment else None,
        assignment_reverted_by=(assignment.reverted_by if assignment else None),
        annotation_count=annotation_count,
    )


def _to_annotation_dto(ann: Annotation) -> AnnotationDTO:
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


class UploadService:
    def __init__(self, db: Session, storage: StorageClient) -> None:
        self._db = db
        self._storage = storage
        self._uploads = UploadRepository(db)
        self._projects = ProjectRepository(db)

    def _image_visible_to_user(
        self,
        image: Image,
        user_id: int,
        role: str,
        *,
        for_participant: bool = False,
        participant_scope: str | None = None,
    ) -> bool:
        if role == "owner":
            if not for_participant:
                return True
            a = image.assignment
            if a is None or a.status == "unassigned":
                return False
            scope = participant_scope or "annotate"
            if scope == "review":
                return (
                    a.reviewer_id == user_id
                    and a.status in _REVIEW_SCOPE_VISIBLE_STATUSES
                )
            return a.assigned_to == user_id and a.status != "approved"
        a = image.assignment
        if a is None or a.status == "unassigned":
            return False
        if role == "annotator":
            return a.assigned_to == user_id and a.status != "approved"
        if role == "reviewer":
            scope = participant_scope or "annotate"
            if scope == "review":
                return (
                    a.reviewer_id == user_id
                    and a.status in _REVIEW_SCOPE_VISIBLE_STATUSES
                )
            return a.assigned_to == user_id and a.status != "approved"
        return False

    def _require_member(self, project_id: int, user_id: int) -> str:
        m = self._projects.get_membership(project_id, user_id)
        if m is None:
            raise UploadForbiddenError
        return m.role

    def create_upload_job(
        self,
        *,
        project_id: int,
        user_id: int,
        filename: str,
        file_bytes: bytes,
        model_id: int | None = None,
    ) -> UploadJobDTO:
        """ZIP 파일을 MinIO에 업로드하고 upload_jobs 행을 생성한 뒤 Celery 태스크를 디스패치한다."""
        role = self._require_member(project_id, user_id)
        if role != "owner":
            raise UploadForbiddenError

        if len(file_bytes) > _MAX_ZIP_BYTES:
            from app.domains.uploads.exceptions import FileTooLargeError

            raise FileTooLargeError(f"파일 크기 제한 초과: {len(file_bytes)} bytes")

        # 기본 ZIP 시그니처 확인 (PK\x03\x04)
        if not file_bytes[:4] == b"PK\x03\x04":
            raise InvalidZipFileError("올바른 ZIP 파일이 아닙니다.")

        if model_id is not None:
            from app.domains.projects.services.class_service import ClassService

            class_svc = ClassService(self._db, self._storage)
            class_svc.select_model(
                project_id=project_id,
                model_id=model_id,
                owner_user_id=user_id,
            )

        safe_name = _safe_filename(filename)

        # 임시로 job을 flush해 ID를 얻은 뒤 MinIO 경로에 사용
        job = self._uploads.create_job(
            project_id=project_id,
            uploaded_by=user_id,
            original_file_name=filename,
            original_file_path="",  # 아래에서 확정
        )
        self._db.flush()

        object_key = f"projects/{project_id}/uploads/{job.id}/original/{safe_name}"
        self._storage.upload_bytes(object_key, file_bytes, content_type="application/zip")

        job.original_file_path = object_key
        self._db.commit()
        self._db.refresh(job)

        # Celery 태스크 비동기 디스패치
        from app.tasks.upload_tasks import process_zip_upload

        process_zip_upload.delay(job.id)

        return _to_job_dto(job)

    def get_upload_job(
        self,
        *,
        job_id: int,
        user_id: int,
        for_participant: bool = False,
        participant_scope: str | None = None,
    ) -> UploadJobDTO:
        job = self._uploads.get_job(job_id)
        if job is None:
            raise UploadJobNotFoundError
        self._require_member(job.project_id, user_id)
        rq_total = rq_first = rq_after = 0
        scope = participant_scope or "annotate"
        if for_participant and scope == "review":
            bd = self._uploads.get_job_review_queue_breakdown_for_user([job_id], user_id)
            rq_total, rq_first, rq_after = bd.get(job_id, (0, 0, 0))
        return _to_job_dto(
            job,
            review_queue_total=rq_total,
            review_queue_first_round=rq_first,
            review_queue_after_reject=rq_after,
        )

    def list_upload_jobs(
        self,
        *,
        project_id: int,
        user_id: int,
        scope: str | None = None,
    ) -> list[UploadJobDTO]:
        """업로드 목록. scope: owner는 all(전체)·annotate(내 어노테이션 배정만)·review(파이프라인 요약); 참여자는 annotate|review."""
        role = self._require_member(project_id, user_id)
        jobs = self._uploads.list_jobs(project_id)

        if role == "annotator":
            if scope is not None and scope != "annotate":
                raise UploadForbiddenError
            eff = "annotate"
        elif role == "reviewer":
            if scope not in (None, "annotate", "review"):
                raise UploadForbiddenError
            eff = scope or "annotate"
        else:
            eff = scope or "all"

        if role == "owner":
            if eff == "all":
                job_ids = [j.id for j in jobs]
                cover_ids = self._uploads.get_cover_image_ids(job_ids)
                label_stats = self._uploads.get_job_label_stats(job_ids)
                return [
                    _to_job_dto(j, cover_image_id=cover_ids.get(j.id), label_stats=label_stats.get(j.id))
                    for j in jobs
                ]
            if eff == "annotate":
                # 어노테이션 탭: 업로드 소유자 전체가 아니라, 내게 어노테이션이 배정된 업로드만 (annotator 와 동일)
                id_set = set(self._uploads.get_job_ids_for_user_annotate(project_id, user_id))
                filtered = [j for j in jobs if j.id in id_set]
                job_ids = [j.id for j in filtered]
                cover_ids = self._uploads.get_cover_image_ids_for_user_annotate(job_ids, user_id)
                ann_stats = self._uploads.get_job_annotate_stats_for_user(job_ids, user_id)
                return [
                    _to_job_dto(
                        j,
                        cover_image_id=cover_ids.get(j.id),
                        label_stats=ann_stats.get(j.id),
                    )
                    for j in filtered
                ]
            # review — 업로드 단위별 검토 파이프라인 요약
            job_ids = [j.id for j in jobs]
            cover_ids = self._uploads.get_cover_image_ids(job_ids)
            rev_stats = self._uploads.get_job_review_pipeline_stats(job_ids)
            return [
                _to_job_dto(
                    j,
                    cover_image_id=cover_ids.get(j.id),
                    label_stats=None,
                    review_pending_count=rev_stats.get(j.id, (0, 0, 0))[0],
                    review_approved_count=rev_stats.get(j.id, (0, 0, 0))[1],
                    done_without_reviewer_count=None,
                )
                for j in jobs
            ]

        # annotator 또는 reviewer(annotate)
        if eff == "annotate":
            id_set = set(self._uploads.get_job_ids_for_user_annotate(project_id, user_id))
            filtered = [j for j in jobs if j.id in id_set]
            job_ids = [j.id for j in filtered]
            cover_ids = self._uploads.get_cover_image_ids_for_user_annotate(job_ids, user_id)
            ann_stats = self._uploads.get_job_annotate_stats_for_user(job_ids, user_id)
            return [
                _to_job_dto(
                    j,
                    cover_image_id=cover_ids.get(j.id),
                    label_stats=ann_stats.get(j.id),
                )
                for j in filtered
            ]

        # reviewer · review
        id_set = set(self._uploads.get_job_ids_for_user_review(project_id, user_id))
        filtered = [j for j in jobs if j.id in id_set]
        job_ids = [j.id for j in filtered]
        cover_ids = self._uploads.get_cover_image_ids_for_user_review(job_ids, user_id)
        rev_stats = self._uploads.get_job_review_stats_for_user(job_ids, user_id)
        rev_bd = self._uploads.get_job_review_queue_breakdown_for_user(job_ids, user_id)
        out: list[UploadJobDTO] = []
        for j in filtered:
            total, approved, pending = rev_stats.get(j.id, (0, 0, 0))
            rq_total, rq_first, rq_after = rev_bd.get(j.id, (0, 0, 0))
            out.append(
                _to_job_dto(
                    j,
                    cover_image_id=cover_ids.get(j.id),
                    label_stats=(total, approved, pending),
                    review_queue_total=rq_total,
                    review_queue_first_round=rq_first,
                    review_queue_after_reject=rq_after,
                )
            )
        return out

    def list_images(
        self,
        *,
        job_id: int,
        user_id: int,
        for_participant: bool = False,
        participant_scope: str | None = None,
    ) -> list[ImageDTO]:
        job = self._uploads.get_job(job_id)
        if job is None:
            raise UploadJobNotFoundError
        role = self._require_member(job.project_id, user_id)
        rows = self._uploads.list_images_for_job(job_id)

        result: list[ImageDTO] = []
        for img, ann_count in rows:
            a = img.assignment
            # owner: 전체(관리) 또는 참여자 모드(내 할당만 = annotator 와 동일)
            if role == "owner":
                if not for_participant:
                    result.append(_to_image_dto(img, ann_count))
                    continue
                scope = participant_scope or "annotate"
                if a is None or a.status == "unassigned":
                    continue
                if scope == "review":
                    if (
                        a.reviewer_id == user_id
                        and a.status in _REVIEW_SCOPE_VISIBLE_STATUSES
                    ):
                        result.append(_to_image_dto(img, ann_count))
                    continue
                if a.assigned_to == user_id and a.status != "approved":
                    result.append(_to_image_dto(img, ann_count))
                continue
            # unassigned는 비owner에게 미노출
            if a is None or a.status == "unassigned":
                continue
            # annotator: 할당된 이미지 중 검토 승인 전까지만 (approved는 큐에서 제외)
            if role == "annotator":
                if a.assigned_to == user_id and a.status != "approved":
                    result.append(_to_image_dto(img, ann_count))
                continue
            # reviewer: participant_scope — annotate(내 어노테이션 할당) | review(내 검토 큐만)
            if role == "reviewer":
                scope = participant_scope or "annotate"
                if scope == "review":
                    if (
                        a.reviewer_id == user_id
                        and a.status in _REVIEW_SCOPE_VISIBLE_STATUSES
                    ):
                        result.append(_to_image_dto(img, ann_count))
                elif a.assigned_to == user_id and a.status != "approved":
                    result.append(_to_image_dto(img, ann_count))
                continue

        return result

    def delete_upload_job_as_owner(
        self,
        *,
        project_id: int,
        job_id: int,
        user_id: int,
    ) -> bool:
        """owner 전용: 스토리지 `projects/{pid}/uploads/{job_id}/` 삭제 후 DB에서 작업·이미지 등 CASCADE 삭제.

        Returns:
            True if a row was deleted, False if the job was already absent (idempotent).

        Raises:
            UploadForbiddenError, UploadJobNotFoundError (job belongs to another project),
            UploadJobStoragePurgeError
        """
        role = self._require_member(project_id, user_id)
        if role != "owner":
            raise UploadForbiddenError

        job = self._uploads.get_job(job_id)
        if job is None:
            return False
        if job.project_id != project_id:
            raise UploadJobNotFoundError

        prefix = f"projects/{project_id}/uploads/{job_id}/"
        try:
            self._storage.delete_prefix(prefix)
        except Exception as exc:
            raise UploadJobStoragePurgeError(str(exc)) from exc

        try:
            self._uploads.delete_job(job_id)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        return True

    def get_image_content(
        self,
        *,
        image_id: int,
        user_id: int,
        for_participant: bool = False,
        participant_scope: str | None = None,
    ) -> tuple[bytes, str]:
        """이미지 바이트와 MIME type을 반환한다."""
        image = self._uploads.get_image_with_assignment(image_id)
        if image is None:
            raise ImageNotFoundError
        role = self._require_member(image.project_id, user_id)
        if not self._image_visible_to_user(
            image,
            user_id,
            role,
            for_participant=for_participant,
            participant_scope=participant_scope,
        ):
            raise UploadForbiddenError

        import os

        ext = os.path.splitext(image.file_name)[1].lower()
        _MIME: dict[str, str] = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
        }
        mime = _MIME.get(ext, "application/octet-stream")
        data = self._storage.get_bytes(image.file_path)
        return data, mime

    def list_annotations(
        self,
        *,
        image_id: int,
        user_id: int,
        for_participant: bool = False,
        participant_scope: str | None = None,
    ) -> list[AnnotationDTO]:
        image = self._uploads.get_image_with_assignment(image_id)
        if image is None:
            raise ImageNotFoundError
        role = self._require_member(image.project_id, user_id)
        if not self._image_visible_to_user(
            image,
            user_id,
            role,
            for_participant=for_participant,
            participant_scope=participant_scope,
        ):
            raise UploadForbiddenError
        anns = self._uploads.list_annotations_for_image(image_id)
        return [_to_annotation_dto(a) for a in anns]
