"""Export Celery tasks — YOLO / COCO ZIP generation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.storage import StorageClient
from app.db.session import SessionLocal
from app.domains.export.repositories.export_repository import ExportRepository
from app.domains.export.services.coco_export_generator import CocoExportGenerator
from app.domains.export.services.yolo_export_generator import YoloExportGenerator
from app.worker import celery_app

logger = logging.getLogger(__name__)


def _utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@celery_app.task(
    bind=True,
    name="app.tasks.export_tasks.run_export",
    autoretry_for=(ConnectionError, TimeoutError, OSError),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
)
def run_export(self, export_job_id: int, project_id: int) -> None:  # noqa: ANN001
    """Generate dataset ZIP (YOLO or COCO) and upload to MinIO."""
    db = SessionLocal()
    repo = ExportRepository(db)
    storage = StorageClient()

    try:
        job = repo.get_job_for_project(project_id=project_id, job_id=export_job_id)
        if job is None:
            logger.error("Export job %s not found for project %s", export_job_id, project_id)
            return

        repo.update_job_status(export_job_id, status="processing")
        db.commit()

        split_rows = repo.list_split_export_rows(job.split_id)
        assignment_ids = list({r.assignment_id for r in split_rows})
        annotations = repo.list_annotations_for_assignments(assignment_ids)
        project_classes = repo.list_active_project_classes(project_id)

        export_format = getattr(job, "export_format", "yolo") or "yolo"
        if export_format == "coco":
            generator = CocoExportGenerator(storage)
        else:
            generator = YoloExportGenerator(storage)

        zip_bytes = generator.build_zip(
            split_rows=split_rows,
            annotations=annotations,
            project_classes=project_classes,
        )

        object_key = f"exports/{project_id}/{export_job_id}.zip"
        storage.upload_bytes(object_key, zip_bytes, content_type="application/zip")

        repo.update_job_status(
            export_job_id,
            status="completed",
            export_path=object_key,
            error_message=None,
            completed_at=_utc_naive_now(),
        )
        db.commit()
        logger.info(
            "Export job %s completed (%s): %s",
            export_job_id,
            export_format,
            object_key,
        )

    except Exception as exc:
        db.rollback()
        logger.exception("Export job %s failed (retry %s)", export_job_id, self.request.retries)
        if self.request.retries >= self.max_retries:
            try:
                repo.update_job_status(
                    export_job_id,
                    status="failed",
                    error_message=str(exc)[:2000],
                    completed_at=_utc_naive_now(),
                )
                db.commit()
            except Exception:
                db.rollback()
            return
        raise self.retry(exc=exc) from exc
    finally:
        db.close()
