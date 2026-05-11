"""업로드 도메인 라우터."""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.storage import StorageClient, get_storage_client
from app.db.session import get_db
from app.domains.projects.exceptions import ModelForbiddenError, ModelNotFoundError
from app.domains.oAuth.deps import get_current_user
from app.domains.uploads.exceptions import (
    FileTooLargeError,
    ImageNotFoundError,
    InvalidZipFileError,
    UploadForbiddenError,
    UploadJobNotFoundError,
    UploadJobStoragePurgeError,
)
from app.domains.uploads.schemas.dtos import (
    AnnotationListResponse,
    AnnotationResponse,
    ImagePathDTO,
    ImageResponse,
    ProjectPathDTO,
    UploadJobPathDTO,
    UploadJobResponse,
)
from app.domains.uploads.services.upload_service import UploadJobDTO, UploadService
from app.models import User

project_uploads_router = APIRouter(prefix="/projects", tags=["uploads"])
upload_jobs_router = APIRouter(prefix="/upload-jobs", tags=["uploads"])
images_router = APIRouter(prefix="/images", tags=["images"])

_log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Dependency factories
# ------------------------------------------------------------------


def _project_path(project_id: Annotated[int, Path(ge=1)]) -> ProjectPathDTO:
    return ProjectPathDTO(project_id=project_id)


def _job_path(job_id: Annotated[int, Path(ge=1)]) -> UploadJobPathDTO:
    return UploadJobPathDTO(job_id=job_id)


def _image_path(image_id: Annotated[int, Path(ge=1)]) -> ImagePathDTO:
    return ImagePathDTO(image_id=image_id)


def get_upload_service(
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage_client),
) -> UploadService:
    return UploadService(db, storage)


# ------------------------------------------------------------------
# HTTP exception helpers
# ------------------------------------------------------------------


def _forbidden() -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")


def _job_not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="upload_job_not_found")


def _image_not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="image_not_found")


def _upload_job_to_response(j: UploadJobDTO) -> UploadJobResponse:
    return UploadJobResponse(
        id=j.id,
        project_id=j.project_id,
        uploaded_by=j.uploaded_by,
        upload_type=j.upload_type,
        status=j.status,
        original_file_name=j.original_file_name,
        total_count=j.total_count,
        processed_count=j.processed_count,
        skipped_count=j.skipped_count,
        error_message=j.error_message,
        created_at=j.created_at,
        completed_at=j.completed_at,
        auto_label_status=j.auto_label_status,
        auto_label_error=j.auto_label_error,
        cover_image_id=j.cover_image_id,
        image_count=j.image_count,
        done_count=j.done_count,
        in_progress_count=j.in_progress_count,
        annotate_tab_total_count=j.annotate_tab_total_count,
        annotate_assignment_total_count=j.annotate_assignment_total_count,
        annotate_approved_count=j.annotate_approved_count,
        review_pending_count=j.review_pending_count,
        review_approved_count=j.review_approved_count,
        done_without_reviewer_count=j.done_without_reviewer_count,
        review_queue_total=j.review_queue_total,
        review_queue_first_round=j.review_queue_first_round,
        review_queue_after_reject=j.review_queue_after_reject,
    )


# ------------------------------------------------------------------
# POST /projects/{project_id}/upload-jobs  — ZIP 업로드
# ------------------------------------------------------------------


@project_uploads_router.post(
    "/{project_id}/upload-jobs",
    response_model=UploadJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload_job(
    zip_file: UploadFile = File(...),
    model_id: int | None = Form(None),
    path: ProjectPathDTO = Depends(_project_path),
    user: User = Depends(get_current_user),
    svc: UploadService = Depends(get_upload_service),
) -> UploadJobResponse:
    file_bytes = await zip_file.read()
    filename = zip_file.filename or "upload.zip"
    try:
        result = svc.create_upload_job(
            project_id=path.project_id,
            user_id=user.id,
            filename=filename,
            file_bytes=file_bytes,
            model_id=model_id,
        )
    except UploadForbiddenError as exc:
        raise _forbidden() from exc
    except ModelNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="model_not_found") from exc
    except ModelForbiddenError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="model_forbidden") from exc
    except InvalidZipFileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    return _upload_job_to_response(result)


# ------------------------------------------------------------------
# GET /projects/{project_id}/upload-jobs  — 업로드 목록
# ------------------------------------------------------------------


@project_uploads_router.get(
    "/{project_id}/upload-jobs",
    response_model=list[UploadJobResponse],
)
def list_upload_jobs(
    path: ProjectPathDTO = Depends(_project_path),
    scope: Annotated[
        Literal["all", "annotate", "review"] | None,
        Query(description="목록 범위: owner=all|annotate|review, 참여자=annotate|review"),
    ] = None,
    user: User = Depends(get_current_user),
    svc: UploadService = Depends(get_upload_service),
) -> list[UploadJobResponse]:
    try:
        jobs = svc.list_upload_jobs(project_id=path.project_id, user_id=user.id, scope=scope)
    except UploadForbiddenError as exc:
        raise _forbidden() from exc
    return [_upload_job_to_response(j) for j in jobs]


@project_uploads_router.delete(
    "/{project_id}/upload-jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_upload_job(
    project_id: Annotated[int, Path(ge=1)],
    job_id: Annotated[int, Path(ge=1)],
    user: User = Depends(get_current_user),
    svc: UploadService = Depends(get_upload_service),
) -> None:
    """프로젝트 owner만 업로드 배치를 삭제한다. 스토리지 prefix 선삭제 후 DB CASCADE."""
    try:
        svc.delete_upload_job_as_owner(project_id=project_id, job_id=job_id, user_id=user.id)
    except UploadForbiddenError as exc:
        raise _forbidden() from exc
    except UploadJobNotFoundError as exc:
        raise _job_not_found() from exc
    except UploadJobStoragePurgeError as exc:
        _log.error("upload job storage purge failed: %s", exc.message, exc_info=True)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="upload_job_storage_purge_failed",
        ) from exc


# ------------------------------------------------------------------
# GET /upload-jobs/{job_id}  — 업로드 작업 상태 조회
# ------------------------------------------------------------------


@upload_jobs_router.get("/{job_id}", response_model=UploadJobResponse)
def get_upload_job(
    path: UploadJobPathDTO = Depends(_job_path),
    for_participant: Annotated[bool, Query(description="owner 참여 모드 등")] = False,
    participant_scope: Annotated[
        Literal["annotate", "review"] | None,
        Query(description="for_participant=true 일 때 annotate|review; review면 검토 큐 분해 포함"),
    ] = None,
    user: User = Depends(get_current_user),
    svc: UploadService = Depends(get_upload_service),
) -> UploadJobResponse:
    try:
        result = svc.get_upload_job(
            job_id=path.job_id,
            user_id=user.id,
            for_participant=for_participant,
            participant_scope=participant_scope,
        )
    except UploadJobNotFoundError as exc:
        raise _job_not_found() from exc
    except UploadForbiddenError as exc:
        raise _forbidden() from exc
    return _upload_job_to_response(result)


# ------------------------------------------------------------------
# GET /upload-jobs/{job_id}/images  — 업로드 단위 이미지 목록
# ------------------------------------------------------------------


@upload_jobs_router.get("/{job_id}/images", response_model=list[ImageResponse])
def list_images(
    path: UploadJobPathDTO = Depends(_job_path),
    for_participant: Annotated[bool, Query(description="owner 참여 모드")] = False,
    participant_scope: Annotated[
        Literal["annotate", "review"] | None,
        Query(description="owner+for_participant: annotate(어노테이터 뷰)|review(리뷰어 뷰), 기본 annotate"),
    ] = None,
    user: User = Depends(get_current_user),
    svc: UploadService = Depends(get_upload_service),
) -> list[ImageResponse]:
    try:
        images = svc.list_images(
            job_id=path.job_id,
            user_id=user.id,
            for_participant=for_participant,
            participant_scope=participant_scope,
        )
    except UploadJobNotFoundError as exc:
        raise _job_not_found() from exc
    except UploadForbiddenError as exc:
        raise _forbidden() from exc
    return [
        ImageResponse(
            id=i.id,
            project_id=i.project_id,
            upload_job_id=i.upload_job_id,
            file_name=i.file_name,
            width=i.width,
            height=i.height,
            created_at=i.created_at,
            assignment_id=i.assignment_id,
            assignment_status=i.assignment_status,
            assignment_reverted_by=i.assignment_reverted_by,
            annotation_count=i.annotation_count,
        )
        for i in images
    ]


# ------------------------------------------------------------------
# GET /images/{image_id}/annotations  — 이미지 어노테이션 목록
# ------------------------------------------------------------------


@images_router.get("/{image_id}/annotations", response_model=AnnotationListResponse)
def list_annotations(
    path: ImagePathDTO = Depends(_image_path),
    for_participant: Annotated[bool, Query(description="owner 참여 모드")] = False,
    participant_scope: Annotated[
        Literal["annotate", "review"] | None,
        Query(description="owner+for_participant: annotate|review"),
    ] = None,
    user: User = Depends(get_current_user),
    svc: UploadService = Depends(get_upload_service),
) -> AnnotationListResponse:
    try:
        anns = svc.list_annotations(
            image_id=path.image_id,
            user_id=user.id,
            for_participant=for_participant,
            participant_scope=participant_scope,
        )
    except ImageNotFoundError as exc:
        raise _image_not_found() from exc
    except UploadForbiddenError as exc:
        raise _forbidden() from exc
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
# GET /images/{image_id}/content  — 이미지 원본 스트림 (프록시)
# ------------------------------------------------------------------


@images_router.get("/{image_id}/content")
def get_image_content(
    path: ImagePathDTO = Depends(_image_path),
    for_participant: Annotated[bool, Query(description="owner 참여 모드")] = False,
    participant_scope: Annotated[
        Literal["annotate", "review"] | None,
        Query(description="owner+for_participant: annotate|review"),
    ] = None,
    user: User = Depends(get_current_user),
    svc: UploadService = Depends(get_upload_service),
) -> Response:
    try:
        data, mime = svc.get_image_content(
            image_id=path.image_id,
            user_id=user.id,
            for_participant=for_participant,
            participant_scope=participant_scope,
        )
    except ImageNotFoundError as exc:
        raise _image_not_found() from exc
    except UploadForbiddenError as exc:
        raise _forbidden() from exc
    return Response(content=data, media_type=mime)
