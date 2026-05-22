"""Deterministic split algorithm tests."""

from app.core.split_algorithm import compute_split_assignments


def test_same_seed_same_result() -> None:
    ids = list(range(1, 21))
    a = compute_split_assignments(ids, train_ratio=70, val_ratio=20, test_ratio=10, random_seed=42)
    b = compute_split_assignments(ids, train_ratio=70, val_ratio=20, test_ratio=10, random_seed=42)
    assert a == b


def test_each_item_exactly_one_split() -> None:
    ids = [5, 3, 8, 1]
    result = compute_split_assignments(
        ids, train_ratio=50, val_ratio=25, test_ratio=25, random_seed=0
    )
    assert len(result) == 4
    assert {r[0] for r in result} == set(ids)
    types = [r[1] for r in result]
    assert types.count("train") + types.count("val") + types.count("test") == 4
