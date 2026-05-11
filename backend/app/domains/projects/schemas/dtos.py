"""프로젝트 API용 Pydantic 스키마."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProjectInvitationRole


class CreateProjectBodyDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(None, max_length=10_000)


class ProjectPathDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(..., ge=1)


class DeleteProjectBodyDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_name: str = Field(..., min_length=1, max_length=500)


class CreateInvitationBodyDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ProjectInvitationRole


class AcceptInvitationBodyDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., min_length=1, max_length=500)


class ProjectSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    created_at: datetime


class ProjectDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    created_at: datetime
    my_role: str


class ProjectMemberResponse(BaseModel):
    user_id: int
    email: str
    role: str
    created_at: datetime


class CreateInvitationResponse(BaseModel):
    invitation_id: int
    token: str
    join_url: str
    expires_at: datetime


# ------------------------------------------------------------------
# Model upload
# ------------------------------------------------------------------


class ClassPathDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_id: int = Field(..., ge=1)


class MlModelResponse(BaseModel):
    id: int
    name: str
    version: str | None = None
    framework: str
    file_path: str
    created_at: datetime


# ------------------------------------------------------------------
# project_classes
# ------------------------------------------------------------------


class ProjectClassResponse(BaseModel):
    id: int
    project_id: int
    export_index: int
    name: str
    color: str | None = None
    is_active: bool
    model_class_id: int | None = None
    created_at: datetime


class AddClassBodyDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    color: str | None = Field(None, max_length=50)


class PatchClassBodyDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=200)
    color: str | None = Field(None, max_length=50)
    is_active: bool | None = None


class SelectModelBodyDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: int = Field(..., ge=1)
