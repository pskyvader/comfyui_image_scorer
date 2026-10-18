from __future__ import annotations

import math

import numpy as np
import pytest

from ..statistics import (
    benjamini_hochberg,
    cliffs_delta,
    correlation_with_ci,
    mann_whitney_pvalue,
    max_statistic_bootstrap,
    standard_error,
)


def test_benjamini_hochberg_empty_input() -> None:
    assert benjamini_hochberg([]).size == 0


def test_benjamini_hochberg_keeps_order_and_never_shrinks() -> None:
    corrected = benjamini_hochberg([0.04, 0.01, 0.20])
    assert corrected.shape == (3,)
    # The smallest raw p-value maps to the first position, and every corrected
    # value is at least as large as its own test.
    assert corrected[1] < corrected[0] < corrected[2]
    assert list(corrected) == pytest.approx([0.06, 0.03, 0.20])


def test_benjamini_hochberg_uniform_p_values_stay_at_the_largest_rank() -> None:
    # Every p-value is 0.05, so each is compared against 0.05 * 10 / 10. The
    # monotonicity step then pulls all of them up to that largest-rank value.
    corrected = benjamini_hochberg([0.05] * 10)
    assert list(corrected) == pytest.approx([0.05] * 10)


def test_benjamini_hochberg_scales_each_p_value_by_its_rank() -> None:
    # Five ordered p-values, each multiplied by 5 / rank. The result is already
    # increasing, so the monotonicity step changes nothing.
    corrected = benjamini_hochberg([0.0001, 0.0004, 0.0019, 0.0095, 0.0201])
    assert list(corrected) == pytest.approx(
        [0.0005, 0.001, 0.00316667, 0.011875, 0.0201], rel=1e-5
    )


def test_benjamini_hochberg_is_monotone() -> None:
    corrected = benjamini_hochberg([0.001, 0.008, 0.039, 0.041, 0.9])
    assert list(corrected) == sorted(corrected)


def test_cliffs_delta_identical_groups_is_zero() -> None:
    assert cliffs_delta([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(0.0)


def test_cliffs_delta_complete_separation_is_one() -> None:
    assert cliffs_delta([10.0, 11.0, 12.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cliffs_delta_complete_reversal_is_minus_one() -> None:
    assert cliffs_delta([1.0, 2.0], [10.0, 11.0]) == pytest.approx(-1.0)


def test_cliffs_delta_excludes_ties_from_both_directions() -> None:
    # Pairs of [5, 1] against [1, 9]: 5 beats 1, 5 loses to 9, 1 ties 1, 1 loses
    # to 9. Wins 1, losses 2, tie 1, so (1 - 2) / 4 = -0.25.
    assert cliffs_delta([5.0, 1.0], [1.0, 9.0]) == pytest.approx(-0.25)

    # With no tie involved the delta is the plain win share: 1 win, 3 losses.
    assert cliffs_delta([9.0, 1.0, 2.0, 3.0], [8.0, 7.0]) == pytest.approx(-0.5)


def test_cliffs_delta_empty_group_is_zero() -> None:
    assert cliffs_delta([], [1.0, 2.0]) == 0.0


def test_cliffs_delta_symmetric_for_swapped_groups() -> None:
    left = [1.0, 4.0, 7.0, 9.0]
    right = [2.0, 2.0, 6.0, 8.0]
    assert cliffs_delta(left, right) == pytest.approx(
        -cliffs_delta(right, left)
    )


def test_mann_whitney_pvalue_detects_separated_groups() -> None:
    low = [0.01 * index for index in range(30)]
    high = [0.5 + 0.01 * index for index in range(30)]
    assert mann_whitney_pvalue(high, low) < 1e-6


def test_mann_whitney_pvalue_identical_groups_is_large() -> None:
    values = [0.5] * 40
    assert mann_whitney_pvalue(values, values) > 0.5


def test_mann_whitney_pvalue_needs_two_values_per_group() -> None:
    assert mann_whitney_pvalue([0.5], [0.1, 0.2, 0.3]) == 1.0
    assert mann_whitney_pvalue([0.5, 0.6], [0.7]) == 1.0


def test_correlation_with_ci_finds_a_perfect_relationship() -> None:
    x = [float(index) for index in range(200)]
    y = [3.0 * value + 1.0 for value in x]
    result = correlation_with_ci(x, y, "pearson", iterations=200, seed=7)
    assert result.coefficient == pytest.approx(1.0)
    assert result.ci_low == pytest.approx(1.0, abs=1e-6)
    assert result.sample_count == 200


def test_correlation_with_ci_measures_noise_on_a_reversed_axis() -> None:
    x = [float(index) for index in range(200)]
    y = [-value for value in x]
    result = correlation_with_ci(x, y, "spearman", iterations=200, seed=3)
    assert result.coefficient == pytest.approx(-1.0)
    assert result.ci_high < 0.0


def test_correlation_with_ci_drops_non_finite_pairs() -> None:
    x = [1.0, 2.0, float("nan"), 4.0, 5.0]
    y = [2.0, 4.0, 6.0, 8.0, float("inf")]
    result = correlation_with_ci(x, y, "pearson", iterations=100, seed=1)
    assert result.sample_count == 3


def test_correlation_with_ci_interval_brackets_the_estimate() -> None:
    generator = pytest.importorskip("numpy.random")
    rng = generator.default_rng(11)
    noise = rng.normal(0.0, 4.0, size=400)
    x = [float(index) for index in range(400)]
    y = [0.5 * value + offset for value, offset in zip(x, noise, strict=True)]
    result = correlation_with_ci(x, y, "pearson", iterations=300, seed=5)
    assert result.ci_low < result.coefficient < result.ci_high
    assert 0.0 < result.coefficient < 1.0


def test_correlation_with_ci_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="equal length"):
        correlation_with_ci([1.0, 2.0], [1.0], "pearson")


def test_correlation_with_ci_rejects_too_few_pairs() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        correlation_with_ci([1.0, 2.0], [1.0, 2.5], "pearson")


def test_correlation_with_ci_rejects_unknown_method() -> None:
    with pytest.raises(ValueError, match="unknown correlation method"):
        correlation_with_ci([1.0, 2.0, 4.0], [1.0, 3.0, 2.0], "kendall")


def test_standard_error() -> None:
    assert standard_error([1.0]) == 0.0
    assert standard_error([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]) == pytest.approx(
        math.sqrt(32.0 / 7.0 / 8.0)
    )


def _family(count: int, columns: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    generator = np.random.default_rng(seed)
    indicators = generator.random((count, columns)) < 0.3
    return indicators, generator.normal(0.0, 1.0, size=count)


def test_the_family_wide_threshold_rejects_nothing_when_there_is_nothing() -> None:
    indicators, values = _family(8000, 200, seed=70)
    result = max_statistic_bootstrap(indicators, values, iterations=200, seed=71)
    # The correction exists to stop a large screen inventing findings. On pure
    # noise the largest observed effect has to stay under the largest effect the
    # same resampling produces.
    assert np.abs(result.observed).max() <= result.critical_value
    assert int((result.p_values <= 0.05).sum()) == 0


def test_the_family_wide_correction_finds_a_genuine_effect_among_thousands() -> None:
    indicators, values = _family(8000, 200, seed=72)
    values[indicators[:, 7]] += 0.9
    result = max_statistic_bootstrap(indicators, values, iterations=200, seed=73)
    assert result.p_values[7] == pytest.approx(min(1.0, 1.0 / 201.0), abs=1e-9)
    # One real effect in the family, and only that one clears it.
    assert int((result.p_values <= 0.05).sum()) == 1


def test_a_condition_copied_across_every_row_is_not_mistaken_for_an_effect() -> None:
    # A condition with no comparison group reproduces the mean exactly, so the
    # resampling reproduces it too and it can never clear the threshold.
    indicators, values = _family(6000, 50, seed=74)
    indicators[:, 3] = True
    result = max_statistic_bootstrap(indicators, values, iterations=100, seed=75)
    assert result.p_values[3] > 0.05


def test_the_threshold_grows_with_the_size_of_the_screen() -> None:
    # Screening 200 conditions instead of one raises the bar, because the
    # largest of 200 draws sits further into the tail than a single draw does.
    # Comparing the same data both ways is what makes the cost of multiplicity
    # visible rather than assumed.
    indicators, values = _family(8000, 200, seed=84)
    screened = max_statistic_bootstrap(indicators, values, iterations=400, seed=85)
    alone = max_statistic_bootstrap(indicators[:, :1], values, iterations=400, seed=85)
    assert screened.critical_value > 1.4 * alone.critical_value


def test_duplicated_conditions_share_one_family_wide_p_value() -> None:
    # Nine copies of the same condition are one finding, not nine independent
    # chances. The correction has to say so, because the alternative reading
    # would charge the finding for the copies it happens to have.
    generator = np.random.default_rng(86)
    indicators = generator.random((8000, 40)) < 0.3
    shared = indicators[:, 0]
    for column in range(1, 10):
        indicators[:, column] = shared
    values = generator.normal(0.0, 1.0, size=8000) + 0.8 * shared

    result = max_statistic_bootstrap(indicators, values, iterations=200, seed=87)
    # The floor for a p-value from a finite resampling is one exceedance.
    assert result.p_values[0] == pytest.approx(1.0 / 201.0)
    assert np.allclose(result.p_values[:10], result.p_values[0])
    # The copies are the same condition, so the family's null maximum is the
    # same too: repeating a condition cannot manufacture a bigger effect.
    assert result.critical_value < 0.15


def test_the_correction_reports_progress_once_per_resample() -> None:
    indicators, values = _family(2000, 20, seed=78)
    seen: list[int] = []
    max_statistic_bootstrap(
        indicators, values, iterations=5, seed=79, progress=seen.append
    )
    assert seen == [1, 2, 3, 4, 5]


def test_the_correction_is_reproducible_for_a_fixed_seed() -> None:
    indicators, values = _family(4000, 60, seed=80)
    first = max_statistic_bootstrap(indicators, values, iterations=80, seed=81)
    second = max_statistic_bootstrap(indicators, values, iterations=80, seed=81)
    assert first.critical_value == pytest.approx(second.critical_value)
    assert np.allclose(first.p_values, second.p_values)
