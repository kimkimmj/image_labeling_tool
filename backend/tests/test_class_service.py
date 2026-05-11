"""ClassService 단위 테스트 (리포지토리·스토리지·파서 목 주입)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.yolo_parser import InvalidYoloModelError
from app.domains.projects.exceptions import (
    ClassDuplicateNameError,
    ClassHardDeleteNotAllowedError,
    ClassHasAnnotationsError,
    ClassNotFoundError,
    ProjectForbiddenError,
    ProjectNotFoundError,
)
from app.domains.projects.services.class_service import ClassService


def _make_service() -> tuple[ClassService, MagicMock, MagicMock, MagicMock, MagicMock]:
    """ClassService와 목 db, storage, project_repo, class_repo를 반환한다."""
    db = MagicMock()
    storage = MagicMock()

    with (
        patch("app.domains.projects.services.class_service.ProjectRepository") as proj_cls,
        patch("app.domains.projects.services.class_service.ClassRepository") as class_cls,
    ):
        mock_proj = MagicMock()
        mock_cls = MagicMock()
        proj_cls.return_value = mock_proj
        class_cls.return_value = mock_cls

        svc = ClassService(db, storage)
        svc._projects = mock_proj
        svc._classes = mock_cls
        svc._storage = storage

    return svc, db, storage, mock_proj, mock_cls


# ------------------------------------------------------------------
# 권한 체크
# ------------------------------------------------------------------


def test_select_model_raises_not_found_if_not_member() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mock_proj.get_membership.return_value = None

    with pytest.raises(ProjectNotFoundError):
        svc.select_model(project_id=1, model_id=10, owner_user_id=99)


def test_select_model_raises_forbidden_if_not_owner() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "annotator"
    mock_proj.get_membership.return_value = mem

    with pytest.raises(ProjectForbiddenError):
        svc.select_model(project_id=1, model_id=10, owner_user_id=5)


def test_add_class_raises_forbidden_for_non_owner() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "reviewer"
    mock_proj.get_membership.return_value = mem

    with pytest.raises(ProjectForbiddenError):
        svc.add_class(project_id=1, owner_user_id=5, name="cat", color=None)


def test_add_class_raises_not_found_if_no_membership() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mock_proj.get_membership.return_value = None

    with pytest.raises(ProjectNotFoundError):
        svc.add_class(project_id=1, owner_user_id=5, name="cat", color=None)


# ------------------------------------------------------------------
# 중복 이름 방어
# ------------------------------------------------------------------


def test_add_class_raises_duplicate_name() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "owner"
    mock_proj.get_membership.return_value = mem
    mock_cls.name_exists.return_value = True

    with pytest.raises(ClassDuplicateNameError) as exc_info:
        svc.add_class(project_id=1, owner_user_id=5, name="dog", color=None)

    assert exc_info.value.name == "dog"


def test_rename_class_raises_duplicate_name() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "owner"
    mock_proj.get_membership.return_value = mem

    existing_class = MagicMock()
    existing_class.id = 7
    existing_class.name = "cat"
    existing_class.project_id = 1
    mock_cls.get_project_class.return_value = existing_class
    mock_cls.name_exists.return_value = True

    with pytest.raises(ClassDuplicateNameError):
        svc.rename_class(class_id=7, owner_user_id=5, name="dog", color=None)


# ------------------------------------------------------------------
# export_index 안정성 — soft delete 후 재사용 없음
# ------------------------------------------------------------------


def test_export_index_increases_monotonically() -> None:
    """_next_export_index 는 항상 max+1 을 반환하며 inactive 포함 이전 인덱스를 재사용하지 않는다."""
    from app.domains.projects.repositories.class_repository import ClassRepository

    session = MagicMock()
    repo = ClassRepository(session)

    # max = 2 인 상황 시뮬레이션
    session.scalar.return_value = 2
    assert repo._next_export_index(project_id=1) == 3

    # 아무 클래스도 없는 경우 — 0-9 를 모델용으로 예약해 10 에서 시작한다
    session.scalar.return_value = None
    assert repo._next_export_index(project_id=1) == 10


# ------------------------------------------------------------------
# deactivate
# ------------------------------------------------------------------


def test_deactivate_class_sets_is_active_false() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "owner"
    mock_proj.get_membership.return_value = mem

    cls_row = MagicMock()
    cls_row.id = 3
    cls_row.project_id = 1
    cls_row.is_active = True
    mock_cls.get_project_class.return_value = cls_row

    svc.deactivate_class(class_id=3, owner_user_id=5)

    assert cls_row.is_active is False
    db.commit.assert_called_once()


def test_deactivate_class_raises_not_found() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mock_cls.get_project_class.return_value = None

    with pytest.raises(ClassNotFoundError):
        svc.deactivate_class(class_id=999, owner_user_id=5)


# ------------------------------------------------------------------
# YOLO 파서 검증
# ------------------------------------------------------------------


def test_invalid_extension_raises_error() -> None:
    from app.core.yolo_parser import parse_yolo_pt

    with pytest.raises(InvalidYoloModelError, match=".pt"):
        parse_yolo_pt(b"dummy", "model.onnx")


def test_non_detect_task_raises_error() -> None:
    """task != 'detect' 이면 InvalidYoloModelError."""
    import sys
    from unittest.mock import MagicMock

    mock_model = MagicMock()
    mock_model.task = "segment"
    mock_model.names = {0: "cat"}

    mock_yolo_cls = MagicMock(return_value=mock_model)
    fake_ultralytics = MagicMock()
    fake_ultralytics.YOLO = mock_yolo_cls

    with patch.dict(sys.modules, {"ultralytics": fake_ultralytics}):
        from app.core import yolo_parser

        with patch("app.core.yolo_parser.tempfile") as mock_tmp:
            tmp_file = MagicMock()
            tmp_file.name = "/tmp/fake.pt"
            mock_tmp.NamedTemporaryFile.return_value.__enter__ = MagicMock(return_value=tmp_file)
            mock_tmp.NamedTemporaryFile.return_value.__exit__ = MagicMock(return_value=False)

            with patch("builtins.open", MagicMock()):
                with pytest.raises(InvalidYoloModelError, match="detect"):
                    yolo_parser.parse_yolo_pt(b"data", "model.pt")


# ------------------------------------------------------------------
# 모델 선택 — project_classes 자동 생성 + 초기 색상
# ------------------------------------------------------------------


def test_select_model_creates_project_classes_with_colors() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "owner"
    mock_proj.get_membership.return_value = mem
    mock_proj.get_owner_user_id.return_value = 5

    ml_model = MagicMock()
    ml_model.id = 10
    ml_model.owner_id = 5
    mock_cls.get_model.return_value = ml_model

    mc0 = MagicMock()
    mc0.class_index = 0
    mc0.name = "cat"
    mc0.id = 1
    mc1 = MagicMock()
    mc1.class_index = 1
    mc1.name = "dog"
    mc1.id = 2
    mock_cls.list_model_classes.return_value = [mc0, mc1]
    mock_cls.get_taken_export_indices.return_value = set()
    mock_cls.get_taken_names.return_value = set()

    svc.select_model(project_id=1, model_id=10, owner_user_id=5)

    mock_cls.bulk_create_project_classes.assert_called_once()
    entries = mock_cls.bulk_create_project_classes.call_args.kwargs["entries"]
    assert [e[0] for e in entries] == [0, 1]
    for e in entries:
        assert len(e) == 4
        col = e[3]
        assert isinstance(col, str) and col.startswith("#") and len(col) == 7
    mock_cls.update_project_model.assert_called_once_with(1, 10)
    db.commit.assert_called_once()


def test_select_model_skips_conflicting_classes() -> None:
    """모델 클래스 index 또는 name 이 이미 project_classes 에 있으면 해당 항목만 건너뛴다."""
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "owner"
    mock_proj.get_membership.return_value = mem
    mock_proj.get_owner_user_id.return_value = 5

    ml_model = MagicMock()
    ml_model.id = 20
    ml_model.owner_id = 5
    mock_cls.get_model.return_value = ml_model

    mc0 = MagicMock()
    mc0.class_index = 0
    mc0.name = "person"
    mc0.id = 1
    mc1 = MagicMock()
    mc1.class_index = 1
    mc1.name = "car"
    mc1.id = 2
    mock_cls.list_model_classes.return_value = [mc0, mc1]
    mock_cls.get_taken_export_indices.return_value = {0}
    mock_cls.get_taken_names.return_value = {"car"}

    svc.select_model(project_id=1, model_id=20, owner_user_id=5)

    mock_cls.bulk_create_project_classes.assert_not_called()


def test_select_model_imports_non_conflicting_classes_only() -> None:
    """index/name 이 겹치지 않는 모델 클래스만 골라서 import 한다."""
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "owner"
    mock_proj.get_membership.return_value = mem
    mock_proj.get_owner_user_id.return_value = 5

    ml_model = MagicMock()
    ml_model.id = 30
    ml_model.owner_id = 5
    mock_cls.get_model.return_value = ml_model

    mc0 = MagicMock()
    mc0.class_index = 0
    mc0.name = "person"
    mc0.id = 1
    mc1 = MagicMock()
    mc1.class_index = 1
    mc1.name = "car"
    mc1.id = 2
    mock_cls.list_model_classes.return_value = [mc0, mc1]
    mock_cls.get_taken_export_indices.return_value = {10}
    mock_cls.get_taken_names.return_value = {"custom"}

    svc.select_model(project_id=1, model_id=30, owner_user_id=5)

    mock_cls.bulk_create_project_classes.assert_called_once()
    entries = mock_cls.bulk_create_project_classes.call_args.kwargs["entries"]
    assert [e[0] for e in entries] == [0, 1]
    for e in entries:
        assert len(e) == 4 and e[3].startswith("#")


def test_list_classes_include_inactive_requires_owner() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "annotator"
    mock_proj.get_membership.return_value = mem
    with pytest.raises(ProjectForbiddenError):
        svc.list_classes(project_id=1, user_id=3, include_inactive=True)


def test_list_classes_include_inactive_ok_for_owner() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "owner"
    mock_proj.get_membership.return_value = mem
    mock_cls.list_project_classes.return_value = []
    svc.list_classes(project_id=1, user_id=5, include_inactive=True)
    mock_cls.list_project_classes.assert_called_once_with(1, include_inactive=True)


def test_rename_class_sets_is_active() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "owner"
    mock_proj.get_membership.return_value = mem
    row = MagicMock()
    row.id = 7
    row.project_id = 1
    row.name = "cat"
    row.is_active = False
    mock_cls.get_project_class.return_value = row
    mock_cls.name_exists.return_value = False

    svc.rename_class(class_id=7, owner_user_id=5, name=None, color=None, is_active=True)

    assert row.is_active is True
    db.commit.assert_called_once()


def test_delete_class_permanent_raises_for_model_linked_class() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "owner"
    mock_proj.get_membership.return_value = mem
    row = MagicMock()
    row.id = 7
    row.project_id = 1
    row.model_class_id = 99
    mock_cls.get_project_class.return_value = row

    with pytest.raises(ClassHardDeleteNotAllowedError):
        svc.delete_class_permanent(class_id=7, owner_user_id=5)

    mock_cls.delete_project_class_row.assert_not_called()


def test_delete_class_permanent_raises_if_annotations_exist() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "owner"
    mock_proj.get_membership.return_value = mem
    row = MagicMock()
    row.id = 7
    row.project_id = 1
    row.model_class_id = None
    mock_cls.get_project_class.return_value = row
    mock_cls.count_annotations_for_class.return_value = 2

    with pytest.raises(ClassHasAnnotationsError):
        svc.delete_class_permanent(class_id=7, owner_user_id=5)

    mock_cls.delete_project_class_row.assert_not_called()


def test_delete_class_permanent_removes_custom_class_row() -> None:
    svc, db, storage, mock_proj, mock_cls = _make_service()
    mem = MagicMock()
    mem.role = "owner"
    mock_proj.get_membership.return_value = mem
    row = MagicMock()
    row.id = 7
    row.project_id = 1
    row.model_class_id = None
    mock_cls.get_project_class.return_value = row
    mock_cls.count_annotations_for_class.return_value = 0

    svc.delete_class_permanent(class_id=7, owner_user_id=5)

    mock_cls.delete_project_class_row.assert_called_once_with(7)
    db.commit.assert_called_once()
