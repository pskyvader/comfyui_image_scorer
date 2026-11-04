"""Tests for condition gates, combination measurement bounds, and caches.

The failure these guard against is silent reshaping of the condition set: a
family killed by an upper bound, a full-coverage condition, or a duplicated
image mask changes which combinations can exist, so every gate is asserted on
surviving labels and masks rather than only on counts.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest

from ..score_influence import (
    CombinationInfluence,
    ScoreInfluenceCache,
    ScoreInfluenceCacheParams,
    analyze_combination_influence,
    analyze_sparse_combination_influence,
    build_condition_data,
    load_score_influence_cache,
    read_condition_elements,
    save_score_influence_cache,
)


def _test_params() -> ScoreInfluenceCacheParams:
    return ScoreInfluenceCacheParams(
        row_scores_sha256="0" * 64,
        minimum_matching_images=2,
        maximum_matching_images=5,
        fold_count=2,
        permutation_rounds=1,
        seed=1,
        bootstrap_iterations=10,
        bootstrap_seed=1,
        score_form="public",
        max_combination_size=2,
        numeric_bins=2,
        memory_budget_gb=1.0,
        property_block_size=None,
        condition_names_sha256="0" * 64,
    )


def _rows(rows: dict[str, dict[str, Any]]) -> list[dict[str, dict[str, Any]]]:
    return [{name: payload} for name, payload in rows.items()]


def test_read_condition_elements_keeps_numeric_families_above_the_minimum() -> None:
    scores = {f"{name}.png": 0.5 for name in "abcd"}
    payloads = {
        "a.png": {"positive_prompt": "word", "steps": "20", "cfg": "7.5"},
        "b.png": {"positive_prompt": "word", "steps": "30", "cfg": "7.5"},
        "c.png": {"positive_prompt": "word", "steps": "40"},
        "d.png": {"positive_prompt": "word", "steps": "50"},
    }
    elements = read_condition_elements(
        scores, _rows(payloads), minimum_matching_images=3, numeric_bins=2
    )
    families = {family for carried in elements.values() for family, _ in carried}
    assert "steps" in families
    # Two recorded values are below the family floor, so no cfg bins appear.
    assert "cfg" not in families
    assert all(elements[name] for name in scores)


def test_build_condition_data_requires_the_minimum_and_drops_full_coverage() -> None:
    names = [f"{name}.png" for name in "abcdef"]
    scores = {name: 0.5 for name in names}
    elements = {
        "a.png": [("sampler", "big"), ("sampler", "everyshot")],
        "b.png": [("sampler", "big"), ("sampler", "everyshot")],
        "c.png": [("sampler", "big"), ("sampler", "everyshot")],
        "d.png": [("sampler", "tiny"), ("sampler", "everyshot")],
        "e.png": [("sampler", "tiny"), ("sampler", "everyshot")],
        "f.png": [("sampler", "everyshot")],
    }
    data = build_condition_data(elements, scores, minimum_matching_images=3)
    assert data.raw_condition_count == 3
    assert data.condition_names == ["sampler: big"]
    assert data.property_image_bitmasks == [0b111]
    assert np.allclose(data.row_scores, 0.5)


def test_build_condition_data_keeps_the_first_label_for_identical_masks() -> None:
    names = [f"{name}.png" for name in "abcde"]
    scores = {name: 0.5 for name in names}
    elements = {
        "a.png": [("model", "x"), ("sampler", "alpha"), ("sampler", "beta")],
        "b.png": [("model", "x"), ("sampler", "alpha"), ("sampler", "beta")],
        "c.png": [("sampler", "alpha"), ("sampler", "beta")],
        "d.png": [("sampler", "alpha"), ("sampler", "beta")],
        "e.png": [],
    }
    data = build_condition_data(elements, scores, minimum_matching_images=2)
    assert data.raw_condition_count == 3
    assert data.condition_names == ["model: x", "sampler: alpha"]
    assert data.property_image_bitmasks == [0b11, 0b1111]


def test_analyze_combination_influence_bounds_its_measurements() -> None:
    rows = np.arange(10)
    parent_combinations = [(0,), (1,), (2,)]
    matching_rows = {
        (0,): rows,
        (1,): np.arange(6),
        (2,): np.arange(5),
    }
    row_scores = np.array([0.9, 0.1, 1.0, 1.0, 1.0, 1.0, 1.0, 0.2, 1.0, 1.0])
    influence = analyze_combination_influence(
        parent_combinations,
        matching_rows,
        row_scores,
        minimum_matching_images=2,
        maximum_matching_images=5,
        fold_count=2,
        permutation_rounds=1,
        seed=1,
    )
    assert list(influence.matching_image_counts) == [0, 0, 5]
    assert list(influence.lift_count) == [0, 0, 2]
    assert set(index for index, *_ in influence.fold_results) == {2}
    assert set(image_count for _, _, image_count, *_ in influence.fold_results) == {2, 3}


def test_save_score_influence_cache_writes_identifiers(
    tmp_path: Path,
) -> None:
    counts = np.array([3, 4, 5], dtype=np.int64)
    cache = ScoreInfluenceCache(
        combination_influence=CombinationInfluence(
            fold_results=[
                (1, 0, 2, 0.4, 0.2, 0.2, 1),
                (1, 1, 2, 0.5, 0.2, 0.3, 1),
            ],
            lift_sum=np.array([0.0, 0.5, 0.0]),
            lift_count=np.array([0, 2, 0], dtype=np.int64),
            matching_image_counts=counts,
            null_lifts=np.array([0.1, 0.2]),
        ),
        family_comparable=np.array([0, 2], dtype=np.intp),
        family_observed=np.array([0.4, 0.5]),
        family_p_values=np.array([0.02, 0.5]),
        family_critical_value=0.09,
        family_iterations=10,
    )
    params = _test_params()
    condition_names = ["model: x", "sampler: alpha", "sampler: big"]
    save_score_influence_cache(tmp_path, cache, params, condition_names)

    loaded = load_score_influence_cache(tmp_path, params)
    assert loaded is not None
    assert np.array_equal(
        loaded.combination_influence.matching_image_counts, counts
    )
    assert loaded.family_critical_value == pytest.approx(0.09)

    npz_path = tmp_path / f"score_influence_{params.cache_key()}.npz"
    with np.load(npz_path, allow_pickle=False) as data:
        assert list(data["combination_index"]) == [0, 1, 2]
        assert list(data["condition_names"]) == condition_names
        assert list(data["matching_image_counts"]) == [3, 4, 5]
    with (tmp_path / f"score_influence_{params.cache_key()}.json").open(
        "r", encoding="utf-8"
    ) as source:
        metadata = json.load(source)
    assert metadata["cache_key"] == params.cache_key()
    assert metadata["params"]["minimum_matching_images"] == 2
    assert metadata["params"]["property_block_size"] is None


def test_score_influence_cache_key_separates_condition_vocabularies() -> None:
    first = _test_params()
    second = replace(first, condition_names_sha256="f" * 64)
    assert first.cache_key() != second.cache_key()


class _SparseLevelSource:
    """Single-level sparse source whose level arrays back its row lookups."""

    def __init__(self, row_groups: list[npt.NDArray[np.intp]]) -> None:
        sizes = [group.size for group in row_groups]
        offsets = np.concatenate(([0], np.cumsum(sizes, dtype=np.int64)))
        image_ids = (
            np.concatenate(row_groups).astype(np.int64)
            if row_groups
            else np.empty(0, dtype=np.int64)
        )
        self._row_groups = row_groups
        self._level = (offsets, image_ids)

    def __len__(self) -> int:
        return len(self._row_groups) + 1

    def combination_at(self, index: int) -> tuple[int, ...]:
        if index == 0:
            return ()
        return (index - 1,)

    def image_rows_at(self, index: int) -> npt.NDArray[np.intp]:
        if index == 0:
            return np.empty(0, dtype=np.intp)
        return self._row_groups[index - 1]

    def image_match_arrays(
        self,
    ) -> list[tuple[npt.NDArray[np.int64], npt.NDArray[np.int64]]]:
        return [self._level]


def test_analyze_sparse_combination_influence_matches_the_dict_path() -> None:
    source = _SparseLevelSource(
        [
            np.arange(8, dtype=np.intp),
            np.arange(3, 9, dtype=np.intp),
            np.array([1, 4, 6, 7, 9, 10], dtype=np.intp),
            np.arange(9, dtype=np.intp),
        ]
    )
    row_scores = np.arange(12, dtype=np.float64)
    shared_bounds = {"minimum_matching_images": 2, "maximum_matching_images": 8}
    sparse = analyze_sparse_combination_influence(
        source,
        row_scores,
        fold_count=3,
        permutation_rounds=3,
        seed=7,
        **shared_bounds,
    )
    sparse_two_rounds = analyze_sparse_combination_influence(
        source,
        row_scores,
        fold_count=3,
        permutation_rounds=2,
        seed=7,
        **shared_bounds,
    )
    mapping: dict[tuple[int, ...], npt.NDArray[np.intp]] = {}
    for index in range(len(source)):
        mapping[source.combination_at(index)] = source.image_rows_at(index)
    dense = analyze_combination_influence(
        [source.combination_at(index) for index in range(len(source))],
        mapping,
        row_scores,
        fold_count=3,
        permutation_rounds=3,
        seed=7,
        **shared_bounds,
    )

    assert np.array_equal(sparse.null_lifts, dense.null_lifts)
    assert np.array_equal(sparse_two_rounds.null_lifts, sparse.null_lifts[:2])
    assert sparse.null_lifts.max(initial=0.0) > 0
    assert np.array_equal(sparse.lift_sum, dense.lift_sum)
    assert np.array_equal(sparse.lift_count, dense.lift_count)
    assert np.array_equal(sparse.matching_image_counts, dense.matching_image_counts)
    assert sparse.fold_results == dense.fold_results
    # The last combination's ten matching rows exceed the maximum, so neither
    # path may measure it despite fold sides that would fit individually.
    assert sparse.matching_image_counts[-1] == 0
    assert all(row[0] != len(source) - 1 for row in sparse.fold_results)
