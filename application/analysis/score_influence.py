"""Condition extraction and fixed-combination influence analysis."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import time
from typing import Any

import numpy as np
import numpy.typing as npt
from tqdm.auto import tqdm

from ...core.io.serialization import extract_prompt_tags
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
            carried.extend(
                (family, term)
                for term, _, _ in extract_terms(text).terms
            )
        carried.extend(categorical[filename].items())
        elements[filename] = carried

    edges_by_family: dict[str, list[float]] = {}
    for family in NUMERIC_FAMILIES:
        values = np.array(
            [numeric[name][family] for name in elements if family in numeric[name]],
            dtype=np.float64,
        )
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
    """Build ordered condition IDs, image scores, and packed image masks."""
    condition_counts: Counter[Condition] = Counter()
    for carried in elements_by_image.values():
        condition_counts.update(carried)

    surviving_conditions = sorted(
        condition
        for condition, count in condition_counts.items()
        if count >= minimum_matching_images
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
) -> tuple[int, list[tuple[int, int, float, float, float]]]:
    matching_values = values[matching_image_rows]
    matching_image_count = int(matching_image_rows.size)
    if matching_image_count < minimum_matching_images:
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
    matching_image_rows_by_combination: Mapping[
        Combination, npt.NDArray[np.intp]
    ],
    row_scores: npt.NDArray[np.float64],
    minimum_matching_images: int,
    fold_count: int,
    permutation_rounds: int,
    seed: int,
) -> CombinationInfluence:
    """Measure fixed combinations by fold-held-out lifts and shuffled-score maxima."""
    started = time.perf_counter()
    fold_assignment = np.random.default_rng(seed).permutation(len(row_scores)) % fold_count
    fold_results: list[tuple[int, int, int, float, float, float, int]] = []
    lift_sum = np.zeros(len(parent_combinations), dtype=np.float64)
    lift_count = np.zeros(len(parent_combinations), dtype=np.int64)
    matching_image_counts = np.zeros(len(parent_combinations), dtype=np.int64)

    for combination_index, combination in enumerate(
        tqdm(parent_combinations, desc="fold analysis")
    ):
        if not combination:
            continue
        matching_rows, lifts = _leave_one_fold_lifts(
            matching_image_rows_by_combination[combination],
            row_scores,
            fold_assignment,
            fold_count,
            minimum_matching_images,
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

    null_started = time.perf_counter()
    generator = np.random.default_rng(seed)
    null_lifts = np.empty(permutation_rounds, dtype=np.float64)
    for round_index in tqdm(range(permutation_rounds), desc="null rounds"):
        shuffled = generator.permutation(row_scores)
        best_lift = 0.0
        for combination in parent_combinations:
            if not combination:
                continue
            _, lifts = _leave_one_fold_lifts(
                matching_image_rows_by_combination[combination],
                shuffled,
                fold_assignment,
                fold_count,
                minimum_matching_images,
            )
            if lifts:
                mean_lift = sum(lift[4] for lift in lifts) / len(lifts)
                best_lift = max(best_lift, abs(mean_lift))
        null_lifts[round_index] = best_lift

    logger.info(
        "null: p50 %+.4f p95 %+.4f max %+.4f in %.0fs",
        np.quantile(null_lifts, 0.5),
        np.quantile(null_lifts, 0.95),
        null_lifts.max(),
        time.perf_counter() - null_started,
    )
    return CombinationInfluence(
        fold_results=fold_results,
        lift_sum=lift_sum,
        lift_count=lift_count,
        matching_image_counts=matching_image_counts,
        null_lifts=null_lifts,
    )
