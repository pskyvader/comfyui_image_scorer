"""Tests for sparse seeding, extension bounds, and the merge dedupe.

The failure these guard against is a cap that reshapes enumeration: a seed
dropped by the maximum never comes back, a full-coverage column turns every
intersected partner into a copy of itself, and identical match sets were stored
many times per level.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from .. import frequent_combinations as frequent_combinations_module
from ..frequent_combinations import (
    create_qualifying_extension_mask,
    generate_combinations,
    generate_combinations_sparse,
)


def _matrix() -> np.ndarray:
    matrix = np.zeros((7, 5), dtype=bool)
    matrix[0:4, 0] = True
    matrix[0:6, 1] = True
    matrix[4:7, 2] = True
    matrix[4:6, 3] = True
    matrix[:, 4] = True
    return matrix


def _results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    depth: int,
    property_block_size: int | None = None,
):
    monkeypatch.setattr(
        frequent_combinations_module, "analysis_dir", tmp_path
    )
    return generate_combinations_sparse(
        _matrix(),
        np.arange(7),
        max_combination_size=depth,
        minimum_matching_images=2,
        maximum_matching_images=4,
        memory_budget_gb=1.0,
        property_block_size=property_block_size,
    )


@pytest.mark.parametrize("property_block_size", [None, 2])
def test_sparse_seeds_ignore_the_maximum_and_drop_full_coverage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    property_block_size: int | None,
) -> None:
    results = _results(monkeypatch, tmp_path, 1, property_block_size)
    # Column 1 matches 6 of 7 images: kept despite being over the maximum.
    # Column 4 matches every image: dropped because its intersections only
    # reproduce the other condition.
    assert results.combination_at(1) == (0,)
    assert results.combination_at(2) == (1,)
    assert results.combination_at(3) == (2,)
    assert results.combination_at(4) == (3,)
    assert len(results) == 5
    assert list(results.image_rows_at(1)) == [0, 1, 2, 3]


@pytest.mark.parametrize("property_block_size", [None, 2])
def test_sparse_children_of_wide_parents_rescue_and_dedupe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    property_block_size: int | None,
) -> None:
    results = _results(monkeypatch, tmp_path, 2, property_block_size)
    # (0, 1) counts 4 images, (1, 2) counts 2 through the over-maximum seed
    # column 1, and (1, 3) plus (2, 3) repeat the {4, 5} set of (1, 2).
    # The blocked route emits qualifiers block by block, so keep order free.
    assert len(results) == 7
    found = {
        results.combination_at(5): tuple(results.image_rows_at(5)),
        results.combination_at(6): tuple(results.image_rows_at(6)),
    }
    assert found == {(0, 1): (0, 1, 2, 3), (1, 2): (4, 5)}
    cache = results.cache_directory
    assert cache is not None
    with (cache / "sparse_level_02_complete.json").open("r", encoding="utf-8") as source:
        summary = json.load(source)
    assert summary["combination_count"] == 2
    assert summary["image_id_count"] == 6


def test_create_qualifying_extension_mask_respects_bounds_and_order() -> None:
    shared = np.array([[5, 3, 2], [5, 3, 2]])
    mask = create_qualifying_extension_mask(
        shared,
        np.array([1, 0]),
        np.arange(3),
        minimum_matching_images=2,
        maximum_matching_images=4,
    )
    assert list(np.nonzero(mask)[1]) == [2, 1, 2]


def _unused_finder(*_args: object, **_kwargs: object) -> tuple[np.ndarray, np.ndarray]:
    return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)


def test_dense_level_one_drops_full_coverage_and_ignores_the_maximum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        frequent_combinations_module, "analysis_dir", tmp_path
    )
    matrix = np.zeros((7, 3), dtype=bool)
    matrix[0:3, 0] = True
    matrix[2:7, 1] = True
    matrix[:, 2] = True
    combinations, matching_rows = generate_combinations(
        matrix,
        np.arange(7),
        max_combination_size=1,
        combination_finder=_unused_finder,
        minimum_matching_images=2,
        maximum_matching_images=2,
    )
    # Column 0 exceeds the maximum but has legal children, column 1 is over the
    # maximum, and column 2 matches every image.
    assert [tuple(combination) for combination in combinations] == [(0,), (1,)]
    assert [sorted(rows.tolist()) for rows in matching_rows] == [
        [0, 1, 2],
        [2, 3, 4, 5, 6],
    ]
