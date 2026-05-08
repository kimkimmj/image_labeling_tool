from enum import Enum


class ProjectRole(str, Enum):
    owner = "owner"
    reviewer = "reviewer"
    annotator = "annotator"


class ProjectInvitationRole(str, Enum):
    annotator = "annotator"
    reviewer = "reviewer"


class InvitationStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    expired = "expired"
    cancelled = "cancelled"


class OAuthProvider(str, Enum):
    """지원 OAuth 제공자."""

    google = "google"
    naver = "naver"
    kakao = "kakao"
