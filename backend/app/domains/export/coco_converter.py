"""COCO detection JSON helpers."""

from __future__ import annotations

from typing import Any


def normalized_bbox_to_coco_pixel(
    x: float,
    y: float,
    width: float,
    height: float,
    image_width: int,
    image_height: int,
) -> list[float]:
    """Top-left normalized box -> COCO [x, y, width, height] in pixels."""
    return [
        round(x * image_width, 2),
        round(y * image_height, 2),
        round(width * image_width, 2),
        round(height * image_height, 2),
    ]


def build_coco_categories(project_classes: list) -> list[dict[str, Any]]:  # noqa: ANN001
    return [
        {
            "id": c.export_index,
            "name": c.name,
            "supercategory": "none",
        }
        for c in sorted(project_classes, key=lambda pc: pc.export_index)
    ]


def build_coco_document(
    *,
    categories: list[dict[str, Any]],
    images: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "info": {
            "description": "Image Labeling Tool export",
            "version": "1.0",
        },
        "licenses": [],
        "categories": categories,
        "images": images,
        "annotations": annotations,
    }
