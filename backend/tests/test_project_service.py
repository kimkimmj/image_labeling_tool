"""ProjectService 초대·수락 단위 테스트 (리포지토리 목 주입)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.domains.projects.exceptions import InvitationInvalidError, ProjectForbiddenError
from app.domains.projects.services.project_service import ProjectService, _hash_token


def _utc_later(hours: int = 1) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=hours)


def _utc_earlier(hours: int = 1) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)


@patch("app.domains.projects.services.project_service.ProjectRepository")
@patch("app.domains.projects.services.project_service.InvitationRepository")
def test_accept_creates_member_and_marks_invitation(
    mock_inv_cls: MagicMock,
    mock_proj_cls: MagicMock,
) -> None:
    db = MagicMock()
    mock_inv = MagicMock()
    mock_inv_cls.return_value = mock_inv
    mock_proj = MagicMock()
    mock_proj_cls.return_value = mock_proj

    inv = MagicMock()
    inv.expires_at = _utc_later()
    inv.project_id = 10
    inv.role = "annotator"
    inv.invited_by = 2
    mock_inv.get_pending_by_token_hash.return_value = inv
    mock_proj.get_membership.return_value = None
    proj = MagicMock()
    proj.id = 10
    proj.name = "Demo"
    proj.description = None
    proj.created_at = inv.expires_at
    mock_proj.get_project.return_value = proj
    mem = MagicMock()
    mem.role = "annotator"
    mock_proj.get_membership.side_effect = [None, mem]

    svc = ProjectService(db)
    out = svc.accept_invitation(user_id=5, token="raw-token")

    assert out.id == 10
    assert out.my_role == "annotator"
    mock_proj.add_member.assert_called_once()
    mock_inv.mark_accepted.assert_called_once()
    db.commit.assert_called()


@patch("app.domains.projects.services.project_service.ProjectRepository")
@patch("app.domains.projects.services.project_service.InvitationRepository")
def test_accept_already_member_still_consumes_invite(
    mock_inv_cls: MagicMock,
    mock_proj_cls: MagicMock,
) -> None:
    db = MagicMock()
    mock_inv = MagicMock()
    mock_inv_cls.return_value = mock_inv
    mock_proj = MagicMock()
    mock_proj_cls.return_value = mock_proj

    inv = MagicMock()
    inv.expires_at = _utc_later()
    inv.project_id = 1
    inv.role = "reviewer"
    inv.invited_by = 2
    mock_inv.get_pending_by_token_hash.return_value = inv
    existing = MagicMock()
    existing.role = "annotator"
    mock_proj.get_membership.return_value = existing
    proj = MagicMock()
    proj.id = 1
    proj.name = "P"
    proj.description = None
    proj.created_at = inv.expires_at
    mock_proj.get_project.return_value = proj

    svc = ProjectService(db)
    out = svc.accept_invitation(user_id=3, token="tok")

    assert out.my_role == "annotator"
    mock_proj.add_member.assert_not_called()
    mock_inv.mark_accepted.assert_called_once()
    db.commit.assert_called()


@patch("app.domains.projects.services.project_service.ProjectRepository")
@patch("app.domains.projects.services.project_service.InvitationRepository")
def test_accept_rejects_expired(mock_inv_cls: MagicMock, mock_proj_cls: MagicMock) -> None:
    db = MagicMock()
    mock_inv = MagicMock()
    mock_inv_cls.return_value = mock_inv
    mock_proj_cls.return_value = MagicMock()

    inv = MagicMock()
    inv.expires_at = _utc_earlier()
    mock_inv.get_pending_by_token_hash.return_value = inv

    svc = ProjectService(db)
    with pytest.raises(InvitationInvalidError):
        svc.accept_invitation(user_id=1, token="x")


@patch("app.domains.projects.services.project_service.ProjectRepository")
@patch("app.domains.projects.services.project_service.InvitationRepository")
def test_accept_unknown_token(mock_inv_cls: MagicMock, mock_proj_cls: MagicMock) -> None:
    db = MagicMock()
    mock_inv = MagicMock()
    mock_inv_cls.return_value = mock_inv
    mock_inv.get_pending_by_token_hash.return_value = None
    mock_proj_cls.return_value = MagicMock()

    svc = ProjectService(db)
    with pytest.raises(InvitationInvalidError):
        svc.accept_invitation(user_id=1, token="nope")


@patch("app.domains.projects.services.project_service.ProjectRepository")
@patch("app.domains.projects.services.project_service.InvitationRepository")
def test_second_accept_after_consume_fails(
    mock_inv_cls: MagicMock,
    mock_proj_cls: MagicMock,
) -> None:
    db = MagicMock()
    mock_inv = MagicMock()
    mock_inv_cls.return_value = mock_inv
    mock_proj = MagicMock()
    mock_proj_cls.return_value = mock_proj

    inv = MagicMock()
    inv.expires_at = _utc_later()
    inv.project_id = 7
    inv.role = "annotator"
    inv.invited_by = 1
    mock_inv.get_pending_by_token_hash.return_value = inv
    mock_proj.get_membership.return_value = None
    proj = MagicMock()
    proj.id = 7
    proj.name = "X"
    proj.description = None
    proj.created_at = inv.expires_at
    mock_proj.get_project.return_value = proj
    mem = MagicMock()
    mem.role = "annotator"

    call_count = {"n": 0}

    def membership_side_effect(pid: int, uid: int):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return None
        return mem

    mock_proj.get_membership.side_effect = membership_side_effect

    svc = ProjectService(db)
    svc.accept_invitation(user_id=9, token="once")

    mock_inv.get_pending_by_token_hash.return_value = None
    with pytest.raises(InvitationInvalidError):
        svc.accept_invitation(user_id=9, token="once")


@patch("app.domains.projects.services.project_service.ProjectRepository")
@patch("app.domains.projects.services.project_service.InvitationRepository")
def test_create_project_adds_owner_row(mock_inv_cls: MagicMock, mock_proj_cls: MagicMock) -> None:
    db = MagicMock()
    mock_inv_cls.return_value = MagicMock()
    mock_proj = MagicMock()
    mock_proj_cls.return_value = mock_proj
    project = MagicMock()
    project.id = 100
    project.name = "New"
    project.description = None
    project.created_at = datetime.now(timezone.utc).replace(tzinfo=None)
    mock_proj.create_project.return_value = project

    svc = ProjectService(db)
    out = svc.create_project(user_id=42, name="New", description=None)

    assert out.id == 100
    mock_proj.create_project.assert_called_once()
    mock_proj.add_member.assert_called_once()
    call_kw = mock_proj.add_member.call_args.kwargs
    assert call_kw["user_id"] == 42
    assert call_kw["invited_by"] == 42
    assert call_kw["role"] == "owner"
    db.commit.assert_called_once()


def test_hash_token_stable() -> None:
    assert _hash_token("abc") == _hash_token("abc")
    assert _hash_token("a") != _hash_token("b")


@patch("app.domains.projects.services.project_service.ProjectRepository")
@patch("app.domains.projects.services.project_service.InvitationRepository")
def test_create_invitation_non_owner_forbidden(
    mock_inv_cls: MagicMock,
    mock_proj_cls: MagicMock,
) -> None:
    db = MagicMock()
    mock_inv_cls.return_value = MagicMock()
    mock_proj = MagicMock()
    mock_proj_cls.return_value = mock_proj
    mock_proj.get_membership.return_value = MagicMock(role="annotator")

    svc = ProjectService(db)
    with pytest.raises(ProjectForbiddenError):
        svc.create_invitation(project_id=1, owner_user_id=5, role="annotator")


@patch("app.domains.projects.services.project_service.ProjectRepository")
@patch("app.domains.projects.services.project_service.InvitationRepository")
def test_list_owned_delegates(mock_inv_cls: MagicMock, mock_proj_cls: MagicMock) -> None:
    db = MagicMock()
    mock_inv_cls.return_value = MagicMock()
    mock_proj = MagicMock()
    mock_proj_cls.return_value = mock_proj
    p = MagicMock()
    p.id = 1
    p.name = "A"
    p.description = None
    p.created_at = _utc_later()
    mock_proj.list_projects_owned_by.return_value = [p]

    svc = ProjectService(db)
    rows = svc.list_owned(99)
    assert len(rows) == 1 and rows[0].id == 1
    mock_proj.list_projects_owned_by.assert_called_once_with(99)


@patch("app.domains.projects.services.project_service.ProjectRepository")
@patch("app.domains.projects.services.project_service.InvitationRepository")
def test_list_member_non_owner_delegates(mock_inv_cls: MagicMock, mock_proj_cls: MagicMock) -> None:
    db = MagicMock()
    mock_inv_cls.return_value = MagicMock()
    mock_proj = MagicMock()
    mock_proj_cls.return_value = mock_proj
    mock_proj.list_projects_member_non_owner.return_value = []

    svc = ProjectService(db)
    assert svc.list_member_non_owner(3) == []
    mock_proj.list_projects_member_non_owner.assert_called_once_with(3)
