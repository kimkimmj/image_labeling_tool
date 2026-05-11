"""MinIO 오브젝트 스토리지 클라이언트 래퍼."""

from __future__ import annotations

import io

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


def _build_client() -> Minio:
    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


class StorageClient:
    """MinIO 버킷 작업을 캡슐화한다."""

    def __init__(self) -> None:
        self._client = _build_client()
        self._bucket = settings.minio_bucket

    def upload_bytes(self, object_key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        """바이트를 MinIO 오브젝트로 업로드한다."""
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=object_key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def get_bytes(self, object_key: str) -> bytes:
        """MinIO 오브젝트를 바이트로 다운로드한다."""
        response = self._client.get_object(self._bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete_object(self, object_key: str) -> None:
        """오브젝트를 삭제한다. 오브젝트가 없으면 무시한다."""
        try:
            self._client.remove_object(self._bucket, object_key)
        except S3Error:
            pass

    def delete_prefix(self, prefix: str) -> None:
        """prefix로 시작하는 모든 오브젝트를 삭제한다. 없으면 아무 작업도 하지 않는다.

        MinIO/S3 list + remove. 네트워크·권한 오류는 예외로 전달한다.
        """
        base = (prefix or "").strip("/")
        search_prefix = f"{base}/" if base else ""
        try:
            objects = self._client.list_objects(
                self._bucket,
                prefix=search_prefix or None,
                recursive=True,
            )
            for obj in objects:
                self._client.remove_object(self._bucket, obj.object_name)
        except S3Error as exc:
            raise RuntimeError(f"MinIO 오류: {exc}") from exc

    def object_exists(self, object_key: str) -> bool:
        """오브젝트 존재 여부를 확인한다."""
        try:
            self._client.stat_object(self._bucket, object_key)
            return True
        except S3Error:
            return False


def get_storage_client() -> StorageClient:
    """FastAPI Depends에서 사용할 수 있는 StorageClient 팩토리."""
    return StorageClient()
