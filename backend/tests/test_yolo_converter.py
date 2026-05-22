"""YOLO label conversion tests."""

from app.domains.export.yolo_converter import bbox_to_yolo_line, build_data_yaml


def test_bbox_to_yolo_line() -> None:
    line = bbox_to_yolo_line(0, 0.4, 0.3, 0.2, 0.1)
    assert line == "0 0.500000 0.350000 0.200000 0.100000"


def test_build_data_yaml() -> None:
    content = build_data_yaml(class_names_by_index={0: "cat", 1: "dog"}, num_classes=2)
    assert "nc: 2" in content
    assert "0: cat" in content
    assert "1: dog" in content
