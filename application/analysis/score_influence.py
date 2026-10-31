"""Condition extraction and fixed-combination influence analysis."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
import time
from typing import Any, Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt
from scipy.sparse import coo_matrix
from tqdm.auto import tqdm

from ...core.io.serialization import atomic_write_json, extract_prompt_tags, load_json
from ...core.observability.logger import ModuleLogger, get_logger
from ...domain.vectors.terms import extract_terms
from .row_fields import as_number, as_weight_map

logger: ModuleLogger = get_logger(__name__)

CATEGORICAL_FAMILIES: tuple[str, ...] = ("model", "sampler", "scheduler", "lora")
NUMERIC_FAMILIES: tuple[str, ...] = (
    "cfg",
    "steps",
    "clip_skip",
    "final_width",
    "final_height",
    "final_aspect_ratio",
)

Condition = tuple[str, str]
Combination = tuple[int, ...]

FOLD_RESULTS_DTYPE = np.dtype(
    [
        ("combination_index", np.int64),
        ("fold", np.int64),
        ("image_count", np.int64),
        ("observed", np.float64),
        ("predicted", np.float64),
        ("lift", np.float64),
        ("depth", np.int64),
    ]
)


class SparseCombinationSource(Protocol):
    """Indexed combinations whose matching rows can be read without materializing all records."""

    def __len__(self) -> int: ...

    def combination_at(self, index: int) -> Combination: ...

    def image_rows_at(self, index: int) -> npt.NDArray[np.intp]: ...


@runtime_checkable
class SparseCombinationArraySource(Protocol):
    """Sparse sources that can expose their level arrays without copying them."""

    def image_match_arrays(
        self,
    ) -> Sequence[tuple[npt.NDArray[np.int64], npt.NDArray[np.int64]]]: ...


@dataclass(frozen=True)
class ConditionData:
    """Per-image condition labels and their packed image masks."""

    condition_names: list[str]
    raw_condition_count: int
    image_names: list[str]
    row_scores: npt.NDArray[np.float64]
    property_image_bitmasks: list[int]


@dataclass(frozen=True)
class CombinationInfluence:
    """Leave-one-fold measurements and their permutation noise floor."""

    fold_results: list[tuple[int, int, int, float, float, float, int]]
    lift_sum: npt.NDArray[np.float64]
    lift_count: npt.NDArray[np.int64]
    matching_image_counts: npt.NDArray[np.int64]
    null_lifts: npt.NDArray[np.float64]


@dataclass(frozen=True)
class ScoreInfluenceCacheParams:
    """Inputs that make a combination-influence cache result reusable."""

    row_scores_sha256: str
    minimum_matching_images: int
    maximum_matching_images: int
    fold_count: int
    permutation_rounds: int
    seed: int
    bootstrap_iterations: int
    bootstrap_seed: int
    score_form: str
    max_combination_size: int
    numeric_bins: int
    memory_budget_gb: float
    property_block_size: int | None

    def cache_key(self) -> str:
        payload = json.dumps(
            [
                self.row_scores_sha256,
                self.minimum_matching_images,
                self.maximum_matching_images,
                self.fold_count,
                self.permutation_rounds,
                self.seed,
                self.bootstrap_iterations,
                self.bootstrap_seed,
                self.score_form,
                self.max_combination_size,
                self.numeric_bins,
                self.memory_budget_gb,
                self.property_block_size,
            ],
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        return hashlib.blake2b(
            b"score-influence-v1" + payload, digest_size=16
        ).hexdigest()


@dataclass(frozen=True)
class ScoreInfluenceCache:
    """Cached combination and family statistics without derived display rows."""

    combination_influence: CombinationInfluence
    family_comparable: npt.NDArray[np.intp]
    family_observed: npt.NDArray[np.float64]
    family_p_values: npt.NDArray[np.float64]
    family_critical_value: float
    family_iterations: int


def score_influence_cache_paths(
    cache_directory: Path, params: ScoreInfluenceCacheParams
) -> tuple[Path, Path]:
    """Return the NPZ and JSON paths for one analysis-parameter key."""
    stem = f"score_influence_{params.cache_key()}"
    return cache_directory / f"{stem}.npz", cache_directory / f"{stem}.json"


def load_score_influence_cache(
    cache_directory: Path | None,
    params: ScoreInfluenceCacheParams,
) -> ScoreInfluenceCache | None:
    """Load cached statistics, returning None when absent or unreadable."""
    if cache_directory is None or not cache_directory.is_dir():
        return None
    npz_path, json_path = score_influence_cache_paths(cache_directory, params)
    if not npz_path.is_file() or not json_path.is_file():
        return None
    metadata, error = load_json(str(json_path), expect=dict)
    if (
        error is not None
        or metadata is None
        or metadata.get("cache_key") != params.cache_key()
    ):
        return None
    try:
        with np.load(npz_path, allow_pickle=False) as data:
            lift_sum = np.asarray(data["lift_sum"], dtype=np.float64)
            lift_count = np.asarray(data["lift_count"], dtype=np.int64)
            matching_image_counts = np.asarray(
                data["matching_image_counts"], dtype=np.int64
            )
            null_lifts = np.asarray(data["null_lifts"], dtype=np.float64)
            raw_fold_results = np.asarray(data["fold_results"])
            family_comparable = np.asarray(data["family_comparable"], dtype=np.intp)
            family_observed = np.asarray(data["family_observed"], dtype=np.float64)
            family_p_values = np.asarray(data["family_p_values"], dtype=np.float64)
            family_critical_value = float(
                np.asarray(data["family_critical_value"]).reshape(-1)[0]
            )
            family_iterations = int(
                np.asarray(data["family_iterations"]).reshape(-1)[0]
            )
            fold_results = [
                (
                    int(row["combination_index"]),
                    int(row["fold"]),
                    int(row["image_count"]),
                    float(row["observed"]),
                    float(row["predicted"]),
                    float(row["lift"]),
                    int(row["depth"]),
                )
                for row in raw_fold_results
            ]
    except (KeyError, OSError, ValueError) as error:
        logger.warning("Failed to load score influence cache %s: %s", npz_path, error)
        return None
    return ScoreInfluenceCache(
        combination_influence=CombinationInfluence(
            fold_results=fold_results,
            lift_sum=lift_sum,
            lift_count=lift_count,
            matching_image_counts=matching_image_counts,
            null_lifts=null_lifts,
        ),
        family_comparable=family_comparable,
        family_observed=family_observed,
        family_p_values=family_p_values,
        family_critical_value=family_critical_value,
        family_iterations=family_iterations,
    )


def save_score_influence_cache(
    cache_directory: Path,
    cache: ScoreInfluenceCache,
    params: ScoreInfluenceCacheParams,
    condition_names: Sequence[str],
) -> None:
    """Write cached statistics as an NPZ array bundle plus JSON metadata.

    The NPZ stores `combination_index`, which maps every result row to its
    position in the combination source, and `condition_names`, which resolves
    every combination ID through the level-one combinations.
    """
    cache_directory.mkdir(parents=True, exist_ok=True)
    npz_path, json_path = score_influence_cache_paths(cache_directory, params)
    fold_results = np.array(
        [
            (
                combination_index,
                fold,
                image_count,
                observed,
                predicted,
                lift,
                depth,
            )
            for combination_index, fold, image_count, observed, predicted, lift, depth in cache.combination_influence.fold_results
        ],
        dtype=FOLD_RESULTS_DTYPE,
    )
    temporary_path = npz_path.with_name(npz_path.name + ".tmp")
    with temporary_path.open("wb") as output:
        np.savez(
            output,
            combination_index=np.arange(
                cache.combination_influence.matching_image_counts.size,
                dtype=np.int64,
            ),
            condition_names=np.asarray(list(condition_names)),
            lift_sum=cache.combination_influence.lift_sum,
            lift_count=cache.combination_influence.lift_count,
            matching_image_counts=cache.combination_influence.matching_image_counts,
            null_lifts=cache.combination_influence.null_lifts,
            fold_results=fold_results,
            family_comparable=cache.family_comparable,
            family_observed=cache.family_observed,
            family_p_values=cache.family_p_values,
            family_critical_value=np.asarray(cache.family_critical_value),
            family_iterations=np.asarray(cache.family_iterations),
        )
    os.replace(temporary_path, npz_path)
    atomic_write_json(
        str(json_path),
        {"cache_key": params.cache_key(), "params": asdict(params)},
        indent=None,
    )


def read_condition_elements(
    scored: Mapping[str, float],
    rows: Iterable[Mapping[str, Any]],
    minimum_matching_images: int,
    numeric_bins: int,
) -> dict[str, list[Condition]]:
    """Extract prompt, categorical, and binned numeric conditions by image."""
    prompts: defaultdict[str, dict[str, str]] = defaultdict(dict)
    categorical: defaultdict[str, dict[str, str]] = defaultdict(dict)
    numeric: defaultdict[str, dict[str, float]] = defaultdict(dict)

    for row in rows:
        filename, payload = next(iter(row.items()))
        filename = str(filename)
        if filename not in scored:
            continue

        positive = extract_prompt_tags(payload)
        if positive:
            prompts[filename]["positive_prompt"] = positive
        negative = payload.get("negative_prompt")
        if isinstance(negative, str) and negative:
            prompts[filename]["negative_prompt"] = negative

        for family in CATEGORICAL_FAMILIES:
            weights = as_weight_map(payload.get(family))
            if weights:
                name, _ = max(weights.items(), key=lambda item: item[1])
                if name:
                    categorical[filename][family] = name

        for family in NUMERIC_FAMILIES:
            value = as_number(payload.get(family))
            if value is not None:
                numeric[filename][family] = value

    elements: dict[str, list[Condition]] = {}
    for filename, family_prompts in prompts.items():
        carried: list[Condition] = []
        for family, text in family_prompts.items():
            carried.extend((family, term) for term, _, _ in extract_terms(text).terms)
        carried.extend(categorical[filename].items())
        elements[filename] = carried

    edges_by_family: dict[str, list[float]] = {}
    for family in NUMERIC_FAMILIES:
        values = np.array(
            [numeric[name][family] for name in elements if family in numeric[name]],
            dtype=np.float64,
        )
        # Family-level: the measurable unit is an individual bin label, not the
        # family's total record count, so only a floor is applied here.
        if values.size < minimum_matching_images:
            continue
        edges_by_family[family] = [
            float(edge)
            for edge in np.unique(
                np.quantile(values, np.linspace(0.0, 1.0, numeric_bins + 1))
            )
        ]

    for filename, carried in elements.items():
        for family in NUMERIC_FAMILIES:
            value = numeric[filename].get(family)
            edges = edges_by_family.get(family)
            if value is not None and edges is not None:
                carried.append((family, _numeric_bin_label(value, edges)))

    return elements


def _numeric_bin_label(value: float, edges: Sequence[float]) -> str:
    for index in range(len(edges) - 1):
        if edges[index] <= value <= edges[index + 1]:
            low, high = f"{edges[index]:.2f}", f"{edges[index + 1]:.2f}"
            return low if index + 2 == len(edges) else f"{low}-{high}"
    return f"{value:.2f}"


def build_condition_data(
    elements_by_image: Mapping[str, Sequence[Condition]],
    scores: Mapping[str, float],
    minimum_matching_images: int,
) -> ConditionData:
    """Build ordered condition IDs, image scores, and packed image masks.

    Conditions are kept when their recorded image count reaches the minimum and
    they do not cover every analyzed image; identical image masks keep only the
    lexicographically first label.
    """
    condition_counts: Counter[Condition] = Counter()
    for carried in elements_by_image.values():
        condition_counts.update(carried)

    carrier_count = len(elements_by_image)
    surviving_conditions = sorted(
        condition
        for condition, count in condition_counts.items()
        if minimum_matching_images <= count < carrier_count
    )
    condition_names = [f"{family}: {value}" for family, value in surviving_conditions]
    condition_indices = {
        condition: index for index, condition in enumerate(surviving_conditions)
    }
    image_names = list(elements_by_image)
    image_rows = {name: row for row, name in enumerate(image_names)}
    row_scores = np.array([scores[name] for name in image_names], dtype=np.float64)

    property_image_bitmasks = [0] * len(surviving_conditions)
    for filename, carried in elements_by_image.items():
        row_bit = 1 << image_rows[filename]
        for condition in carried:
            condition_index = condition_indices.get(condition)
            if condition_index is not None:
                property_image_bitmasks[condition_index] |= row_bit

    kept_masks: set[int] = set()
    kept_indices: list[int] = []
    for index, mask in enumerate(property_image_bitmasks):
        if mask not in kept_masks:
            kept_masks.add(mask)
            kept_indices.append(index)
    if len(kept_indices) < len(surviving_conditions):
        logger.info(
            "dropped %d conditions matching the same images as an earlier condition",
            len(surviving_conditions) - len(kept_indices),
        )
    condition_names = [condition_names[index] for index in kept_indices]
    property_image_bitmasks = [property_image_bitmasks[index] for index in kept_indices]

    return ConditionData(
        condition_names=condition_names,
        raw_condition_count=len(condition_counts),
        image_names=image_names,
        row_scores=row_scores,
        property_image_bitmasks=property_image_bitmasks,
    )


def _leave_one_fold_lifts(
    matching_image_rows: npt.NDArray[np.intp],
    values: npt.NDArray[np.float64],
    fold_assignment: npt.NDArray[np.intp],
    fold_count: int,
    minimum_matching_images: int,
    maximum_matching_images: int,
) -> tuple[int, list[tuple[int, int, float, float, float]]]:
    matching_values = values[matching_image_rows]
    matching_image_count = int(matching_image_rows.size)
    if (
        matching_image_count < minimum_matching_images
        or matching_image_count > maximum_matching_images
    ):
        return matching_image_count, []

    folds = fold_assignment[matching_image_rows]
    image_counts_by_fold = np.bincount(folds, minlength=fold_count)
    score_sums_by_fold = np.bincount(
        folds, weights=matching_values, minlength=fold_count
    )
    total_image_count = int(image_counts_by_fold.sum())
    total_score_sum = float(score_sums_by_fold.sum())
    lifts = []
    for fold in range(fold_count):
        fold_image_count = int(image_counts_by_fold[fold])
        other_image_count = total_image_count - fold_image_count
        # Both fold sizes stay under the maximum: each is at most the total,
        # which the early return already bounded.
        if (
            fold_image_count < minimum_matching_images
            or other_image_count < minimum_matching_images
        ):
            continue
        observed = float(score_sums_by_fold[fold] / fold_image_count)
        predicted = float(
            (total_score_sum - score_sums_by_fold[fold]) / other_image_count
        )
        lifts.append(
            (fold, fold_image_count, observed, predicted, observed - predicted)
        )
    return matching_image_count, lifts


def analyze_combination_influence(
    parent_combinations: Sequence[Combination],
    matching_image_rows_by_combination: Mapping[Combination, npt.NDArray[np.intp]],
    row_scores: npt.NDArray[np.float64],
    minimum_matching_images: int,
    maximum_matching_images: int,
    fold_count: int,
    permutation_rounds: int,
    seed: int,
) -> CombinationInfluence:
    """Measure fixed combinations by fold-held-out lifts and shuffled-score maxima."""
    combination_count = len(parent_combinations)
    combination_at = parent_combinations.__getitem__

    def image_rows_at(index: int) -> npt.NDArray[np.intp]:
        return matching_image_rows_by_combination[parent_combinations[index]]

    fold_results, lift_sum, lift_count, matching_image_counts, fold_assignment = (
        _collect_combination_fold_results(
            combination_count,
            combination_at,
            image_rows_at,
            row_scores,
            minimum_matching_images,
            maximum_matching_images,
            fold_count,
            seed,
        )
    )
    null_started = time.perf_counter()
    null_lifts = _calculate_null_lifts(
        combination_count,
        combination_at,
        image_rows_at,
        row_scores,
        fold_assignment,
        fold_count,
        minimum_matching_images,
        maximum_matching_images,
        permutation_rounds,
        seed,
    )
    _log_null_lifts(null_lifts, null_started)
    return CombinationInfluence(
        fold_results=fold_results,
        lift_sum=lift_sum,
        lift_count=lift_count,
        matching_image_counts=matching_image_counts,
        null_lifts=null_lifts,
    )


def analyze_sparse_combination_influence(
    combinations: SparseCombinationSource,
    row_scores: npt.NDArray[np.float64],
    minimum_matching_images: int,
    maximum_matching_images: int,
    fold_count: int,
    permutation_rounds: int,
    seed: int,
) -> CombinationInfluence:
    """Analyze sparse cached combinations by index without building a matching-row dictionary."""
    combination_count = len(combinations)
    fold_results, lift_sum, lift_count, matching_image_counts, fold_assignment = (
        _collect_combination_fold_results(
            combination_count,
            combinations.combination_at,
            combinations.image_rows_at,
            row_scores,
            minimum_matching_images,
            maximum_matching_images,
            fold_count,
            seed,
        )
    )
    null_started = time.perf_counter()
    if isinstance(combinations, SparseCombinationArraySource):
        null_lifts = _calculate_sparse_null_lifts(
            combinations.image_match_arrays(),
            row_scores,
            fold_assignment,
            fold_count,
            minimum_matching_images,
            maximum_matching_images,
            permutation_rounds,
            seed,
        )
    else:
        null_lifts = _calculate_null_lifts(
            combination_count,
            combinations.combination_at,
            combinations.image_rows_at,
            row_scores,
            fold_assignment,
            fold_count,
            minimum_matching_images,
            maximum_matching_images,
            permutation_rounds,
            seed,
        )
    _log_null_lifts(null_lifts, null_started)
    return CombinationInfluence(
        fold_results=fold_results,
        lift_sum=lift_sum,
        lift_count=lift_count,
        matching_image_counts=matching_image_counts,
        null_lifts=null_lifts,
    )


def _collect_combination_fold_results(
    combination_count: int,
    combination_at: Callable[[int], Combination],
    image_rows_at: Callable[[int], npt.NDArray[np.intp]],
    row_scores: npt.NDArray[np.float64],
    minimum_matching_images: int,
    maximum_matching_images: int,
    fold_count: int,
    seed: int,
) -> tuple[
    list[tuple[int, int, int, float, float, float, int]],
    npt.NDArray[np.float64],
    npt.NDArray[np.int64],
    npt.NDArray[np.int64],
    npt.NDArray[np.intp],
]:
    started = time.perf_counter()
    fold_assignment = (
        np.random.default_rng(seed).permutation(len(row_scores)) % fold_count
    )
    fold_results: list[tuple[int, int, int, float, float, float, int]] = []
    lift_sum = np.zeros(combination_count, dtype=np.float64)
    lift_count = np.zeros(combination_count, dtype=np.int64)
    matching_image_counts = np.zeros(combination_count, dtype=np.int64)

    for combination_index in tqdm(range(combination_count), desc="fold analysis"):
        combination = combination_at(combination_index)
        if not combination:
            continue
        matching_rows, lifts = _leave_one_fold_lifts(
            image_rows_at(combination_index),
            row_scores,
            fold_assignment,
            fold_count,
            minimum_matching_images,
            maximum_matching_images,
        )
        if not lifts:
            continue
        matching_image_counts[combination_index] = matching_rows
        for fold, image_count, observed, predicted, lift in lifts:
            fold_results.append(
                (
                    combination_index,
                    fold,
                    image_count,
                    observed,
                    predicted,
                    lift,
                    len(combination),
                )
            )
            lift_sum[combination_index] += lift
            lift_count[combination_index] += 1

    logger.info(
        "fold analysis: %d measurements in %.0fs",
        len(fold_results),
        time.perf_counter() - started,
    )
    return fold_results, lift_sum, lift_count, matching_image_counts, fold_assignment


def _calculate_null_lifts(
    combination_count: int,
    combination_at: Callable[[int], Combination],
    image_rows_at: Callable[[int], npt.NDArray[np.intp]],
    row_scores: npt.NDArray[np.float64],
    fold_assignment: npt.NDArray[np.intp],
    fold_count: int,
    minimum_matching_images: int,
    maximum_matching_images: int,
    permutation_rounds: int,
    seed: int,
) -> npt.NDArray[np.float64]:
    generator = np.random.default_rng(seed)
    null_lifts = np.empty(permutation_rounds, dtype=np.float64)
    for round_index in tqdm(range(permutation_rounds), desc="null rounds"):
        shuffled = generator.permutation(row_scores)
        best_lift = 0.0
        for combination_index in range(combination_count):
            combination = combination_at(combination_index)
            if not combination:
                continue
            _, lifts = _leave_one_fold_lifts(
                image_rows_at(combination_index),
                shuffled,
                fold_assignment,
                fold_count,
                minimum_matching_images,
                maximum_matching_images,
            )
            if lifts:
                mean_lift = sum(lift[4] for lift in lifts) / len(lifts)
                best_lift = max(best_lift, abs(mean_lift))
        null_lifts[round_index] = best_lift
    return null_lifts


def _calculate_sparse_null_lifts(
    image_match_levels: Sequence[tuple[npt.NDArray[np.int64], npt.NDArray[np.int64]]],
    row_scores: npt.NDArray[np.float64],
    fold_assignment: npt.NDArray[np.intp],
    fold_count: int,
    minimum_matching_images: int,
    maximum_matching_images: int,
    permutation_rounds: int,
    seed: int,
) -> npt.NDArray[np.float64]:
    # Bound temporary COO arrays instead of constructing one matrix for all levels.
    max_batch_matches = 2_000_000
    batch_ranges = [
        (level_index, start, stop)
        for level_index, (offsets, _image_ids) in enumerate(image_match_levels)
        for start, stop in _matching_batch_ranges(offsets, max_batch_matches)
    ]
    logger.info(
        "null: %d rounds over %d batches", permutation_rounds, len(batch_ranges)
    )
    null_lifts = np.zeros(permutation_rounds, dtype=np.float64)
    generator = np.random.default_rng(seed)
    for round_index in tqdm(range(permutation_rounds), desc="null rounds", position=0):
        shuffled = generator.permutation(row_scores)
        round_best_lift = 0.0
        for level_index, start, stop in tqdm(
            batch_ranges,
            desc="sparse null batches",
            unit="batch",
            leave=False,
            position=1,
        ):
            offsets, image_ids = image_match_levels[level_index]
            batch_offsets = offsets[start : stop + 1]
            first_image = int(batch_offsets[0])
            last_image = int(batch_offsets[-1])
            batch_image_ids = image_ids[first_image:last_image]
            batch_combination_count = stop - start
            batch_match_counts = np.diff(batch_offsets)
            batch_combination_rows = np.repeat(
                np.arange(batch_combination_count, dtype=np.int32),
                batch_match_counts,
            )
            batch_fold_rows = (
                batch_combination_rows * fold_count + fold_assignment[batch_image_ids]
            )
            batch_fold_counts = np.bincount(
                batch_fold_rows,
                minlength=batch_combination_count * fold_count,
            ).reshape(batch_combination_count, fold_count)
            fold_membership = coo_matrix(
                (
                    np.ones(batch_image_ids.size, dtype=np.bool_),
                    (batch_fold_rows, batch_image_ids),
                ),
                shape=(batch_combination_count * fold_count, len(row_scores)),
                dtype=np.bool_,
            ).tocsr()

            total_counts = batch_fold_counts.sum(axis=1)
            other_counts = total_counts[:, None] - batch_fold_counts
            valid_folds = (
                (batch_fold_counts >= minimum_matching_images)
                & (other_counts >= minimum_matching_images)
                & (batch_fold_counts <= maximum_matching_images)
                & (other_counts <= maximum_matching_images)
            )
            valid_fold_counts = valid_folds.sum(axis=1)

            fold_score_sums = np.asarray(fold_membership @ shuffled).reshape(
                batch_combination_count, fold_count
            )
            total_score_sums = fold_score_sums.sum(axis=1)
            lifts = np.zeros_like(fold_score_sums)
            np.divide(
                fold_score_sums,
                batch_fold_counts,
                out=lifts,
                where=valid_folds,
            )
            predicted = np.zeros_like(fold_score_sums)
            np.divide(
                total_score_sums[:, None] - fold_score_sums,
                other_counts,
                out=predicted,
                where=valid_folds,
            )
            lifts -= predicted
            mean_lifts = np.divide(
                (lifts * valid_folds).sum(axis=1),
                valid_fold_counts,
                out=np.zeros(batch_combination_count, dtype=np.float64),
                where=valid_fold_counts > 0,
            )
            round_best_lift = max(
                round_best_lift,
                float(np.abs(mean_lifts).max(initial=0.0)),
            )
        null_lifts[round_index] = round_best_lift

    return null_lifts


def _matching_batch_ranges(
    offsets: npt.NDArray[np.int64], max_batch_matches: int
) -> Iterable[tuple[int, int]]:
    combination_count = len(offsets) - 1
    start = 0
    while start < combination_count:
        stop = start + 1
        while (
            stop < combination_count
            and int(offsets[stop + 1]) - int(offsets[start]) <= max_batch_matches
        ):
            stop += 1
        yield start, stop
        start = stop


def _log_null_lifts(null_lifts: npt.NDArray[np.float64], started: float) -> None:
    logger.info(
        "null: p50 %+.4f p95 %+.4f max %+.4f in %.0fs",
        np.quantile(null_lifts, 0.5),
        np.quantile(null_lifts, 0.95),
        null_lifts.max(),
        time.perf_counter() - started,
    )
