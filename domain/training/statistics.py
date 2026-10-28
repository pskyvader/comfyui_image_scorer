"""Statistical helpers for score comparisons.

Every analyzer in this module reports a p-value per tested term or feature, and
one test per term is never enough to trust: with thousands of terms a plain
0.05 threshold is crossed by chance alone. `benjamini_hochberg` is the
correction used wherever such a family of tests is reported, and
`cliffs_delta` sits beside it because a corrected p-value says "not chance",
not "large".

`max_statistic_bootstrap` exists for the other shape of problem: a whole screen
of thousands of conditions where only the extremes get reported. Correcting only
the reported subset corrects for the wrong family, so that case is handled by
comparing every effect against the distribution of the largest effect the same
resampling produces.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from random import Random
from collections.abc import Callable, Sequence
from typing import Any, cast

import numpy as np
import numpy.typing as npt
from scipy.stats import mannwhitneyu, pearsonr, spearmanr

from ...core.configuration.settings import config


@dataclass(frozen=True)
class CorrelationResult:
    """One correlation coefficient with its bootstrap interval and p-value."""

    coefficient: float
    ci_low: float
    ci_high: float
    p_value: float
    sample_count: int


def benjamini_hochberg(p_values: Sequence[float]) -> npt.NDArray[np.float64]:
    """Return BH-adjusted q-values, monotone and never below the raw p-value."""
    raw = np.asarray(p_values, dtype=np.float64)
    if raw.size == 0:
        return raw

    order = np.argsort(raw, kind="stable")
    ordered: npt.NDArray[np.float64] = raw[order]
    count = ordered.size
    scaled = ordered * count / np.arange(1, count + 1)
    # Enforce monotonicity from the largest p-value downwards, then clip so a
    # corrected value can never report more evidence than its own test.
    monotone: npt.NDArray[np.float64] = np.minimum.accumulate(scaled[::-1])[::-1]
    adjusted: npt.NDArray[np.float64] = np.clip(monotone, 0.0, 1.0)

    result: npt.NDArray[np.float64] = np.empty_like(adjusted)
    result[order] = adjusted
    return result


@dataclass(frozen=True)
class MaxStatisticResult:
    """Family-wise corrected results for one batch of difference-of-mean tests.

    `critical_value` is the reading that matters when a whole family is screened
    at once: the largest effect the procedure expects from noise alone at the
    requested confidence. Any observed effect beyond it survives the family, not
    just its own single test.
    """

    observed: npt.NDArray[np.float64]
    p_values: npt.NDArray[np.float64]
    critical_value: float
    iterations: int


def max_statistic_bootstrap(
    indicators: npt.NDArray[np.bool_],
    values: npt.NDArray[np.float64],
    *,
    seed: int = 0,
    progress: Callable[[int], None] | None = None,
    iterations: int | None = None,
    confidence: float | None = None,
) -> MaxStatisticResult:
    """Correct a whole family of binary-condition effects for multiplicity at once.

    Benjamini-Hochberg controls the false discovery *rate* and assumes the tests
    it corrects are the tests that were run. Screening thousands of conditions
    and reporting only the interesting ones breaks that assumption, because the
    reported set is already the extreme tail. This uses the Westfall-Young max-T
    bootstrap instead, which controls the family-wise error rate without the
    independence assumption and without caring how many conditions were screened.

    Each resample recomputes every condition's difference of means, and the
    largest centred effect across all of them becomes that resample's null
    maximum. A condition is then significant when it beats the distribution of
    that maximum, so its threshold widens automatically when conditions overlap
    and a large effect is shared by many of them.

    Every column must have images on both sides. A condition carried by nearly
    every image has no comparison group, and its effect is just the mean of the
    values, which the resampling reproduces exactly and therefore never rejects.

    `iterations` and `confidence` fall back to the ``analysis_bootstrap_resamples``
    and ``analysis_confidence_level`` training settings when not supplied.
    """
    training_conf = config["training"]
    if iterations is None:
        iterations = int(training_conf["analysis_bootstrap_resamples"])
    if confidence is None:
        confidence = float(training_conf["analysis_confidence_level"])

    present = indicators.astype(np.float64)
    row_count = len(values)
    with_count = present.sum(axis=0)
    without_count = row_count - with_count
    with_sum = present.T @ values
    without_sum = values.sum() - with_sum
    observed = (
        with_sum / np.maximum(with_count, 1) - without_sum / np.maximum(without_count, 1)
    )

    generator = np.random.default_rng(seed)
    null_maximums = np.empty(iterations, dtype=np.float64)
    for iteration in range(iterations):
        draws = generator.integers(0, row_count, size=row_count)
        # Counting the drawn rows as weights turns the per-resample group sums
        # into two matrix-vector products, so the whole family is resampled
        # without materialising a resampled copy of the design. Both products
        # are indexed by the original row, because that is the axis the weights
        # live on: a weight counts draws of a row, it does not belong to a
        # position in the draw order.
        weights = np.bincount(draws, minlength=row_count).astype(np.float64)
        weighted_values = weights * values
        drawn_with_count = present.T @ weights
        drawn_with_sum = present.T @ weighted_values
        replicate = drawn_with_sum / np.maximum(drawn_with_count, 1) - (
            weighted_values.sum() - drawn_with_sum
        ) / np.maximum(row_count - drawn_with_count, 1)
        # Centring on the observed effect gives an approximation of each
        # condition's statistic under no association, and resampling the rows
        # together preserves whatever dependence the conditions really have.
        null_maximums[iteration] = float(np.abs(replicate - observed).max())
        if progress is not None:
            progress(iteration + 1)

    exceeds = null_maximums[:, None] >= np.abs(observed)[None, :]
    # The plus one keeps an unexceeded condition from reporting exactly zero,
    # which no finite resampling can justify.
    p_values = (1 + exceeds.sum(axis=0)) / (iterations + 1)
    return MaxStatisticResult(
        observed=observed,
        p_values=p_values,
        critical_value=float(np.quantile(null_maximums, confidence)),
        iterations=iterations,
    )


def mann_whitney_pvalue(first: Sequence[float], second: Sequence[float]) -> float:
    """Two-sided Mann-Whitney U p-value for two score groups.

    A group with fewer than two values cannot carry a rank comparison, so that
    is reported as 1.0 rather than as the NaN scipy returns with a warning.
    """
    if len(first) < 2 or len(second) < 2:
        return 1.0
    # scipy ships no complete stubs, so the result object is read through the
    # single attribute this call documents.
    result = cast("Any", mannwhitneyu(list(first), list(second), alternative="two-sided"))
    return float(result.pvalue)


def cliffs_delta(first: Sequence[float], second: Sequence[float]) -> float:
    """Cliff's delta: the share of pairs where first exceeds second, minus the reverse.

    Runs in O(n log n) through the rank sum rather than the O(n*m) pairwise
    count, which matters because this is evaluated once per term.
    """
    left = np.sort(np.asarray(first, dtype=np.float64).ravel())
    right = np.sort(np.asarray(second, dtype=np.float64).ravel())
    if left.size == 0 or right.size == 0:
        return 0.0

    # Count pairs where the first group wins, ties contributing half each.
    wins = np.searchsorted(right, left, side="left")
    ties = np.searchsorted(right, left, side="right") - wins
    total = int(left.size * right.size)
    losses = total - int(wins.sum()) - int(ties.sum())
    return float((int(wins.sum()) - losses) / total)


def correlation_with_ci(
    x: Sequence[float],
    y: Sequence[float],
    method: str,
    *,
    seed: int = 0,
    iterations: int | None = None,
    confidence: float | None = None,
) -> CorrelationResult:
    """Correlate two samples and bootstrap a percentile interval for the coefficient.

    ``method`` is ``"pearson"`` or ``"spearman"``. The interval resamples whole
    image pairs, so it answers "how stable is this coefficient under resampling"
    rather than assuming a parametric shape.

    `iterations` and `confidence` fall back to the ``analysis_bootstrap_resamples``
    and ``analysis_confidence_level`` training settings when not supplied.
    """
    if iterations is None:
        iterations = int(config["training"]["analysis_bootstrap_resamples"])
    if confidence is None:
        confidence = float(config["training"]["analysis_confidence_level"])

    first = np.asarray(x, dtype=np.float64)
    second = np.asarray(y, dtype=np.float64)
    if first.shape != second.shape:
        raise ValueError(
            f"correlation samples must have equal length, got {first.size} and {second.size}"
        )

    finite = np.isfinite(first) & np.isfinite(second)
    first = first[finite]
    second = second[finite]
    count = first.size
    if count < 3:
        raise ValueError(f"correlation needs at least 3 finite pairs, got {count}")

    # scipy ships no complete stubs for these, so its results are read through
    # the two-element (coefficient, p-value) shape they all document.
    if method == "pearson":
        measured = cast("tuple[float, float]", pearsonr(first, second))
    elif method == "spearman":
        measured = cast("tuple[float, float]", spearmanr(first, second))
    else:
        raise ValueError(f"unknown correlation method: {method}")

    rng = Random(seed)
    coefficients = np.empty(iterations, dtype=np.float64)
    filled = 0
    while filled < iterations:
        indices = [rng.randrange(count) for _ in range(count)]
        sample_first = first[indices]
        sample_second = second[indices]
        if np.ptp(sample_first) == 0.0 or np.ptp(sample_second) == 0.0:
            # A constant resample carries no rank information; skip rather than
            # record a NaN that would poison the percentiles.
            continue
        if method == "pearson":
            coefficients[filled] = float(
                cast("tuple[float, float]", pearsonr(sample_first, sample_second))[0]
            )
        else:
            coefficients[filled] = float(
                cast("tuple[float, float]", spearmanr(sample_first, sample_second))[0]
            )
        filled += 1

    tail = (1.0 - confidence) / 2.0
    ci_low, ci_high = np.percentile(coefficients, [tail * 100.0, (1.0 - tail) * 100.0])
    return CorrelationResult(
        coefficient=float(measured[0]),
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        p_value=float(measured[1]),
        sample_count=count,
    )


def standard_error(values: Sequence[float]) -> float:
    """Sample standard error, returning 0.0 for fewer than two observations."""
    array = np.asarray(values, dtype=np.float64)
    if array.size < 2:
        return 0.0
    return float(sqrt(float(np.var(array, ddof=1)) / array.size))
