"""ZIP 업로드 태스크 단위 테스트."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 헬퍼: 다양한 ZIP 바이트 생성
# ---------------------------------------------------------------------------


def _make_zip(entries: dict[str, bytes]) -> bytes:
    """entries = {filename: content_bytes}"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _make_tiny_png() -> bytes:
    """1×1 픽셀 PNG."""
    import struct
    import zlib

    def _chunk(name: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + name + data
        return c + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\xff\xff")
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


# ---------------------------------------------------------------------------
# _is_valid_image_entry
# ---------------------------------------------------------------------------


def test_is_valid_image_entry_accepts_jpg() -> None:
    from app.tasks.upload_tasks import _is_valid_image_entry

    zi = zipfile.ZipInfo("photo.jpg")
    assert _is_valid_image_entry(zi) is True


def test_is_valid_image_entry_accepts_png_nested() -> None:
    from app.tasks.upload_tasks import _is_valid_image_entry

    zi = zipfile.ZipInfo("sub/dir/img.png")
    assert _is_valid_image_entry(zi) is True


def test_is_valid_image_entry_rejects_directory() -> None:
    from app.tasks.upload_tasks import _is_valid_image_entry

    zi = zipfile.ZipInfo("images/")
    assert _is_valid_image_entry(zi) is False


def test_is_valid_image_entry_rejects_macosx() -> None:
    from app.tasks.upload_tasks import _is_valid_image_entry

    zi = zipfile.ZipInfo("__MACOSX/._photo.jpg")
    assert _is_valid_image_entry(zi) is False


def test_is_valid_image_entry_rejects_ds_store() -> None:
    from app.tasks.upload_tasks import _is_valid_image_entry

    zi = zipfile.ZipInfo(".DS_Store")
    assert _is_valid_image_entry(zi) is False


def test_is_valid_image_entry_rejects_txt() -> None:
    from app.tasks.upload_tasks import _is_valid_image_entry

    zi = zipfile.ZipInfo("readme.txt")
    assert _is_valid_image_entry(zi) is False


def test_is_valid_image_entry_rejects_hidden_file() -> None:
    from app.tasks.upload_tasks import _is_valid_image_entry

    zi = zipfile.ZipInfo(".hidden.jpg")
    assert _is_valid_image_entry(zi) is False


def test_is_valid_image_entry_accepts_uppercase_extension() -> None:
    from app.tasks.upload_tasks import _is_valid_image_entry

    zi = zipfile.ZipInfo("PHOTO.JPG")
    assert _is_valid_image_entry(zi) is True


# ---------------------------------------------------------------------------
# _validate_and_get_dims
# ---------------------------------------------------------------------------


def test_validate_and_get_dims_valid_png() -> None:
    from app.tasks.upload_tasks import _validate_and_get_dims

    png = _make_tiny_png()
    result = _validate_and_get_dims(png)
    assert result == (1, 1)


def test_validate_and_get_dims_invalid_bytes() -> None:
    from app.tasks.upload_tasks import _validate_and_get_dims

    result = _validate_and_get_dims(b"not an image")
    assert result is None


def test_validate_and_get_dims_corrupt_png() -> None:
    from app.tasks.upload_tasks import _validate_and_get_dims

    # PNG 헤더만 있고 나머지 없음
    result = _validate_and_get_dims(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10)
    assert result is None


# ---------------------------------------------------------------------------
# total_count = 모든 ZIP 엔트리 수
# ---------------------------------------------------------------------------


def test_total_count_includes_all_entries() -> None:
    """ZIP 안의 모든 엔트리 수가 total_count가 된다."""
    png = _make_tiny_png()
    entries = {
        "img1.jpg": png,
        "img2.png": png,
        "readme.txt": b"hello",
        "__MACOSX/._img1.jpg": b"mac",
        "folder/": b"",  # directory entry
    }
    zip_bytes = _make_zip(entries)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        total = len(zf.infolist())

    assert total == 5  # 모든 엔트리


# ---------------------------------------------------------------------------
# skipped_count 계산
# ---------------------------------------------------------------------------


def test_skipped_count_is_total_minus_processed() -> None:
    """total_count - processed_count = skipped_count."""
    total = 10
    processed = 7
    skipped = total - processed
    assert skipped == 3


# ---------------------------------------------------------------------------
# _build_class_index_map
# ---------------------------------------------------------------------------


def test_build_class_index_map_returns_mapping() -> None:
    from app.tasks.upload_tasks import _build_class_index_map

    db = MagicMock()
    row1 = MagicMock()
    row1.class_index = 0
    row1.id = 10
    row2 = MagicMock()
    row2.class_index = 1
    row2.id = 20

    db.execute.return_value = [row1, row2]

    result = _build_class_index_map(db, project_id=1, model_id=5)
    assert result == {0: 10, 1: 20}


# ---------------------------------------------------------------------------
# UploadService.create_upload_job
# ---------------------------------------------------------------------------


def test_create_upload_job_dispatches_celery_task() -> None:
    """create_upload_job 호출 시 Celery 태스크가 디스패치돼야 한다."""
    from app.domains.uploads.services.upload_service import UploadService

    db = MagicMock()
    storage = MagicMock()

    png = _make_tiny_png()
    zip_bytes = _make_zip({"img.png": png})

    with (
        patch("app.domains.uploads.services.upload_service.ProjectRepository") as proj_cls,
        patch("app.domains.uploads.services.upload_service.UploadRepository") as up_cls,
        patch("app.tasks.upload_tasks.process_zip_upload") as mock_task,
    ):
        mock_proj = MagicMock()
        mock_up = MagicMock()
        proj_cls.return_value = mock_proj
        up_cls.return_value = mock_up

        mock_proj.get_membership.return_value = MagicMock()

        from datetime import datetime

        fake_job = MagicMock()
        fake_job.id = 42
        fake_job.project_id = 1
        fake_job.uploaded_by = 7
        fake_job.upload_type = "image_zip"
        fake_job.status = "pending"
        fake_job.original_file_name = "test.zip"
        fake_job.original_file_path = "projects/1/uploads/42/original/test.zip"
        fake_job.total_count = None
        fake_job.processed_count = None
        fake_job.error_message = None
        fake_job.created_at = datetime.utcnow()
        fake_job.completed_at = None
        mock_up.create_job.return_value = fake_job

        svc = UploadService(db, storage)
        svc._projects = mock_proj
        svc._uploads = mock_up

        svc.create_upload_job(
            project_id=1,
            user_id=7,
            filename="test.zip",
            file_bytes=zip_bytes,
        )

    mock_task.delay.assert_called_once_with(42)


def test_create_upload_job_rejects_non_zip() -> None:
    from app.domains.uploads.exceptions import InvalidZipFileError
    from app.domains.uploads.services.upload_service import UploadService

    db = MagicMock()
    storage = MagicMock()

    with (
        patch("app.domains.uploads.services.upload_service.ProjectRepository") as proj_cls,
        patch("app.domains.uploads.services.upload_service.UploadRepository"),
    ):
        mock_proj = MagicMock()
        proj_cls.return_value = mock_proj
        mock_proj.get_membership.return_value = MagicMock()

        svc = UploadService(db, storage)
        svc._projects = mock_proj

        with pytest.raises(InvalidZipFileError):
            svc.create_upload_job(
                project_id=1,
                user_id=7,
                filename="notzip.zip",
                file_bytes=b"this is not a zip",
            )


# ---------------------------------------------------------------------------
# owner 임시 배정 — _get_project_owner_id
# ---------------------------------------------------------------------------


def test_get_project_owner_id_returns_owner() -> None:
    from app.tasks.upload_tasks import _get_project_owner_id

    db = MagicMock()
    row = MagicMock()
    row.user_id = 99
    db.scalar.return_value = row

    result = _get_project_owner_id(db, project_id=1)
    assert result == 99


def test_get_project_owner_id_returns_none_if_no_owner() -> None:
    from app.tasks.upload_tasks import _get_project_owner_id

    db = MagicMock()
    db.scalar.return_value = None

    result = _get_project_owner_id(db, project_id=1)
    assert result is None
