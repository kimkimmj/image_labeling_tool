"""Build COCO detection dataset ZIP bytes from split export rows."""

from __future__ import annotations

import io
import json
import zipfile
from collections import defaultdict
from typing import Any

from app.core.storage import StorageClient
from app.domains.export.coco_converter import (
    build_coco_categories,
    build_coco_document,
    normalized_bbox_to_coco_pixel,
)
from app.domains.export.repositories.export_repository import ExportAnnotationRow, ExportSplitRow
from app.models import ProjectClass

_SPLIT_JSON_NAMES = {
    "train": "annotations/instances_train.json",
    "val": "annotations/instances_val.json",
    "test": "annotations/instances_test.json",
}


class CocoExportGenerator:
    def __init__(self, storage: StorageClient) -> None:
        self._storage = storage

    def build_zip(
        self,
        *,
        split_rows: list[ExportSplitRow],
        annotations: list[ExportAnnotationRow],
        project_classes: list[ProjectClass],
    ) -> bytes:
        categories = build_coco_categories(project_classes)
        anns_by_assignment: dict[int, list[ExportAnnotationRow]] = defaultdict(list)
        for ann in annotations:
            anns_by_assignment[ann.assignment_id].append(ann)

        rows_by_split: dict[str, list[ExportSplitRow]] = defaultdict(list)
        for row in split_rows:
            rows_by_split[row.split_type].append(row)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for split_type, rows in rows_by_split.items():
                images_json: list[dict[str, Any]] = []
                annotations_json: list[dict[str, Any]] = []
                ann_id = 1

                for row in rows:
                    image_zip_path = f"images/{split_type}/{row.file_name}"
                    image_bytes = self._storage.get_bytes(row.file_path)
                    zf.writestr(image_zip_path, image_bytes)

                    images_json.append(
                        {
                            "id": row.image_id,
                            "file_name": row.file_name,
                            "width": row.width,
                            "height": row.height,
                        }
                    )

                    for ann in anns_by_assignment.get(row.assignment_id, []):
                        bbox = normalized_bbox_to_coco_pixel(
                            ann.x,
                            ann.y,
                            ann.width,
                            ann.height,
                            row.width,
                            row.height,
                        )
                        area = bbox[2] * bbox[3]
                        annotations_json.append(
                            {
                                "id": ann_id,
                                "image_id": row.image_id,
                                "category_id": ann.export_index,
                                "bbox": bbox,
                                "area": area,
                                "iscrowd": 0,
                            }
                        )
                        ann_id += 1

                json_name = _SPLIT_JSON_NAMES.get(split_type)
                if json_name:
                    doc = build_coco_document(
                        categories=categories,
                        images=images_json,
                        annotations=annotations_json,
                    )
                    zf.writestr(
                        json_name,
                        json.dumps(doc, indent=2),
                    )

        buffer.seek(0)
        return buffer.read()
