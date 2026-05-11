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


class ClassNotFoundError(Exception):
    """project_class 가 없을 때."""

    pass


class ClassDuplicateNameError(Exception):
    """같은 프로젝트 내에 동일한 이름의 클래스가 이미 존재할 때."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class ClassHardDeleteNotAllowedError(Exception):
    """모델에서 가져온 클래스(model_class_id 있음)는 DB에서 영구 삭제할 수 없다."""

    pass


class ClassHasAnnotationsError(Exception):
    """해당 클래스를 쓰는 어노테이션이 있어 영구 삭제할 수 없다."""

    pass


class ModelNotFoundError(Exception):
    """ml_model 이 없을 때."""

    pass


class ModelForbiddenError(Exception):
    """모델 소유자가 프로젝트 owner와 일치하지 않을 때."""

    pass


class InvalidModelError(Exception):
    """업로드한 파일이 유효한 YOLO detection 모델이 아닐 때."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ProjectDeleteNameMismatchError(Exception):
    """삭제 확인용 프로젝트 이름과 실제 이름이 다를 때."""

    pass


class ProjectActiveUploadsError(Exception):
    """pending/processing 업로드 작업이 있을 때 삭제를 거절."""

    pass


class ProjectStoragePurgeError(Exception):
    """객체 스토리지 prefix 삭제 실패."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
