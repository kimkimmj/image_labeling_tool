from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domains.oAuth.deps import get_current_user
from app.domains.projects.exceptions import (
    InvitationInvalidError,
    ProjectForbiddenError,
    ProjectNotFoundError,
)
from app.domains.projects.schemas.dtos import (
    AcceptInvitationBodyDTO,
    CreateInvitationBodyDTO,
    CreateInvitationResponse,
    CreateProjectBodyDTO,
    ProjectDetailResponse,
    ProjectMemberResponse,
    ProjectPathDTO,
    ProjectSummaryResponse,
)
from app.domains.projects.services.project_service import ProjectService
from app.models import User

router = APIRouter(prefix="/projects", tags=["projects"])
invitations_router = APIRouter(prefix="/project-invitations", tags=["project-invitations"])


def project_path(project_id: Annotated[int, Path(ge=1)]) -> ProjectPathDTO:
    return ProjectPathDTO(project_id=project_id)


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="project_not_found")


def _forbidden() -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")


def _bad_invite() -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_or_expired_invitation")


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
