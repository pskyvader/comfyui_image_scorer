"""Tests for the combination search.

The claim under test is the one the module exists to support: a pair whose
lift is near zero when its parts already carry the effect, and a pair whose
lift is real when they only matter together. A search that reported the second
as strong as the first would be measuring two marginals and calling it a
combination.
"""

from __future__ import annotations

import numpy as np
import pytest

from ..combination_search import (
    Element,
    additive_prediction,
    beam_search,
    bootstrap_interval,
    find_combinations,
    greedy_search,
    indicator_matrix,
    nested_cross_validation,
    permutation_null,
    search_combinations,
    validate_on_holdout,
)

CAR = Element("prompt", "car")
RED = Element("prompt", "red")
CFG4 = Element("cfg", "4")
CFG7 = Element("cfg", "7")
ELEMENTS = (CAR, RED, CFG4, CFG7)


def _rows(count: int, seed: int) -> list[list[Element]]:
    generator = np.random.default_rng(seed)
    rows: list[list[Element]] = []
    for _ in range(count):
        present = [
            CFG4 if generator.random() < 0.5 else CFG7,
        ]
        if generator.random() < 0.5:
            present.append(CAR)
        if generator.random() < 0.5:
            present.append(RED)
        rows.append(present)
    return rows


def _scores(
    rows: list[list[Element]], interaction: float, seed: int, noise: float = 0.12
) -> list[float]:
    """Scores built around an optional car+red interaction.

    The base sits mid-scale so the noise cannot clip at either bound: a clipped
    sample has a compressed mean, which would shrink every measured lift and
    make the assertions below a test of the clipping rather than of the search.
    """
    generator = np.random.default_rng(seed)
    values = []
    for present in rows:
        base = 0.5
        if interaction > 0 and CAR in present and RED in present:
            base += interaction
        if CFG4 in present:
            base += 0.05
        values.append(float(base + generator.normal(0.0, noise)))
    return values


def test_indicator_matrix_marks_the_right_cells() -> None:
    rows = [[CAR, CFG4], [CFG7], [], [RED, CAR]]
    matrix = indicator_matrix(rows, ELEMENTS)
    assert matrix.shape == (4, 4)
    # Column order is the element order: car, red, cfg 4, cfg 7.
    assert matrix[0].tolist() == [True, False, True, False]
    assert matrix[1].tolist() == [False, False, False, True]
    assert not matrix[2].any()
    assert matrix[3].tolist() == [True, True, False, False]


def test_indicator_matrix_ignores_unlisted_elements() -> None:
    unknown = Element("prompt", "not-a-candidate")
    matrix = indicator_matrix([[unknown, CAR]], ELEMENTS)
    assert matrix[0].tolist() == [True, False, False, False]


def test_additive_prediction_with_no_columns_is_the_mean() -> None:
    scores = np.array([0.1, 0.5, 0.9], dtype=np.float64)
    predicted = additive_prediction(
        np.zeros((3, 2), dtype=np.bool_), scores, []
    )
    assert predicted.tolist() == pytest.approx([0.5, 0.5, 0.5])


def test_additive_prediction_reproduces_an_additive_truth() -> None:
    # Score is exactly the sum of the two effects, so the fit must reproduce it.
    matrix = np.array([[True, True], [True, False], [False, True], [False, False]])
    scores = np.array([0.9, 0.6, 0.5, 0.2], dtype=np.float64)
    predicted = additive_prediction(matrix, scores, [0, 1])
    assert predicted.tolist() == pytest.approx(scores.tolist(), abs=1e-6)


def test_additive_prediction_stays_finite_on_collinear_columns() -> None:
    # Every image carries both, so the two columns are identical.
    matrix = np.array([[True, True], [True, True]], dtype=np.bool_)
    scores = np.array([0.5, 0.7], dtype=np.float64)
    predicted = additive_prediction(matrix, scores, [0, 1])
    assert np.isfinite(predicted).all()


def test_bootstrap_interval_brackets_the_mean() -> None:
    generator = np.random.default_rng(3)
    values = generator.normal(0.0, 1.0, size=600)
    low, high = bootstrap_interval(values, iterations=300, seed=5)
    assert low < float(values.mean()) < high


def test_bootstrap_interval_of_one_value_is_that_value() -> None:
    assert bootstrap_interval(np.array([0.42])) == pytest.approx((0.42, 0.42))


def test_bootstrap_interval_of_nothing_is_zero() -> None:
    assert bootstrap_interval(np.array([], dtype=np.float64)) == (0.0, 0.0)


def test_interaction_pair_carries_lift_the_parts_do_not() -> None:
    rows = _rows(6000, seed=1)
    scores = _scores(rows, interaction=0.25, seed=2)
    found = find_combinations(
        rows, scores, ELEMENTS, max_elements=2, min_support=100, seed=11
    )
    pair = found[-1]
    assert set(pair.elements) == {CAR, RED}
    # Neither term has a marginal effect on its own, so a pair that merely added
    # them would show lift near zero.
    #
    # The lift is about half the true interaction, not all of it: with two
    # independent binary factors the additive fit already predicts each factor's
    # marginal on the conjunction, so only the unexplained remainder is left.
    assert pair.lift > 0.05
    assert pair.lift < 0.25
    assert pair.q_value < 0.05
    # And the figure has to survive on images the search never saw.
    assert pair.holdout_lift == pytest.approx(pair.lift, abs=0.03)


def test_lift_is_smaller_than_a_pure_interaction() -> None:
    """The additive fit absorbs half of a symmetric interaction.

    Documented rather than assumed: a reader seeing a lift of +0.06 on a pair
    with a true +0.25 interaction should know that is the expected ratio, not a
    measurement failure.
    """
    rows = _rows(20000, seed=30)
    scores = _scores(rows, interaction=0.25, seed=31)
    matrix = indicator_matrix(rows, ELEMENTS)
    value_array = np.asarray(scores, dtype=np.float64)
    found = greedy_search(matrix, value_array, ELEMENTS, max_elements=2, min_support=200)
    pair = found[-1]
    assert 0.20 * 0.25 < pair.lift < 0.55 * 0.25


def test_two_pure_marginals_add_up_and_show_no_lift() -> None:
    # Each element shifts the score on its own and there is no interaction, so
    # the pair's score is exactly what the two effects predict.
    rows = _rows(6000, seed=4)
    generator = np.random.default_rng(5)
    scores = [
        float(
            np.clip(
                0.3
                + (0.12 if CAR in present else 0.0)
                + (0.08 if RED in present else 0.0)
                + generator.normal(0.0, 0.10),
                0.0,
                1.0,
            )
        )
        for present in rows
    ]
    found = find_combinations(
        rows, scores, ELEMENTS, max_elements=2, min_support=100, seed=13
    )
    pair = found[-1]
    assert pair.lift == pytest.approx(0.0, abs=0.01)
    assert pair.mean_score > pair.predicted_score - 0.01


def test_greedy_search_never_repeats_an_element() -> None:
    rows = _rows(4000, seed=6)
    scores = _scores(rows, interaction=0.2, seed=7)
    matrix = indicator_matrix(rows, ELEMENTS)
    value_array = np.asarray(scores, dtype=np.float64)
    found = greedy_search(matrix, value_array, ELEMENTS, max_elements=4, min_support=50)
    for result in found:
        assert len(set(result.columns)) == len(result.columns)


def test_greedy_search_grows_one_element_per_step() -> None:
    rows = _rows(4000, seed=8)
    scores = _scores(rows, interaction=0.2, seed=9)
    matrix = indicator_matrix(rows, ELEMENTS)
    found = greedy_search(
        matrix, np.asarray(scores, dtype=np.float64), ELEMENTS, max_elements=3,
        min_support=50,
    )
    assert [len(result.elements) for result in found] == [1, 2, 3]


def test_greedy_search_stops_when_nothing_has_both_sides() -> None:
    # One column carrying every image leaves no comparison group at any step.
    rows = [[CAR, CFG4] for _ in range(500)]
    scores = [0.5] * 500
    found = find_combinations(
        rows, scores, (CAR, CFG4), max_elements=3, min_support=100, seed=1
    )
    assert found == []


def test_a_narrow_first_pick_does_not_end_the_search() -> None:
    """The support floor scales with the subset, so the search can keep growing.

    Without the relative floor a rare condition can be picked first, leave a
    subset too small for any second condition to clear the absolute floor, and
    end a five-element search at one element.
    """
    generator = np.random.default_rng(30)
    rows: list[list[Element]] = []
    for _ in range(6000):
        present = [
            CAR if generator.random() < 0.6 else CFG7,
            CFG4 if generator.random() < 0.5 else CFG7,
            RED if generator.random() < 0.5 else CFG7,
        ]
        rows.append(present)
    scores = [
        float(0.5 + 0.10 * (CAR in present) + 0.08 * (RED in present))
        + generator.normal(0.0, 0.1)
        for present in rows
    ]
    found = find_combinations(
        rows, scores, ELEMENTS, max_elements=4, min_support=50, seed=31
    )
    assert len(found) >= 2
    # Every step has to rest on a readable share of its own subset.
    previous = len(rows) / 2
    for result in found:
        assert result.support >= 0.25 * previous
        previous = result.support


def test_q_values_never_fall_below_the_raw_p_value() -> None:
    rows = _rows(4000, seed=10)
    scores = _scores(rows, interaction=0.25, seed=12)
    found = find_combinations(rows, scores, ELEMENTS, max_elements=3, min_support=50)
    for result in found:
        assert result.q_value >= result.p_value - 1e-12


def test_holdout_records_the_unseen_half_support() -> None:
    rows = _rows(6000, seed=14)
    scores = _scores(rows, interaction=0.25, seed=15)
    found = find_combinations(
        rows, scores, ELEMENTS, max_elements=2, min_support=100, seed=17
    )
    for result in found:
        # The two halves together hold every row, so neither can exceed the set.
        assert 0 < result.holdout_support <= len(rows)
        if result.holdout_support:
            assert result.holdout_lift == pytest.approx(
                result.holdout_mean_score - result.holdout_predicted_score
            )


def test_validate_on_holdout_leaves_unsupported_combinations_alone() -> None:
    matrix = indicator_matrix(_rows(400, seed=18), ELEMENTS)
    value_array = np.asarray(_scores(_rows(400, seed=18), 0.2, 19), dtype=np.float64)
    found = greedy_search(matrix, value_array, ELEMENTS, max_elements=2, min_support=20)
    validated = validate_on_holdout(found, matrix, value_array, min_support=10_000)
    assert all(item.holdout_support == 0 for item in validated)


def test_find_combinations_rejects_misaligned_input() -> None:
    with pytest.raises(ValueError, match="must align"):
        find_combinations([[CAR]], [0.5, 0.6], ELEMENTS)


def test_find_combinations_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="no records"):
        find_combinations([], [], ELEMENTS)


def test_combination_reports_its_families_and_label() -> None:
    rows = _rows(6000, seed=20)
    scores = _scores(rows, interaction=0.25, seed=21)
    found = find_combinations(
        rows, scores, ELEMENTS, max_elements=3, min_support=100, seed=23
    )
    mixed = next(item for item in found if len(item.elements) > 1)
    assert mixed.label == " + ".join(str(element) for element in mixed.elements)
    assert mixed.single_family is (len(set(mixed.families)) == 1)
    assert len(mixed.families) == len(mixed.elements)


def test_beam_width_one_matches_the_greedy_chain() -> None:
    rows = _rows(6000, seed=40)
    scores = _scores(rows, interaction=0.25, seed=41)
    matrix = indicator_matrix(rows, ELEMENTS)
    value_array = np.asarray(scores, dtype=np.float64)
    chain = greedy_search(matrix, value_array, ELEMENTS, max_elements=3, min_support=100)
    beam = beam_search(
        matrix, value_array, ELEMENTS, beam_width=1, max_elements=3, min_support=100
    )
    assert [item.columns for item in chain] == [item.columns for item in beam]


def test_a_wider_beam_reports_more_alternatives() -> None:
    rows = _rows(8000, seed=42)
    scores = _scores(rows, interaction=0.25, seed=43)
    matrix = indicator_matrix(rows, ELEMENTS)
    value_array = np.asarray(scores, dtype=np.float64)
    chain = greedy_search(matrix, value_array, ELEMENTS, max_elements=3, min_support=100)
    beam = beam_search(
        matrix, value_array, ELEMENTS, beam_width=4, max_elements=3, min_support=100
    )
    assert len(beam) > len(chain)
    # A beam can only ever contain combinations whose elements are all distinct.
    for result in beam:
        assert len(set(result.columns)) == len(result.columns)


def test_a_combination_is_measured_once_however_many_paths_reach_it() -> None:
    rows = _rows(8000, seed=42)
    scores = _scores(rows, interaction=0.25, seed=43)
    matrix = indicator_matrix(rows, ELEMENTS)
    value_array = np.asarray(scores, dtype=np.float64)
    beam = beam_search(
        matrix, value_array, ELEMENTS, beam_width=8, max_elements=3, min_support=100
    )
    keys = [frozenset(result.columns) for result in beam]
    assert len(keys) == len(set(keys))


def test_beam_reports_every_depth_it_reaches() -> None:
    rows = _rows(8000, seed=44)
    scores = _scores(rows, interaction=0.25, seed=45)
    found = search_combinations(
        rows,
        scores,
        ELEMENTS,
        beam_width=3,
        max_elements=3,
        min_support=100,
        seed=46,
    )
    depths = {len(item.elements) for item in found}
    assert depths <= {1, 2, 3}
    assert len(depths) >= 2


def test_search_combinations_reports_holdout_figures() -> None:
    rows = _rows(6000, seed=47)
    scores = _scores(rows, interaction=0.25, seed=48)
    found = search_combinations(
        rows, scores, ELEMENTS, beam_width=2, max_elements=2, min_support=100, seed=49
    )
    assert found
    assert all(item.holdout_support > 0 for item in found)


def _folds(count: int, seed: int, noise: float = 0.15) -> tuple[list[list[Element]], list[float]]:
    generator = np.random.default_rng(seed)
    rows: list[list[Element]] = []
    scores: list[float] = []
    for _ in range(count):
        present = [
            CAR if generator.random() < 0.6 else CFG7,
            RED if generator.random() < 0.5 else CFG7,
            CFG4 if generator.random() < 0.5 else CFG7,
        ]
        rows.append(present)
        together = CAR in present and RED in present
        scores.append(
            0.5
            + 0.10 * (CAR in present)
            + 0.08 * (RED in present)
            + (0.30 if together else 0.0)
            + float(generator.normal(0.0, noise))
        )
    return rows, scores


def test_every_fold_reaches_the_interaction_it_was_never_shown() -> None:
    rows, scores = _folds(9000, seed=51)
    result = nested_cross_validation(
        rows, scores, ELEMENTS, fold_count=4, min_support=100, seed=52
    )
    assert len(result.selections) == 4
    assert result.unmeasurable_folds == 0
    # The interaction is worth roughly 0.30, and a lift is smaller than that by
    # construction, but it has to stay clearly positive on every fold.
    assert result.mean_lift > 0.05
    assert min(result.lifts) > 0.0
    # Four folds that each chose blind all landing on the same combination is the
    # difference between a converged result and a search that is just churning.
    assert result.repetitions[result.most_repeated_label] == 4


def test_cross_validation_is_reproducible_for_a_fixed_seed() -> None:
    rows, scores = _folds(6000, seed=53)
    first = nested_cross_validation(
        rows, scores, ELEMENTS, fold_count=4, min_support=100, seed=54
    )
    second = nested_cross_validation(
        rows, scores, ELEMENTS, fold_count=4, min_support=100, seed=54
    )
    assert [item.label for item in first.selections] == [
        item.label for item in second.selections
    ]
    assert first.lifts == second.lifts


def test_cross_validation_rejects_a_single_fold() -> None:
    rows, scores = _folds(4000, seed=55)
    with pytest.raises(ValueError, match="at least 2 folds"):
        nested_cross_validation(rows, scores, ELEMENTS, fold_count=1, seed=56)


def test_cross_validation_reports_progress_once_per_fold() -> None:
    rows, scores = _folds(4000, seed=57)
    seen: list[int] = []
    nested_cross_validation(
        rows,
        scores,
        ELEMENTS,
        fold_count=3,
        min_support=100,
        seed=58,
        progress=seen.append,
    )
    assert seen == [3]


def test_the_permutation_null_invents_nothing_from_pure_noise() -> None:
    rows, _scores = _folds(6000, seed=59)
    generator = np.random.default_rng(60)
    noise = [float(value) for value in generator.normal(0.0, 0.3, size=len(rows))]
    invented = permutation_null(
        rows,
        noise,
        ELEMENTS,
        rounds=6,
        fold_count=3,
        min_support=100,
        seed=61,
    )
    assert invented.shape == (6,)
    # With no association anywhere, the search still returns a winner, and its
    # lift is the size of the bias being corrected for.
    assert invented.max() < 0.15


def test_a_real_interaction_outranks_what_the_null_invents() -> None:
    rows, scores = _folds(9000, seed=62)
    result = nested_cross_validation(
        rows, scores, ELEMENTS, fold_count=4, min_support=100, seed=63
    )
    invented = permutation_null(
        rows,
        scores,
        ELEMENTS,
        rounds=8,
        fold_count=4,
        min_support=100,
        seed=63,
    )
    assert result.mean_lift > float(np.quantile(invented, 0.95))


def test_the_null_reports_the_same_statistic_the_estimate_does() -> None:
    # Comparing the best fold against a null of means would put the two on
    # different scales, so both sides have to be the mean across folds.
    rows, scores = _folds(9000, seed=66)
    result = nested_cross_validation(
        rows, scores, ELEMENTS, fold_count=4, min_support=100, seed=67
    )
    invented = permutation_null(
        rows,
        scores,
        ELEMENTS,
        rounds=6,
        fold_count=4,
        min_support=100,
        seed=67,
    )
    assert result.mean_lift <= result.best_lift
    assert float(invented.max()) <= result.best_lift + 0.15


def test_the_permutation_null_reports_progress_once_per_round() -> None:
    rows, scores = _folds(3000, seed=64)
    seen: list[int] = []
    permutation_null(
        rows,
        scores,
        ELEMENTS,
        rounds=4,
        fold_count=2,
        min_support=100,
        seed=65,
        progress=seen.append,
    )
    assert seen == [1, 2, 3, 4]
