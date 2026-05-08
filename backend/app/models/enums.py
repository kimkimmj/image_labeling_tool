from enum import Enum


class OAuthProvider(str, Enum):
    """지원 OAuth 제공자."""

    google = "google"
    naver = "naver"
    kakao = "kakao"
