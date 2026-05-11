"""업로드 도메인 비즈니스 예외."""

from __future__ import annotations


class UploadJobNotFoundError(Exception):
    pass


class UploadJobStoragePurgeError(Exception):
    """업로드 작업에 해당하는 객체 스토리지 prefix 삭제 실패."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UploadForbiddenError(Exception):
    pass


class ImageNotFoundError(Exception):
    pass


class InvalidZipFileError(Exception):
    pass


class FileTooLargeError(Exception):
    pass
