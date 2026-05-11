"""ZIP 이미지 업로드 처리 Celery 태스크."""

from __future__ import annotations

import io
import logging
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.storage import StorageClient
from app.db.session import SessionLocal
from app.models.ml_model import ModelClass, ProjectClass
from app.models.project import Project, ProjectUser
from app.models.upload import Annotation, Image, ImageAssignment, UploadJob
from app.worker import celery_app

logger = logging.getLogger(__name__)


def _job_deleted_abort(db: Session, job_id: int) -> bool:
    """job 행이 없으면 True(호출자가 태스크 중단)."""
    if db.get(UploadJob, job_id) is None:
        logger.info("[Job %d] 업로드 작업이 삭제되어 태스크를 중단합니다.", job_id)
        return True
    return False

_VALID_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
)

_IMAGE_MIME: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}

# __MACOSX, .DS_Store, 숨김 파일 패턴
_SKIP_PATTERN = re.compile(r"(^|/)(__MACOSX|\.DS_Store|Thumbs\.db|desktop\.ini)(/|$)")


def _is_valid_image_entry(zip_info: zipfile.ZipInfo) -> bool:
    """ZipInfo가 저장할 가치 있는 이미지 파일인지 판별한다."""
    name = zip_info.filename
    if zip_info.is_dir():
        return False
    if _SKIP_PATTERN.search(name):
        return False
    basename = os.path.basename(name)
    if basename.startswith("."):
        return False
    ext = os.path.splitext(basename)[1].lower()
    return ext in _VALID_EXTENSIONS


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w.\-]", "_", os.path.basename(name))[:200]


def _get_project_owner_id(db: Session, project_id: int) -> int | None:
    """프로젝트 owner의 user_id를 반환한다."""
    stmt = select(ProjectUser).where(
        ProjectUser.project_id == project_id,
        ProjectUser.role == "owner",
    )
    row = db.scalar(stmt)
    return row.user_id if row else None


def _build_class_index_map(
    db: Session, project_id: int, model_id: int
) -> dict[int, int]:
    """YOLO 클래스 인덱스 → project_class.id 매핑 테이블을 빌드한다."""
    stmt = (
        select(ModelClass.class_index, ProjectClass.id)
        .join(ProjectClass, ProjectClass.model_class_id == ModelClass.id)
        .where(
            ModelClass.model_id == model_id,
            ProjectClass.project_id == project_id,
            ProjectClass.is_active.is_(True),
        )
    )
    return {row.class_index: row.id for row in db.execute(stmt)}


def _load_yolo_model(model_pt_bytes: bytes) -> tuple[object, str]:
    """YOLO 모델을 임시 파일로 로드하고 (model, tmp_path)를 반환한다.

    호출자가 사용 후 tmp_path를 직접 삭제해야 한다.
    """
    from ultralytics import YOLO  # type: ignore[import]

    with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as tmp:
        tmp.write(model_pt_bytes)
        tmp_path = tmp.name

    logger.info("[YOLO] 모델 로드 중: %s (%d bytes)", tmp_path, len(model_pt_bytes))
    model = YOLO(tmp_path)
    logger.info("[YOLO] 모델 로드 완료")
    return model, tmp_path


def _infer_single(
    model: object,
    image_bytes: bytes,
) -> list[tuple[float, float, float, float, int, float]]:
    """이미 로드된 YOLO 모델로 이미지 한 장을 추론한다.

    Returns [(x, y, w, h, class_index, confidence), ...] — 정규화 좌표(top-left).
    """
    from PIL import Image as PILImage  # type: ignore[import]

    pil_img = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
    results = model(pil_img, verbose=False)  # type: ignore[operator]
    out: list[tuple[float, float, float, float, int, float]] = []
    for r in results:
        for box in r.boxes:
            cx, cy, bw, bh = box.xywhn[0].tolist()
            x = max(0.0, cx - bw / 2)
            y = max(0.0, cy - bh / 2)
            w = min(1.0, bw)
            h = min(1.0, bh)
            out.append((x, y, w, h, int(box.cls[0]), float(box.conf[0])))
    return out


@celery_app.task(bind=True, name="app.tasks.upload_tasks.process_zip_upload")
def process_zip_upload(self: object, job_id: int) -> None:  # noqa: ANN001
    """ZIP 파일을 압축 해제해 이미지를 저장하고 자동 라벨링을 실행한다."""
    logger.info("[Job %d] 태스크 시작", job_id)
    db: Session = SessionLocal()
    storage = StorageClient()

    try:
        job: UploadJob | None = db.get(UploadJob, job_id)
        if job is None:
            logger.info("[Job %d] DB에 업로드 작업 없음 — 이미 삭제되었거나 잘못된 id", job_id)
            return

        job.status = "processing"
        db.commit()

        logger.info("[Job %d] ZIP 다운로드 중: %s", job_id, job.original_file_path)
        zip_bytes = storage.get_bytes(job.original_file_path)
        logger.info("[Job %d] ZIP 크기: %d bytes", job_id, len(zip_bytes))

        project: Project | None = db.get(Project, job.project_id)
        if project is None:
            _fail_job(db, job, "프로젝트를 찾을 수 없습니다.")
            return

        owner_id = _get_project_owner_id(db, job.project_id)
        if owner_id is None:
            _fail_job(db, job, "프로젝트 owner를 찾을 수 없습니다.")
            return

        saved_image_data: list[tuple[Image, bytes]] = []

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            all_entries = zf.infolist()
            total_count = len(all_entries)
            logger.info("[Job %d] ZIP 전체 엔트리 수: %d", job_id, total_count)

            idx = 0
            for entry in all_entries:
                if _job_deleted_abort(db, job_id):
                    return
                if not _is_valid_image_entry(entry):
                    logger.debug(
                        "[Job %d] skip (필터): %s", job_id, entry.filename
                    )
                    continue

                try:
                    raw = zf.read(entry.filename)
                    dims = _validate_and_get_dims(raw)
                    if dims is None:
                        logger.warning(
                            "[Job %d] skip (PIL 오픈 실패): %s (%d bytes)",
                            job_id, entry.filename, len(raw),
                        )
                        continue

                    width, height = dims
                    safe_name = _sanitize_filename(entry.filename)
                    object_key = (
                        f"projects/{job.project_id}/uploads/{job_id}/images/"
                        f"{idx:04d}_{safe_name}"
                    )
                    ext = os.path.splitext(safe_name)[1].lower()
                    content_type = _IMAGE_MIME.get(ext, "application/octet-stream")

                    storage.upload_bytes(object_key, raw, content_type=content_type)
                    logger.info(
                        "[Job %d] 이미지 저장 [%d] %s → %s (%dx%d)",
                        job_id, idx, entry.filename, object_key, width, height,
                    )

                    image = Image(
                        project_id=job.project_id,
                        upload_job_id=job_id,
                        file_name=safe_name,
                        file_path=object_key,
                        width=width,
                        height=height,
                    )
                    db.add(image)
                    db.flush()

                    assignment = ImageAssignment(
                        image_id=image.id,
                        assigned_to=None,
                        assigned_by=owner_id,
                        status="unassigned",
                    )
                    db.add(assignment)
                    db.flush()

                    saved_image_data.append((image, raw))
                    idx += 1

                except IntegrityError:
                    db.rollback()
                    if _job_deleted_abort(db, job_id):
                        return
                    logger.error(
                        "[Job %d] 이미지 DB 무결성 오류 (%s)",
                        job_id,
                        entry.filename,
                        exc_info=True,
                    )
                    continue
                except Exception as e:  # noqa: BLE001
                    logger.error(
                        "[Job %d] 이미지 처리 오류 (%s): %s",
                        job_id, entry.filename, e, exc_info=True,
                    )
                    continue

        job = db.get(UploadJob, job_id)
        if job is None:
            logger.info("[Job %d] ZIP 처리 후 job 없음 — 삭제로 종료", job_id)
            return

        job.total_count = total_count
        job.processed_count = len(saved_image_data)
        try:
            db.commit()
        except Exception:
            db.rollback()
            if db.get(UploadJob, job_id) is None:
                logger.info("[Job %d] 저장 커밋 중 job 삭제", job_id)
                return
            raise
        logger.info(
            "[Job %d] 저장 완료: %d / %d (제외 %d)",
            job_id,
            len(saved_image_data),
            total_count,
            total_count - len(saved_image_data),
        )

        # ZIP 저장 완료 → 상태 먼저 completed로 업데이트
        job = db.get(UploadJob, job_id)
        if job is None:
            logger.info("[Job %d] 완료 표기 전 job 삭제됨", job_id)
            return
        job.status = "completed"
        job.completed_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        try:
            db.commit()
        except Exception:
            db.rollback()
            if db.get(UploadJob, job_id) is None:
                logger.info("[Job %d] 완료 커밋 중 job 삭제", job_id)
                return
            raise
        logger.info("[Job %d] ZIP 저장 완료", job_id)

        job = db.get(UploadJob, job_id)
        if job is None:
            logger.info("[Job %d] 자동 라벨 단계 전 job 삭제됨 — 종료", job_id)
            return

        if project.selected_model_id and saved_image_data:
            logger.info(
                "[Job %d] YOLO 자동 라벨링 시작 (model_id=%d, 이미지 %d장)",
                job_id, project.selected_model_id, len(saved_image_data),
            )
            job.auto_label_status = "running"
            db.commit()
            try:
                finished = _run_auto_labeling(
                    db=db,
                    storage=storage,
                    project=project,
                    saved_image_data=saved_image_data,
                    owner_id=owner_id,
                    job_id=job_id,
                )
                if not finished:
                    return
                job = db.get(UploadJob, job_id)
                if job is None:
                    return
                job.auto_label_status = "completed"
                job.auto_label_completed_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
                db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error("[Job %d] YOLO 라벨링 실패: %s", job_id, exc, exc_info=True)
                job = db.get(UploadJob, job_id)
                if job is None:
                    return
                job.auto_label_status = "failed"
                job.auto_label_error = str(exc)[:500]
                db.commit()
        else:
            if not project.selected_model_id:
                logger.info("[Job %d] selected_model 없음 → YOLO 스킵", job_id)
            job = db.get(UploadJob, job_id)
            if job is None:
                logger.info("[Job %d] 스킵 표기 전 job 삭제됨", job_id)
                return
            job.auto_label_status = "skipped"
            db.commit()

        logger.info("[Job %d] 태스크 완료", job_id)

    except Exception as exc:  # noqa: BLE001
        logger.error("[Job %d] 태스크 실패: %s", job_id, exc, exc_info=True)
        try:
            j = db.get(UploadJob, job_id)
            _fail_job(db, j, str(exc))
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()


def _validate_and_get_dims(raw: bytes) -> tuple[int, int] | None:
    """PIL로 이미지를 열어 (width, height)를 반환한다.

    verify() 대신 load()를 사용한다.
    - verify()는 JPEG 정상 파일에서도 예외를 던지는 경우가 많음
    - load()는 실제 픽셀 디코딩을 강제하므로 깨진 파일을 더 안정적으로 걸러냄
    """
    try:
        from PIL import Image as PILImage  # type: ignore[import]

        img = PILImage.open(io.BytesIO(raw))
        img.load()  # 실제 디코딩 강제 — 손상 파일은 여기서 예외 발생
        return img.size  # (width, height)
    except Exception:  # noqa: BLE001
        return None


def _run_auto_labeling(
    *,
    db: Session,
    storage: StorageClient,
    project: Project,
    saved_image_data: list[tuple[Image, bytes]],
    owner_id: int,
    job_id: int,
) -> bool:
    """YOLO 자동 라벨링. job 이 삭제되면 False, 정상 완료면 True."""

    tmp_path: str | None = None
    total_annotations = 0

    try:
        if _job_deleted_abort(db, job_id):
            return False
        from app.models.ml_model import MlModel

        ml_model: MlModel | None = db.get(MlModel, project.selected_model_id)
        if ml_model is None:
            raise RuntimeError(f"model_id={project.selected_model_id} DB에 없음")

        logger.info("[Job %d] YOLO: 모델 파일 다운로드 중 (%s)",
                    job_id, ml_model.file_path)
        model_bytes = storage.get_bytes(ml_model.file_path)

        class_map = _build_class_index_map(db, project.id, project.selected_model_id)
        logger.info("[Job %d] YOLO: class 매핑 %d개 — %s",
                    job_id, len(class_map), class_map)

        if not class_map:
            logger.warning("[Job %d] YOLO: 매핑된 project_class 없음 → 추론 스킵", job_id)
            return True

        yolo_model, tmp_path = _load_yolo_model(model_bytes)
        del model_bytes

        assignment_map: dict[int, int] = {}
        for img, _ in saved_image_data:
            db.refresh(img)
            if img.assignment is not None:
                assignment_map[img.id] = img.assignment.id

        for i, (img, img_bytes) in enumerate(saved_image_data):
            if _job_deleted_abort(db, job_id):
                return False
            assignment_id = assignment_map.get(img.id)
            if assignment_id is None:
                logger.warning("[Job %d] YOLO [%d/%d] image_id=%d: assignment 없음 → 스킵",
                               job_id, i + 1, len(saved_image_data), img.id)
                continue

            try:
                detections = _infer_single(yolo_model, img_bytes)
                logger.info(
                    "[Job %d] YOLO [%d/%d] image_id=%d (%s): bbox %d개 검출",
                    job_id, i + 1, len(saved_image_data),
                    img.id, img.file_name, len(detections),
                )

                saved = 0
                for x, y, w, h, class_idx, conf in detections:
                    project_class_id = class_map.get(class_idx)
                    if project_class_id is None:
                        continue
                    db.add(Annotation(
                        assignment_id=assignment_id,
                        image_id=img.id,
                        class_id=project_class_id,
                        x=x,
                        y=y,
                        width=w,
                        height=h,
                        confidence=conf,
                        source="auto",
                        created_by=owner_id,
                    ))
                    saved += 1

                db.commit()
                total_annotations += saved
                logger.info(
                    "[Job %d] YOLO [%d/%d] image_id=%d: annotation %d개 저장",
                    job_id, i + 1, len(saved_image_data), img.id, saved,
                )

            except Exception as e:  # noqa: BLE001
                logger.error(
                    "[Job %d] YOLO [%d/%d] image_id=%d 추론 오류: %s",
                    job_id, i + 1, len(saved_image_data), img.id, e, exc_info=True,
                )
                db.rollback()
                if _job_deleted_abort(db, job_id):
                    return False
                continue

        logger.info(
            "[Job %d] YOLO 완료: 이미지 %d장, 총 annotation %d개",
            job_id, len(saved_image_data), total_annotations,
        )
        return True
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _fail_job(db: Session, job: UploadJob | None, message: str) -> None:
    if job is None:
        return
    logger.error("Job fail: %s", message)
    jid = job.id
    fresh = db.get(UploadJob, jid)
    if fresh is None:
        logger.info("[Job %d] 이미 삭제되어 실패 상태 갱신 생략", jid)
        return
    fresh.status = "failed"
    fresh.error_message = str(message)[:1000]
    db.commit()
