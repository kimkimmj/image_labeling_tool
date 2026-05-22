"""Deterministic train/val/test split for dataset items."""

from __future__ import annotations

import random
from typing import Literal

SplitType = Literal["train", "val", "test"]


def compute_split_assignments(
    item_ids: list[int],
    *,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    random_seed: int,
) -> list[tuple[int, SplitType]]:
    """Return (dataset_item_id, split_type) for each item.

    Ratios must sum to 100. Items are shuffled with random_seed after stable sort by id.
    Remainder after floor allocation is assigned in order: train, val, test.
    """
    total = train_ratio + val_ratio + test_ratio
    if abs(total - 100.0) > 1e-6:
        raise ValueError("train_ratio + val_ratio + test_ratio must equal 100")

    n = len(item_ids)
    if n == 0:
        return []

    ordered = sorted(item_ids)
    rng = random.Random(random_seed)
    rng.shuffle(ordered)

    train_n = int(n * train_ratio / 100)
    val_n = int(n * val_ratio / 100)
    test_n = int(n * test_ratio / 100)
    remainder = n - train_n - val_n - test_n

    counts = {"train": train_n, "val": val_n, "test": test_n}
    for key in ("train", "val", "test"):
        if remainder <= 0:
            break
        counts[key] += 1
        remainder -= 1

    result: list[tuple[int, SplitType]] = []
    idx = 0
    for split_type in ("train", "val", "test"):
        count = counts[split_type]
        for _ in range(count):
            if idx >= n:
                break
            result.append((ordered[idx], split_type))
            idx += 1

    return result
