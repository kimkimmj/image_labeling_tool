"""프로젝트·멤버 DB 접근."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project, ProjectUser, User
from app.models.enums import ProjectRole


class ProjectRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_project(
        self,
        *,
        name: str,
        description: str | None,
        created_by: int,
    ) -> Project:
        project = Project(
            name=name,
            description=description,
            created_by=created_by,
            selected_model_id=None,
        )
        self._session.add(project)
        self._session.flush()
        return project

    def add_member(
        self,
        *,
        project_id: int,
        user_id: int,
        role: str,
        invited_by: int,
    ) -> ProjectUser:
        row = ProjectUser(
            project_id=project_id,
            user_id=user_id,
            role=role,
            invited_by=invited_by,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get_project(self, project_id: int) -> Project | None:
        return self._session.get(Project, project_id)

    def get_membership(self, project_id: int, user_id: int) -> ProjectUser | None:
        stmt = select(ProjectUser).where(
            ProjectUser.project_id == project_id,
            ProjectUser.user_id == user_id,
        )
        return self._session.scalar(stmt)

    def list_projects_owned_by(self, user_id: int) -> list[Project]:
        stmt = (
            select(Project)
            .join(ProjectUser)
            .where(
                ProjectUser.user_id == user_id,
                ProjectUser.role == "owner",
            )
            .order_by(Project.created_at.desc())
        )
        return list(self._session.scalars(stmt).unique().all())

    def list_projects_member_non_owner(self, user_id: int) -> list[Project]:
        stmt = (
            select(Project)
            .join(ProjectUser)
            .where(
                ProjectUser.user_id == user_id,
                ProjectUser.role != "owner",
            )
            .order_by(Project.created_at.desc())
        )
        return list(self._session.scalars(stmt).unique().all())

    def list_members_for_project(self, project_id: int) -> list[tuple[ProjectUser, User]]:
        stmt = (
            select(ProjectUser, User)
            .join(User, User.id == ProjectUser.user_id)
            .where(ProjectUser.project_id == project_id)
            .order_by(ProjectUser.created_at.asc())
        )
        return list(self._session.execute(stmt).all())

    def get_owner_user_id(self, project_id: int) -> int | None:
        """프로젝트 owner 멤버의 user_id. 없으면 None."""
        stmt = select(ProjectUser.user_id).where(
            ProjectUser.project_id == project_id,
            ProjectUser.role == ProjectRole.owner.value,
        )
        return self._session.scalar(stmt)

    def delete_project(self, project_id: int) -> None:
        """projects 행을 삭제한다. 없으면 무시. FK CASCADE는 DB에 위임."""
        row = self._session.get(Project, project_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()
