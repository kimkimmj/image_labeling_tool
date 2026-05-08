"""프로젝트 도메인 예외."""


class ProjectNotFoundError(Exception):
    """프로젝트가 없거나 접근 권한이 없을 때."""

    pass


class ProjectForbiddenError(Exception):
    """멤버는 있으나 요청한 작업(owner 전용 등)에 권한이 없을 때."""

    pass


class InvitationInvalidError(Exception):
    """초대 토큰이 유효하지 않거나 만료·이미 사용됨."""

    pass
