"""Build YOLO dataset ZIP bytes from split export rows."""

from __future__ import annotations

import io
import zipfile
from collections import defaultdict
from pathlib import PurePosixPath

from app.core.storage import StorageClient
from app.domains.export.repositories.export_repository import ExportAnnotationRow, ExportSplitRow
from app.domains.export.yolo_converter import bbox_to_yolo_line, build_data_yaml
from app.models import ProjectClass


class YoloExportGenerator:
    def __init__(self, storage: StorageClient) -> None:
        self._storage = storage

    def build_zip(
        self,
        *,
        split_rows: list[ExportSplitRow],
        annotations: list[ExportAnnotationRow],
        project_classes: list[ProjectClass],
    ) -> bytes:
        labels_by_assignment: dict[int, list[str]] = defaultdict(list)
        for ann in annotations:
            line = bbox_to_yolo_line(
                ann.export_index,
                ann.x,
                ann.y,
                ann.width,
                ann.height,
            )
            labels_by_assignment[ann.assignment_id].append(line)

        class_names = {c.export_index: c.name for c in project_classes}
        max_index = max(class_names.keys(), default=-1)
        num_classes = max_index + 1 if max_index >= 0 else 0
        yaml_content = build_data_yaml(
            class_names_by_index=class_names,
            num_classes=num_classes,
        )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("data.yaml", yaml_content)

            for row in split_rows:
                split_dir = row.split_type
                stem = PurePosixPath(row.file_name).stem
                image_zip_path = f"images/{split_dir}/{row.file_name}"
                label_zip_path = f"labels/{split_dir}/{stem}.txt"

                image_bytes = self._storage.get_bytes(row.file_path)
                zf.writestr(image_zip_path, image_bytes)

                label_lines = labels_by_assignment.get(row.assignment_id, [])
                label_body = "\n".join(label_lines)
                if label_body:
                    label_body += "\n"
                zf.writestr(label_zip_path, label_body)

        buffer.seek(0)
        return buffer.read()
