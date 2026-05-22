"""Convert normalized bbox annotations to YOLO label lines."""

from __future__ import annotations


def bbox_to_yolo_line(
    export_index: int,
    x: float,
    y: float,
    width: float,
    height: float,
) -> str:
    """Top-left normalized box -> YOLO class cx cy w h line."""
    cx = x + width / 2.0
    cy = y + height / 2.0
    return f"{export_index} {cx:.6f} {cy:.6f} {width:.6f} {height:.6f}"


def build_data_yaml(
    *,
    class_names_by_index: dict[int, str],
    num_classes: int,
) -> str:
    """Ultralytics-style data.yaml content."""
    lines = [
        "path: .",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        f"nc: {num_classes}",
        "names:",
    ]
    for idx in range(num_classes):
        name = class_names_by_index.get(idx, f"class_{idx}")
        lines.append(f"  {idx}: {name}")
    return "\n".join(lines) + "\n"
