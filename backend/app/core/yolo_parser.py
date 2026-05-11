"""YOLO .pt 파일 파싱 및 검증 유틸리티."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class YoloModelInfo:
    framework: str
    version: str | None
    class_names: dict[int, str]


class InvalidYoloModelError(Exception):
    """YOLO 모델이 유효하지 않거나 detection 모델이 아닐 때."""


def parse_yolo_pt(file_bytes: bytes, filename: str) -> YoloModelInfo:
    """바이트로 받은 .pt 파일을 Ultralytics YOLO로 로드해 클래스 정보를 추출한다.

    - task == "detect" 여야 통과
    - model.names 가 비어 있으면 InvalidYoloModelError
    """
    if not filename.lower().endswith(".pt"):
        raise InvalidYoloModelError("YOLO 모델 파일은 .pt 확장자만 허용합니다.")

    try:
        from ultralytics import YOLO  # type: ignore[import]
    except ImportError as exc:
        raise ImportError("ultralytics 패키지가 설치되어 있지 않습니다.") from exc

    with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        try:
            model = YOLO(str(tmp_path))
        except Exception as exc:
            raise InvalidYoloModelError(f"YOLO 모델 로드 실패: {exc}") from exc

        task: str | None = getattr(model, "task", None)
        if task != "detect":
            raise InvalidYoloModelError(
                f"detection 모델만 허용합니다. (task={task!r})"
            )

        names: dict[int, str] | None = getattr(model, "names", None)
        if not names:
            raise InvalidYoloModelError("model.names 가 비어 있습니다.")

        version: str | None = _extract_version(model)
    finally:
        tmp_path.unlink(missing_ok=True)

    return YoloModelInfo(
        framework="ultralytics",
        version=version,
        class_names=dict(names),
    )


def _extract_version(model: object) -> str | None:
    """체크포인트 메타데이터에서 버전 문자열을 best-effort로 추출한다."""
    try:
        ckpt: dict = getattr(model, "ckpt", None) or {}
        return (
            ckpt.get("version")
            or ckpt.get("ultralytics_version")
            or (ckpt.get("train_args") or {}).get("version")
        )
    except Exception:
        return None
