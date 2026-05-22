"""COCO export helper tests."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from unittest.mock import MagicMock

from app.domains.export.coco_converter import (
    build_coco_categories,
    build_coco_document,
    normalized_bbox_to_coco_pixel,
)
from app.domains.export.repositories.export_repository import (
    ExportAnnotationRow,
    ExportSplitRow,
)
from app.domains.export.services.coco_export_generator import CocoExportGenerator


class _FakeClass:
    def __init__(self, export_index: int, name: str) -> None:
        self.export_index = export_index
        self.name = name


def test_normalized_bbox_to_coco_pixel() -> None:
    bbox = normalized_bbox_to_coco_pixel(0.1, 0.2, 0.3, 0.4, 100, 200)
    assert bbox == [10.0, 40.0, 30.0, 80.0]


def test_build_coco_document_structure() -> None:
    doc = build_coco_document(
        categories=[{"id": 0, "name": "cat", "supercategory": "none"}],
        images=[{"id": 1, "file_name": "a.jpg", "width": 100, "height": 100}],
        annotations=[
            {
                "id": 1,
                "image_id": 1,
                "category_id": 0,
                "bbox": [10, 10, 20, 20],
                "area": 400,
                "iscrowd": 0,
            }
        ],
    )
    assert "info" in doc
    assert doc["licenses"] == []
    assert len(doc["categories"]) == 1
    assert len(doc["images"]) == 1
    assert len(doc["annotations"]) == 1


def test_build_coco_categories_uses_export_index() -> None:
    cats = build_coco_categories([_FakeClass(1, "dog"), _FakeClass(0, "cat")])
    assert cats[0]["id"] == 0
    assert cats[1]["id"] == 1


def test_coco_export_generator_zip_layout() -> None:
    storage = MagicMock()
    storage.get_bytes.return_value = b"fake-image"

    rows = [
        ExportSplitRow(
            split_type="train",
            image_id=10,
            assignment_id=100,
            file_name="img.jpg",
            file_path="minio/key/img.jpg",
            width=640,
            height=480,
        ),
    ]
    annotations = [
        ExportAnnotationRow(
            assignment_id=100,
            export_index=0,
            x=0.5,
            y=0.5,
            width=0.1,
            height=0.1,
        ),
    ]
    classes = [_FakeClass(0, "person")]

    zip_bytes = CocoExportGenerator(storage).build_zip(
        split_rows=rows,
        annotations=annotations,
        project_classes=classes,  # type: ignore[arg-type]
    )

    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())
        assert "images/train/img.jpg" in names
        assert "annotations/instances_train.json" in names

        data = json.loads(zf.read("annotations/instances_train.json"))
        assert data["images"][0]["id"] == 10
        assert len(data["annotations"]) == 1
        assert data["annotations"][0]["category_id"] == 0
