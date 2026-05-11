import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.core.storage import StorageClient, get_storage_client
from app.db.session import get_db
from app.domains.oAuth.deps import get_current_user
from app.domains.projects.exceptions import (
    ClassDuplicateNameError,
    ClassHardDeleteNotAllowedError,
    ClassHasAnnotationsError,
    ClassNotFoundError,
    InvitationInvalidError,
    ModelForbiddenError,
    ModelNotFoundError,
    ProjectActiveUploadsError,
    ProjectDeleteNameMismatchError,
    ProjectForbiddenError,
    ProjectNotFoundError,
    ProjectStoragePurgeError,
)
from app.domains.projects.schemas.dtos import (
    AcceptInvitationBodyDTO,
    AddClassBodyDTO,
    ClassPathDTO,
    CreateInvitationBodyDTO,
    CreateInvitationResponse,
    CreateProjectBodyDTO,
    DeleteProjectBodyDTO,
    MlModelResponse,
    PatchClassBodyDTO,
    ProjectClassResponse,
    ProjectDetailResponse,
    ProjectMemberResponse,
    ProjectPathDTO,
    ProjectSummaryResponse,
    SelectModelBodyDTO,
)
from app.domains.projects.services.class_service import ClassService
from app.domains.projects.services.project_service import ProjectService
from app.models import User

router = APIRouter(prefix="/projects", tags=["projects"])
invitations_router = APIRouter(prefix="/project-invitations", tags=["project-invitations"])
classes_router = APIRouter(prefix="/classes", tags=["classes"])

_log = logging.getLogger(__name__)


def project_path(project_id: Annotated[int, Path(ge=1)]) -> ProjectPathDTO:
    return ProjectPathDTO(project_id=project_id)


def class_path(class_id: Annotated[int, Path(ge=1)]) -> ClassPathDTO:
    return ClassPathDTO(class_id=class_id)


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def get_class_service(
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage_client),
) -> ClassService:
    return ClassService(db, storage)


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="project_not_found")


def _forbidden() -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")


def _bad_invite() -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_or_expired_invitation")


def _class_not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="class_not_found")


def _class_duplicate() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail="class_name_already_exists")


def _class_hard_delete_forbidden() -> HTTPException:
    return HTTPException(
        status.HTTP_403_FORBIDDEN,
        detail="class_hard_delete_only_for_custom_classes",
    )


def _class_has_annotations() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail="class_has_annotations",
    )


@router.post(
    "/",
    response_model=ProjectSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    body: CreateProjectBodyDTO,
    user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> ProjectSummaryResponse:
    result = svc.create_project(
        user_id=user.id,
        name=body.name,
        description=body.description,
    )
    return ProjectSummaryResponse(
        id=result.id,
        name=result.name,
        description=result.description,
        created_at=result.created_at,
    )


@router.get("/owned", response_model=list[ProjectSummaryResponse])
def list_owned_projects(
    user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> list[ProjectSummaryResponse]:
    rows = svc.list_owned(user.id)
    return [
        ProjectSummaryResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/member", response_model=list[ProjectSummaryResponse])
def list_member_projects(
    user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> list[ProjectSummaryResponse]:
    rows = svc.list_member_non_owner(user.id)
    return [
        ProjectSummaryResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
)
def get_project(
    path: ProjectPathDTO = Depends(project_path),
    user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> ProjectDetailResponse:
    try:
        d = svc.get_project_for_member(path.project_id, user.id)
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    return ProjectDetailResponse(
        id=d.id,
        name=d.name,
        description=d.description,
        created_at=d.created_at,
        my_role=d.my_role,
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project(
    path: ProjectPathDTO = Depends(project_path),
    body: DeleteProjectBodyDTO = Body(...),
    user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
    storage: StorageClient = Depends(get_storage_client),
) -> None:
    """owner만 프로젝트를 삭제한다. 스토리지 `projects/{id}/` 선삭제 후 DB CASCADE."""
    try:
        deleted = svc.delete_project_as_owner(
            project_id=path.project_id,
            owner_user_id=user.id,
            confirm_name=body.confirm_name,
            storage=storage,
        )
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    except ProjectForbiddenError as exc:
        raise _forbidden() from exc
    except ProjectDeleteNameMismatchError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="project_delete_name_mismatch",
        ) from exc
    except ProjectActiveUploadsError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="project_has_active_uploads",
        ) from exc
    except ProjectStoragePurgeError as exc:
        _log.error("project storage purge failed: %s", exc.message, exc_info=True)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="project_storage_purge_failed",
        ) from exc

    if not deleted:
        pass  # idempotent: already gone → 204


@router.get(
    "/{project_id}/members",
    response_model=list[ProjectMemberResponse],
)
def list_project_members(
    path: ProjectPathDTO = Depends(project_path),
    user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> list[ProjectMemberResponse]:
    try:
        rows = svc.list_members(path.project_id, user.id)
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    except ProjectForbiddenError as exc:
        raise _forbidden() from exc
    return [
        ProjectMemberResponse(
            user_id=r.user_id,
            email=r.email,
            role=r.role,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post(
    "/{project_id}/invitations",
    response_model=CreateInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_invitation(
    body: CreateInvitationBodyDTO,
    path: ProjectPathDTO = Depends(project_path),
    user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> CreateInvitationResponse:
    try:
        result = svc.create_invitation(
            project_id=path.project_id,
            owner_user_id=user.id,
            role=body.role.value,
        )
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    except ProjectForbiddenError as exc:
        raise _forbidden() from exc
    return CreateInvitationResponse(
        invitation_id=result.invitation_id,
        token=result.token,
        join_url=result.join_url,
        expires_at=result.expires_at,
    )


@invitations_router.post(
    "/accept",
    response_model=ProjectDetailResponse,
)
def accept_project_invitation(
    body: AcceptInvitationBodyDTO,
    user: User = Depends(get_current_user),
    svc: ProjectService = Depends(get_project_service),
) -> ProjectDetailResponse:
    try:
        d = svc.accept_invitation(user_id=user.id, token=body.token)
    except InvitationInvalidError as exc:
        raise _bad_invite() from exc
    return ProjectDetailResponse(
        id=d.id,
        name=d.name,
        description=d.description,
        created_at=d.created_at,
        my_role=d.my_role,
    )


# ------------------------------------------------------------------
# 모델 목록 조회 / 선택
# ------------------------------------------------------------------


@router.get("/{project_id}/models", response_model=list[MlModelResponse])
def list_available_models(
    path: ProjectPathDTO = Depends(project_path),
    user: User = Depends(get_current_user),
    svc: ClassService = Depends(get_class_service),
) -> list[MlModelResponse]:
    """프로젝트 owner가 소유한 모델만 반환한다."""
    try:
        rows = svc.list_available_models(project_id=path.project_id, user_id=user.id)
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    return [
        MlModelResponse(
            id=r.id,
            name=r.name,
            version=r.version,
            framework=r.framework,
            file_path=r.file_path,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/{project_id}/model", response_model=MlModelResponse | None)
def get_selected_model(
    path: ProjectPathDTO = Depends(project_path),
    user: User = Depends(get_current_user),
    svc: ClassService = Depends(get_class_service),
) -> MlModelResponse | None:
    """프로젝트에 현재 선택된 모델을 반환한다."""
    try:
        r = svc.get_selected_model(project_id=path.project_id, user_id=user.id)
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    if r is None:
        return None
    return MlModelResponse(
        id=r.id,
        name=r.name,
        version=r.version,
        framework=r.framework,
        file_path=r.file_path,
        created_at=r.created_at,
    )


@router.put(
    "/{project_id}/model",
    response_model=MlModelResponse,
)
def select_model(
    body: SelectModelBodyDTO,
    path: ProjectPathDTO = Depends(project_path),
    user: User = Depends(get_current_user),
    svc: ClassService = Depends(get_class_service),
) -> MlModelResponse:
    """프로젝트에 사용할 모델을 선택한다 (owner 전용)."""
    try:
        r = svc.select_model(
            project_id=path.project_id,
            model_id=body.model_id,
            owner_user_id=user.id,
        )
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    except ProjectForbiddenError as exc:
        raise _forbidden() from exc
    except ModelNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="model_not_found") from exc
    except ModelForbiddenError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="model_forbidden") from exc
    return MlModelResponse(
        id=r.id,
        name=r.name,
        version=r.version,
        framework=r.framework,
        file_path=r.file_path,
        created_at=r.created_at,
    )


# ------------------------------------------------------------------
# project_classes
# ------------------------------------------------------------------


@router.get("/{project_id}/classes", response_model=list[ProjectClassResponse])
def list_classes(
    path: ProjectPathDTO = Depends(project_path),
    user: User = Depends(get_current_user),
    svc: ClassService = Depends(get_class_service),
    include_inactive: bool = Query(False, description="비활성 클래스 포함 (프로젝트 owner 전용)"),
) -> list[ProjectClassResponse]:
    try:
        rows = svc.list_classes(
            project_id=path.project_id,
            user_id=user.id,
            include_inactive=include_inactive,
        )
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    except ProjectForbiddenError as exc:
        raise _forbidden() from exc
    return [
        ProjectClassResponse(
            id=r.id,
            project_id=r.project_id,
            export_index=r.export_index,
            name=r.name,
            color=r.color,
            is_active=r.is_active,
            model_class_id=r.model_class_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post(
    "/{project_id}/classes",
    response_model=ProjectClassResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_class(
    body: AddClassBodyDTO,
    path: ProjectPathDTO = Depends(project_path),
    user: User = Depends(get_current_user),
    svc: ClassService = Depends(get_class_service),
) -> ProjectClassResponse:
    try:
        r = svc.add_class(
            project_id=path.project_id,
            owner_user_id=user.id,
            name=body.name,
            color=body.color,
        )
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    except ProjectForbiddenError as exc:
        raise _forbidden() from exc
    except ClassDuplicateNameError as exc:
        raise _class_duplicate() from exc
    return ProjectClassResponse(
        id=r.id,
        project_id=r.project_id,
        export_index=r.export_index,
        name=r.name,
        color=r.color,
        is_active=r.is_active,
        model_class_id=r.model_class_id,
        created_at=r.created_at,
    )


# ------------------------------------------------------------------
# /classes/{class_id} — top-level router (classes_router)
# ------------------------------------------------------------------


@classes_router.patch("/{class_id}", response_model=ProjectClassResponse)
def patch_class(
    body: PatchClassBodyDTO,
    path: ClassPathDTO = Depends(class_path),
    user: User = Depends(get_current_user),
    svc: ClassService = Depends(get_class_service),
) -> ProjectClassResponse:
    try:
        r = svc.rename_class(
            class_id=path.class_id,
            owner_user_id=user.id,
            name=body.name,
            color=body.color,
            is_active=body.is_active,
        )
    except ClassNotFoundError as exc:
        raise _class_not_found() from exc
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    except ProjectForbiddenError as exc:
        raise _forbidden() from exc
    except ClassDuplicateNameError as exc:
        raise _class_duplicate() from exc
    return ProjectClassResponse(
        id=r.id,
        project_id=r.project_id,
        export_index=r.export_index,
        name=r.name,
        color=r.color,
        is_active=r.is_active,
        model_class_id=r.model_class_id,
        created_at=r.created_at,
    )


@classes_router.delete(
    "/{class_id}",
    response_model=ProjectClassResponse,
)
def delete_class(
    path: ClassPathDTO = Depends(class_path),
    user: User = Depends(get_current_user),
    svc: ClassService = Depends(get_class_service),
) -> ProjectClassResponse:
    try:
        r = svc.deactivate_class(class_id=path.class_id, owner_user_id=user.id)
    except ClassNotFoundError as exc:
        raise _class_not_found() from exc
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    except ProjectForbiddenError as exc:
        raise _forbidden() from exc
    return ProjectClassResponse(
        id=r.id,
        project_id=r.project_id,
        export_index=r.export_index,
        name=r.name,
        color=r.color,
        is_active=r.is_active,
        model_class_id=r.model_class_id,
        created_at=r.created_at,
    )


@classes_router.delete(
    "/{class_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_class_permanent(
    path: ClassPathDTO = Depends(class_path),
    user: User = Depends(get_current_user),
    svc: ClassService = Depends(get_class_service),
) -> Response:
    """수동 추가 클래스(project_classes.model_class_id IS NULL)만 행 삭제. 모델 클래스는 403."""
    try:
        svc.delete_class_permanent(class_id=path.class_id, owner_user_id=user.id)
    except ClassNotFoundError as exc:
        raise _class_not_found() from exc
    except ClassHardDeleteNotAllowedError as exc:
        raise _class_hard_delete_forbidden() from exc
    except ClassHasAnnotationsError as exc:
        raise _class_has_annotations() from exc
    except ProjectNotFoundError as exc:
        raise _not_found() from exc
    except ProjectForbiddenError as exc:
        raise _forbidden() from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
