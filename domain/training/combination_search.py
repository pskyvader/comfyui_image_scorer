"""Search for element combinations that move the score beyond their parts.

A single element is measured as its mean-score difference against the rest of
the dataset. A combination needs a different measure: if `cfg 4` scores +0.04
and `prompt: black` scores +0.05, then the pair scoring +0.09 shows no
interaction at all, only two effects sitting side by side. So every combination
here is reported as a **lift**: the observed mean score of the images matching
all of its elements, minus the score predicted from those same elements acting
additively. Lift is the quantity that answers "does this combination matter
beyond its parts", and it is deliberately smaller than a raw gap: for two
independent binary factors, the additive fit already predicts each factor's own
marginal on the conjunction, so only the unexplained remainder survives. A pair
whose true interaction is +0.25 typically reports a lift near +0.06. Read it as
"this much the parts do not explain", not as "this much the pair adds".

The search is greedy and forward, because five-element subsets drawn from a
thousand candidates are not enumerable. Each step adds the candidate that most
improves the score of the already-selected set, scored on the residual left
after that set is accounted for, so a strong marginal is not selected twice and
two strong marginals are not mistaken for a pair. The first step's lift is
structurally zero, because one column predicts its own group mean exactly: a
single element is measured as a marginal difference, not as a lift.

Two guards matter more than the search itself. Support is required on both
sides of every comparison, and the search runs on one half of the images with
its lift re-measured on the other, because greedy selection over a thousand
candidates will otherwise find something that only looked good.

That second guard is necessary but not sufficient. Re-measuring on a held-back
half protects the winner from having fitted the images it was measured on, yet it
still leaves the winner chosen as the largest of a thousand noisy estimates on
the half it did see. `nested_cross_validation` removes that too by selecting
inside every fold and scoring the selection out of fold, and `permutation_null`
then answers the question neither can: how large a lift this procedure
manufactures when the scores carry no signal at all.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
import logging

import numpy as np
import numpy.typing as npt
from scipy import stats

from ...core.observability.logger import ModuleLogger, get_logger
from .statistics import benjamini_hochberg

logger: ModuleLogger = get_logger(__name__)

FOLD_COUNT: int = 5
PERMUTATION_ROUNDS: int = 200

MAX_ELEMENTS: int = 5
MIN_SUPPORT: int = 100
# Partial combinations kept alive per step. One beam is the greedy search; a
# wider beam is what turns a single chain into a ranked set of alternatives.
BEAM_WIDTH: int = 12
# Share of the current subset a candidate must also hold. An absolute floor
# alone lets the search take one rare condition first and strand itself in a
# corner it cannot grow out of: with a floor of 100 images, a condition present
# on 117 images is eligible, and the remaining 117 leave no room for a second
# candidate to have support on both sides. Scaling the floor with the subset
# bounds how far one condition can narrow the search, so a result at depth five
# is still a pattern over a readable share of the dataset rather than a handful
# of images.
MIN_SUBSET_SHARE: float = 0.25
BOOTSTRAP_ITERATIONS: int = 400
DEFAULT_CONFIDENCE: float = 0.95
# Candidates scored per block when scanning the matrix, so peak memory stays
# proportional to this rather than to the whole candidate count.
COLUMN_BLOCK: int = 256
# The least-squares solve is exact for a full-rank design, but two candidates
# can be collinear (every image using one LoRA also uses one model), which would
# otherwise produce an unbounded coefficient and a meaningless prediction.
RIDGE: float = 1e-6


@dataclass(frozen=True, order=True)
class Element:
    """One candidate condition: a named family and the value it takes.

    `family` is the parameter the value came from (`prompt`, `model`, `cfg`) and
    `value` is the specific condition (`hair`, `euler_ancestral`, `4.0-5.5`).
    Keeping them apart is what lets a result report which kind of element a
    combination leaned on. The type is ordered so a candidate set can be sorted
    into a stable column order, which is what keeps a column index found on the
    search half meaning the same condition on the holdout half.
    """

    family: str
    value: str

    def __str__(self) -> str:
        return f"{self.family}: {self.value}"


@dataclass(frozen=True)
class Combination:
    """One searched combination and every measurement behind it.

    `lift` is the reported effect: observed mean minus additive prediction.
    `predicted_score` is the baseline it is measured against, kept so the lift
    can be read against the gap rather than taken on trust. `holdout_lift` is
    the same quantity on images the search never saw, which is the number to
    believe.
    """

    elements: tuple[Element, ...]
    columns: tuple[int, ...]
    support: int
    mean_score: float
    predicted_score: float
    lift: float
    ci_low: float
    ci_high: float
    p_value: float
    q_value: float
    holdout_support: int = 0
    holdout_mean_score: float = 0.0
    holdout_predicted_score: float = 0.0
    holdout_lift: float = 0.0

    @property
    def label(self) -> str:
        return " + ".join(str(element) for element in self.elements)

    @property
    def families(self) -> tuple[str, ...]:
        return tuple(element.family for element in self.elements)

    @property
    def single_family(self) -> bool:
        return len(set(self.families)) == 1


def indicator_matrix(
    records: Sequence[Sequence[Element]], elements: Sequence[Element]
) -> npt.NDArray[np.bool_]:
    """One boolean column per element, true where the image carries it.

    Element order fixes column order, which is what lets a column index found on
    the search half mean the same condition on the held-out half.
    """
    lookup = {element: index for index, element in enumerate(elements)}
    matrix = np.zeros((len(records), len(elements)), dtype=np.bool_)
    for row_index, present in enumerate(records):
        for element in present:
            column = lookup.get(element)
            if column is not None:
                matrix[row_index, column] = True
    return matrix


def additive_prediction(
    matrix: npt.NDArray[np.bool_],
    scores: npt.NDArray[np.float64],
    columns: Sequence[int],
) -> npt.NDArray[np.float64]:
    """Predicted score when the given element columns act additively.

    An exact least-squares fit with an intercept, solved through the normal
    equations rather than a model-fitting library: there are at most
    ``MAX_ELEMENTS`` columns, so the system is tiny and the search stays free of
    an infrastructure dependency.
    """
    if not len(columns):
        return np.full(len(scores), float(scores.mean()), dtype=np.float64)

    design = np.column_stack(
        [np.ones(len(scores), dtype=np.float64)]
        + [matrix[:, column].astype(np.float64) for column in columns]
    )
    gram = design.T @ design
    for index in range(1, len(gram)):
        gram[index, index] += RIDGE
    coefficients = np.linalg.solve(gram, design.T @ scores)
    return design @ coefficients


def bootstrap_interval(
    values: npt.NDArray[np.float64],
    iterations: int = BOOTSTRAP_ITERATIONS,
    confidence: float = DEFAULT_CONFIDENCE,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile interval for the mean of a subset.

    Uses a local generator rather than a global RNG so two calls in the same run
    do not draw the same numbers.
    """
    if values.size == 0:
        return 0.0, 0.0
    if values.size == 1:
        mean = float(values[0])
        return mean, mean

    generator = np.random.default_rng(seed)
    draws = generator.integers(0, values.size, size=(iterations, values.size))
    means = values[draws].mean(axis=1)
    tail = (1.0 - confidence) / 2.0
    low, high = np.percentile(means, [tail * 100.0, (1.0 - tail) * 100.0])
    return float(low), float(high)


def _combination_from(
    columns: tuple[int, ...],
    elements: Sequence[Element],
    matrix: npt.NDArray[np.bool_],
    scores: npt.NDArray[np.float64],
    seed: int,
) -> Combination:
    """Measure one combination's lift against its own additive prediction."""
    match = np.ones(len(scores), dtype=np.bool_)
    for column in columns:
        match &= matrix[:, column]
    matched = scores[match]

    predicted = additive_prediction(matrix, scores, columns)[match]
    predicted_mean = float(predicted.mean())
    observed_mean = float(matched.mean())
    # The residual per image, so the interval describes the lift rather than the
    # raw score spread.
    residual = matched - predicted
    low, high = bootstrap_interval(residual, seed=seed)
    p_value = (
        float(stats.ttest_1samp(residual, 0.0).pvalue) if matched.size >= 2 else 1.0
    )
    return Combination(
        elements=tuple(elements[column] for column in columns),
        columns=columns,
        support=int(matched.size),
        mean_score=observed_mean,
        predicted_score=predicted_mean,
        lift=observed_mean - predicted_mean,
        ci_low=low,
        ci_high=high,
        p_value=p_value,
        q_value=1.0,
    )


def greedy_search(
    matrix: npt.NDArray[np.bool_],
    scores: npt.NDArray[np.float64],
    elements: Sequence[Element],
    max_elements: int = MAX_ELEMENTS,
    min_support: int = MIN_SUPPORT,
    min_subset_share: float = MIN_SUBSET_SHARE,
    seed: int = 0,
) -> list[Combination]:
    """Grow a combination one element at a time, best residual gain first.

    Each candidate is scored by how much it moves the mean score of the images
    already matching the selection, with the images that do not match the
    candidate as the comparison group. That is the residual after the selection
    is accounted for, which keeps the search from re-picking an element it
    already holds.

    A candidate needs ``min_support`` images and at least ``min_subset_share`` of
    the current subset, which is what stops a narrow first pick from ending the
    search at the first step.
    """
    row_count, column_count = matrix.shape
    selected: list[int] = []
    subset = np.ones(row_count, dtype=np.bool_)
    used: set[int] = set()
    results: list[Combination] = []

    for step in range(max_elements):
        sub_matrix = matrix[subset]
        if sub_matrix.shape[0] < min_support:
            logger.info(
                "stopping at %d elements: only %d images match",
                len(selected),
                int(sub_matrix.shape[0]),
            )
            break

        sub_scores = scores[subset]
        # One pass over every candidate, in column blocks: casting the whole
        # candidate matrix to float at once would allocate
        # rows x candidates x 8 bytes, which is the memory ceiling of the whole
        # search for no benefit over blocking.
        with_counts = np.zeros(column_count, dtype=np.float64)
        with_sums = np.zeros(column_count, dtype=np.float64)
        for start in range(0, column_count, COLUMN_BLOCK):
            stop = min(start + COLUMN_BLOCK, column_count)
            block = sub_matrix[:, start:stop].astype(np.float64)
            with_counts[start:stop] = block.sum(axis=0)
            with_sums[start:stop] = block.T @ sub_scores

        subset_size = float(sub_matrix.shape[0])
        total_sum = float(sub_scores.sum())
        without_counts = subset_size - with_counts
        without_sums = total_sum - with_sums

        available = np.array(
            [index not in used for index in range(column_count)], dtype=bool
        )
        # The floor scales with the subset so one condition cannot narrow the
        # search past the point where a second one could still be measured.
        required = max(
            float(min_support), min_subset_share * float(sub_matrix.shape[0])
        )
        eligible = (
            (with_counts >= required)
            & (without_counts >= required)
            & available
        )
        if not eligible.any():
            logger.info(
                "stopping at %d elements: no candidate keeps %d images on both sides",
                len(selected),
                int(required),
            )
            break

        with np.errstate(invalid="ignore", divide="ignore"):
            gain_with = np.where(with_counts > 0, with_sums / with_counts, -np.inf)
            gain_without = np.where(
                without_counts > 0, without_sums / without_counts, -np.inf
            )
            gain = np.where(eligible, gain_with - gain_without, -np.inf)

        best = int(np.argmax(gain))
        if not np.isfinite(gain[best]):
            break

        selected.append(best)
        used.add(best)
        subset = subset & matrix[:, best]

        combination = _combination_from(
            tuple(selected), elements, matrix, scores, seed + step
        )
        results.append(combination)
        logger.info(
            "step %d: + %-30s support %6d  observed %.4f vs predicted %.4f  lift %+.4f",
            step + 1,
            combination.elements[-1],
            combination.support,
            combination.mean_score,
            combination.predicted_score,
            combination.lift,
        )

    if results:
        corrected = benjamini_hochberg(
            [result.p_value for result in results]
        )
        results = [
            replace(result, q_value=float(q_value))
            for result, q_value in zip(results, corrected, strict=True)
        ]

    return results


def beam_search(
    matrix: npt.NDArray[np.bool_],
    scores: npt.NDArray[np.float64],
    elements: Sequence[Element],
    beam_width: int = BEAM_WIDTH,
    max_elements: int = MAX_ELEMENTS,
    min_support: int = MIN_SUPPORT,
    min_subset_share: float = MIN_SUBSET_SHARE,
    seed: int = 0,
) -> list[Combination]:
    """Keep several partial combinations alive and extend all of them.

    Each step scores every candidate against every live beam, keeps the best
    ``beam_width`` extensions, and reports one combination per depth per beam.
    `beam_width=1` is the greedy search exactly, which is why the two share their
    measurement and support rules rather than reimplementing them.
    """
    row_count = matrix.shape[0]
    beams: list[tuple[int, ...]] = [()]
    subsets: list[npt.NDArray[np.bool_]] = [np.ones(row_count, dtype=np.bool_)]
    results: list[Combination] = []
    # Two beams can reach the same set by different routes, because element
    # order inside a combination carries no meaning. Keyed on the set so a
    # combination is measured once however many paths found it.
    reported: set[frozenset[int]] = set()

    for step in range(max_elements):
        extensions: list[tuple[float, tuple[int, ...], npt.NDArray[np.bool_], int]] = []

        for columns, subset in zip(beams, subsets, strict=True):
            sub_matrix = matrix[subset]
            if sub_matrix.shape[0] < min_support:
                continue
            sub_scores = scores[subset]

            with_counts = np.zeros(matrix.shape[1], dtype=np.float64)
            with_sums = np.zeros(matrix.shape[1], dtype=np.float64)
            for start in range(0, matrix.shape[1], COLUMN_BLOCK):
                stop = min(start + COLUMN_BLOCK, matrix.shape[1])
                block = sub_matrix[:, start:stop].astype(np.float64)
                with_counts[start:stop] = block.sum(axis=0)
                with_sums[start:stop] = block.T @ sub_scores

            subset_size = float(sub_matrix.shape[0])
            without_counts = subset_size - with_counts
            without_sums = float(sub_scores.sum()) - with_sums

            used = set(columns)
            available = np.array(
                [index not in used for index in range(matrix.shape[1])], dtype=bool
            )
            required = max(float(min_support), min_subset_share * subset_size)
            eligible = (
                (with_counts >= required) & (without_counts >= required) & available
            )
            if not eligible.any():
                continue

            with np.errstate(invalid="ignore", divide="ignore"):
                gain = np.where(
                    eligible,
                    np.where(with_counts > 0, with_sums / with_counts, -np.inf)
                    - np.where(
                        without_counts > 0, without_sums / without_counts, -np.inf
                    ),
                    -np.inf,
                )

            # Only the strongest few extensions per beam are worth expanding;
            # keeping all of them would make the next step quadratic in the
            # candidate count for no measurable gain.
            ranked = np.argsort(gain)[::-1]
            for candidate in ranked[:beam_width]:
                if not np.isfinite(gain[candidate]):
                    break
                extension = columns + (int(candidate),)
                extensions.append(
                    (
                        float(gain[candidate]),
                        extension,
                        subset & matrix[:, candidate],
                        int((subset & matrix[:, candidate]).sum()),
                    )
                )

        if not extensions:
            logger.info(
                "stopping at depth %d: no extension keeps its floor on both sides",
                step + 1,
            )
            break

        # Rank extensions by gain, but a beam's children are ordered by the
        # measurement they will report so a beam stays coherent across depths.
        extensions.sort(key=lambda item: item[0], reverse=True)
        chosen = extensions[:beam_width]
        beams = [item[1] for item in chosen]
        subsets = [item[2] for item in chosen]

        for _gain, columns, _subset, _support in chosen:
            key = frozenset(columns)
            if key in reported:
                continue
            reported.add(key)
            results.append(
                _combination_from(columns, elements, matrix, scores, seed + len(columns))
            )

    if results:
        corrected = benjamini_hochberg([result.p_value for result in results])
        results = [
            replace(result, q_value=float(q_value))
            for result, q_value in zip(results, corrected, strict=True)
        ]

    logger.info(
        "beam search: %d combinations reported, best lift %+.4f",
        len(results),
        max((result.lift for result in results), default=0.0),
    )
    return results


def validate_on_holdout(
    combinations: Sequence[Combination],
    holdout_matrix: npt.NDArray[np.bool_],
    holdout_scores: npt.NDArray[np.float64],
    min_support: int = MIN_SUPPORT,
) -> list[Combination]:
    """Re-measure each combination's lift on images the search never saw.

    Greedy selection fits the search half, so its lift is optimistic. Each
    combination keeps both figures: a lift that collapses on the holdout half was
    selected by noise rather than by the data.
    """
    validated: list[Combination] = []
    for combination in combinations:
        match = np.ones(len(holdout_scores), dtype=np.bool_)
        for column in combination.columns:
            match &= holdout_matrix[:, column]

        matched = holdout_scores[match]
        if matched.size < min_support:
            validated.append(combination)
            continue

        predicted = additive_prediction(
            holdout_matrix, holdout_scores, combination.columns
        )[match]
        predicted_mean = float(predicted.mean())
        holdout_mean = float(matched.mean())
        validated.append(
            Combination(
                elements=combination.elements,
                columns=combination.columns,
                support=combination.support,
                mean_score=combination.mean_score,
                predicted_score=combination.predicted_score,
                lift=combination.lift,
                ci_low=combination.ci_low,
                ci_high=combination.ci_high,
                p_value=combination.p_value,
                q_value=combination.q_value,
                holdout_support=int(matched.size),
                holdout_mean_score=holdout_mean,
                holdout_predicted_score=predicted_mean,
                holdout_lift=holdout_mean - predicted_mean,
            )
        )

    remeasured = sum(1 for item in validated if item.holdout_support)
    logger.info(
        "holdout: %d of %d combinations kept %d images on the unseen half",
        remeasured,
        len(validated),
        min_support,
    )
    return validated


@dataclass(frozen=True)
class FoldSelection:
    """One fold's chosen combination, measured on the images it never saw.

    The lift here is honest twice over: the combination was selected without the
    held-out fold, and the additive prediction it is compared against was fitted
    on the training folds and merely applied here, so neither the choice nor the
    baseline has seen these images.
    """

    fold: int
    label: str
    columns: tuple[int, ...]
    support: int
    observed_score: float
    predicted_score: float
    lift: float


@dataclass(frozen=True)
class CrossValidationResult:
    """What the selection procedure yields when it never sees what it is scored on."""

    selections: tuple[FoldSelection, ...]
    fold_count: int
    unmeasurable_folds: int
    repetitions: Mapping[str, int]

    @property
    def lifts(self) -> tuple[float, ...]:
        return tuple(selection.lift for selection in self.selections)

    @property
    def mean_lift(self) -> float:
        """Average out-of-fold lift over the folds where the choice was measurable.

        A fold whose winner matched too few held-out images is reported through
        `unmeasurable_folds` instead of being counted as zero, because a
        combination that failed to reproduce is missing data rather than a
        measured absence of effect. `permutation_null` applies the identical
        rule, so the comparison between them stays like for like.
        """
        if not self.selections:
            return 0.0
        return float(np.mean(self.lifts))

    @property
    def best_lift(self) -> float:
        return max(self.lifts, default=0.0)

    @property
    def most_repeated_label(self) -> str:
        """The label the folds agreed on most, empty when no two folds agreed."""
        return max(self.repetitions, key=lambda label: self.repetitions[label], default="")


def _fold_assignment(row_count: int, fold_count: int, seed: int) -> npt.NDArray[np.intp]:
    """Deal the rows into folds round robin over a shuffle, so the folds are equal.

    Round robin over a permutation keeps every fold the same size, which matters
    because each fold's measurement is taken on its own rows and unbalanced folds
    would make the folds' lifts incomparable.
    """
    generator = np.random.default_rng(seed)
    assignment = np.empty(row_count, dtype=np.intp)
    assignment[generator.permutation(row_count)] = np.arange(row_count) % fold_count
    return assignment


def _out_of_fold_selection(
    matrix: npt.NDArray[np.bool_],
    scores: npt.NDArray[np.float64],
    elements: Sequence[Element],
    assignment: npt.NDArray[np.intp],
    beam_width: int,
    max_elements: int,
    min_support: int,
    min_subset_share: float,
    seed: int,
) -> tuple[list[FoldSelection], int]:
    """Select inside every fold and score the selection on the fold it never saw."""
    selections: list[FoldSelection] = []
    unmeasurable = 0
    # The support floor is stated per measurement, but the search only sees
    # one training fold. A combination rare enough to fall under the floor on a
    # held-out fold is unmeasurable no matter how well it scored, and the search
    # cannot know that from the rows it can see. Scaling the floor it works to by
    # the fold count is what makes the winner's measurement possible, and it
    # pushes the search towards combinations broad enough to mean something.
    search_floor = min_support * (int(assignment.max()) + 1)

    for fold in range(int(assignment.max()) + 1):
        held_out = assignment == fold
        training = ~held_out
        found = beam_search(
            matrix[training],
            scores[training],
            elements,
            beam_width=beam_width,
            max_elements=max_elements,
            min_support=search_floor,
            min_subset_share=min_subset_share,
            seed=seed,
        )
        if not found:
            unmeasurable += 1
            continue

        chosen = max(found, key=lambda combination: combination.lift)
        match = np.ones(int(held_out.sum()), dtype=np.bool_)
        training_block = matrix[training]
        held_out_block = matrix[held_out]
        for column in chosen.columns:
            match &= held_out_block[:, column]

        design = np.column_stack(
            [np.ones(int(training.sum()), dtype=np.float64)]
            + [training_block[:, column].astype(np.float64) for column in chosen.columns]
        )
        coefficients, *_ = np.linalg.lstsq(design, scores[training], rcond=None)

        support = int(match.sum())
        if support < min_support:
            unmeasurable += 1
            continue

        observed_score = float(scores[held_out][match].mean())
        held_out_design = np.column_stack(
            [np.ones(int(held_out.sum()), dtype=np.float64)]
            + [held_out_block[:, column].astype(np.float64) for column in chosen.columns]
        )
        predicted_score = float((held_out_design[match] @ coefficients).mean())
        selections.append(
            FoldSelection(
                fold=fold,
                label=chosen.label,
                columns=chosen.columns,
                support=support,
                observed_score=observed_score,
                predicted_score=predicted_score,
                lift=observed_score - predicted_score,
            )
        )

    return selections, unmeasurable


def nested_cross_validation(
    records: Sequence[Sequence[Element]],
    scores: Sequence[float],
    elements: Sequence[Element],
    fold_count: int = FOLD_COUNT,
    beam_width: int = BEAM_WIDTH,
    max_elements: int = MAX_ELEMENTS,
    min_support: int = MIN_SUPPORT,
    min_subset_share: float = MIN_SUBSET_SHARE,
    seed: int = 0,
    progress: Callable[[int], None] | None = None,
) -> CrossValidationResult:
    """Measure what the selection procedure actually delivers, fold by fold.

    A single held-out half answers one question: did this combination survive
    being measured elsewhere? It cannot answer whether the *procedure* is
    reliable, because the combination it returns was chosen as the best of a
    thousand candidates on the half it searched, so its lift there is a maximum
    and is biased upward by an amount nobody measured.

    Folding removes that. Every fold selects its own winner from the other folds
    and is then scored on the fold it never saw, so each reported lift comes
    from a combination that was chosen blind to the images it is measured on. The
    mean across folds is what the procedure yields on unseen data; how often the
    folds pick the same combination says whether the procedure is converging on
    something or just churning.

    `min_support` is the floor for the measurement, so the search is told to hold
    `min_support * fold_count` on the rows it can see. Without that scaling the
    search happily returns a winner matching a few hundred images out of
    thousands, which cannot clear the floor on the smaller fold meant to score it,
    and the fold reports nothing at all.

    `progress` receives the completed fold count after each fold.
    """
    if fold_count < 2:
        raise ValueError(f"cross-validation needs at least 2 folds, got {fold_count}")

    matrix = indicator_matrix(records, elements)
    score_array = np.asarray(scores, dtype=np.float64)
    assignment = _fold_assignment(len(records), fold_count, seed)

    selections, unmeasurable = _out_of_fold_selection(
        matrix,
        score_array,
        elements,
        assignment,
        beam_width,
        max_elements,
        min_support,
        min_subset_share,
        seed,
    )
    if progress is not None:
        progress(fold_count)

    repetitions: dict[str, int] = {}
    for selection in selections:
        repetitions[selection.label] = repetitions.get(selection.label, 0) + 1

    result = CrossValidationResult(
        selections=tuple(selections),
        fold_count=fold_count,
        unmeasurable_folds=unmeasurable,
        repetitions=repetitions,
    )
    logger.info(
        "cross-validation over %d folds: mean out-of-fold lift %+.4f, best %+.4f, "
        "%d fold(s) unmeasurable, most repeated: %s",
        fold_count,
        result.mean_lift,
        result.best_lift,
        unmeasurable,
        result.most_repeated_label or "none",
    )
    return result


def permutation_null(
    records: Sequence[Sequence[Element]],
    scores: Sequence[float],
    elements: Sequence[Element],
    rounds: int = PERMUTATION_ROUNDS,
    fold_count: int = FOLD_COUNT,
    beam_width: int = BEAM_WIDTH,
    max_elements: int = MAX_ELEMENTS,
    min_support: int = MIN_SUPPORT,
    min_subset_share: float = MIN_SUBSET_SHARE,
    seed: int = 0,
    progress: Callable[[int], None] | None = None,
) -> npt.NDArray[np.float64]:
    """Run the same selection on shuffled scores and return what it invents.

    Every interval in this module answers "how noisy is measuring this". None of
    them answer "would this procedure have found something anyway", which is the
    question that decides whether a lift is a finding or an artefact of searching
    hard enough. Shuffling the scores across images destroys every association
    the design implies while leaving the design, the sample size and the score
    distribution untouched, so the lifts this produces are exactly what the same
    search manufactures from noise.

    Each round runs the identical cross-validation, so each entry is that round's
    mean out-of-fold lift. The mean is the statistic carried over rather than the
    best fold, because the best of `fold_count` lifts is a maximum and comparing
    it against a null of means would reintroduce the very selection bias the
    cross-validation exists to remove.

    The fold assignment and the search seed are held fixed across rounds, so the
    only thing varying between rounds is the data, which keeps the spread tight
    enough for a usable tail.

    `progress` receives the completed round count after each round.
    """
    matrix = indicator_matrix(records, elements)
    score_array = np.asarray(scores, dtype=np.float64)
    assignment = _fold_assignment(len(records), fold_count, seed)

    generator = np.random.default_rng(seed)
    invented = np.empty(rounds, dtype=np.float64)
    # Each round runs one search per fold, so leaving the search's own logging on
    # would bury the progress bar under thousands of lines describing runs whose
    # only purpose is to be thrown away.
    previous_level = logger.level
    logger.setLevel(logging.WARNING)
    try:
        for round_index in range(rounds):
            shuffled = generator.permutation(score_array)
            selections, _unmeasurable = _out_of_fold_selection(
                matrix,
                shuffled,
                elements,
                assignment,
                beam_width,
                max_elements,
                min_support,
                min_subset_share,
                seed,
            )
            invented[round_index] = (
                float(np.mean([selection.lift for selection in selections]))
                if selections
                else 0.0
            )
            if progress is not None:
                progress(round_index + 1)
    finally:
        logger.setLevel(previous_level)

    logger.info(
        "permutation null over %d rounds: mean out-of-fold lift p50=%.4f p95=%.4f max=%.4f",
        rounds,
        float(np.quantile(invented, 0.5)),
        float(np.quantile(invented, 0.95)),
        float(invented.max()),
    )
    return invented


def find_combinations(
    records: Sequence[Sequence[Element]],
    scores: Sequence[float],
    elements: Sequence[Element],
    max_elements: int = MAX_ELEMENTS,
    min_support: int = MIN_SUPPORT,
    holdout_share: float = 0.5,
    min_subset_share: float = MIN_SUBSET_SHARE,
    seed: int = 0,
) -> list[Combination]:
    """Search on one half of the images and report each result on the other.

    This is the entry point a notebook wants: build the per-image element lists,
    hand them over, and every result carries a training and a holdout figure.
    """
    return search_combinations(
        records,
        scores,
        elements,
        beam_width=1,
        max_elements=max_elements,
        min_support=min_support,
        holdout_share=holdout_share,
        min_subset_share=min_subset_share,
        seed=seed,
    )


def search_combinations(
    records: Sequence[Sequence[Element]],
    scores: Sequence[float],
    elements: Sequence[Element],
    beam_width: int = BEAM_WIDTH,
    max_elements: int = MAX_ELEMENTS,
    min_support: int = MIN_SUPPORT,
    holdout_share: float = 0.5,
    min_subset_share: float = MIN_SUBSET_SHARE,
    seed: int = 0,
) -> list[Combination]:
    """Widen the search to several live combinations per step, then hold them out.

    A greedy search returns one chain: the single best first element and the
    single best addition to it. That answers "what is the strongest pattern"
    once, and cannot report a runner-up that starts from a different first
    element. A beam keeps several partial combinations alive and extends each of
    them, which is what turns one chain into a ranked set.
    """
    if not records:
        raise ValueError("no records to search")
    if len(records) != len(scores):
        raise ValueError(
            f"records and scores must align, got {len(records)} and {len(scores)}"
        )

    score_array = np.asarray(scores, dtype=np.float64)
    matrix = indicator_matrix(records, elements)

    generator = np.random.default_rng(seed)
    order = generator.permutation(len(records))
    cut = int(len(records) * (1.0 - holdout_share))
    train_rows, holdout_rows = order[:cut], order[cut:]

    found = beam_search(
        matrix[train_rows],
        score_array[train_rows],
        elements,
        beam_width=beam_width,
        max_elements=max_elements,
        min_support=min_support,
        min_subset_share=min_subset_share,
        seed=seed,
    )
    logger.info(
        "beam of %d produced %d distinct combinations across %d depths",
        beam_width,
        len(found),
        len({len(item.elements) for item in found}),
    )
    return validate_on_holdout(
        found,
        matrix[holdout_rows],
        score_array[holdout_rows],
        min_support=min_support,
    )
