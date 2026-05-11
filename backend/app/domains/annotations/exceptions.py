"""어노테이션 도메인 비즈니스 예외."""

from __future__ import annotations


class AnnotationNotFoundError(Exception):
    pass


class AnnotationForbiddenError(Exception):
    pass


class AnnotationImmutableError(Exception):
    """approved 상태 이미지는 어노테이션을 수정할 수 없다."""
    pass


class InvalidClassError(Exception):
    """class_id가 프로젝트에 속하지 않거나 비활성 상태."""
    pass


class InvalidBboxError(Exception):
    """좌표 범위 검증 실패."""
    pass
