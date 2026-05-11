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


class UploadType(str, Enum):
    image_zip = "image_zip"
    video = "video"


class UploadStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class AssignmentStatus(str, Enum):
    unassigned = "unassigned"
    assigned = "assigned"
    in_progress = "in_progress"
    done = "done"
    submitted = "submitted"
    review_assigned = "review_assigned"
    approved = "approved"
    reverted = "reverted"
    rejected = "rejected"  # 미사용 — reverted 로 통일, ENUM 잔존만


class AnnotationSource(str, Enum):
    auto = "auto"
    manual = "manual"
