"""OAuth 로그인 도메인 예외.

비즈니스 규칙 위반은 서비스에서 발생시키고, 라우터에서 HTTP 상태로 매핑한다.
"""


class OAuthExchangeError(Exception):
    """IdP 토큰 교환·프로필 조회가 실패했을 때 발생한다."""

    pass


class OAuthEmailMissingError(Exception):
    """필수 이메일을 IdP 프로필에서 얻지 못했을 때 발생한다."""

    pass


class OAuthInvalidStateError(Exception):
    """OAuth state 또는 PKCE verifier 검증에 실패했을 때 발생한다."""

    pass


class EmailConflictError(Exception):
    """동일 이메일이 이미 다른 사용자에 등록된 경우 신규 OAuth 가입을 거절할 때 발생한다."""

    pass
