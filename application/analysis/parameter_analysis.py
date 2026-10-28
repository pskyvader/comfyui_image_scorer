"""Parameter analysis: relationships between generation parameters and score.

The `text_data.jsonl` rows are `{filename: payload}` one-key objects, and the
payload holds the generation parameters at the top level rather than nested
under `generation_params`. Scores live in their own artifact keyed by filename,
so every measurement here joins on the filename carried by the row instead of
trusting row order, and the text sidecar is streamed rather than materialized.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, cast

import numpy as np

from ...core.filesystem.paths import analysis_dir
from ...core.observability.logger import get_logger, ModuleLogger
from ...core.configuration.settings import config
from ...domain.training.statistics import (
    benjamini_hochberg,
    cliffs_delta,
    mann_whitney_pvalue,
)
from ...domain.vectors.terms import extract_terms
from .inputs import AnalysisInputs
from .row_fields import as_number, as_weight_map, strongest

logger: ModuleLogger = get_logger(__name__)

NUMERIC_PARAMS: tuple[str, ...] = ("steps", "cfg")
CATEGORY_PARAMS: tuple[str, ...] = ("sampler", "scheduler", "model")


@dataclass(frozen=True)
class TermCorrelationSummary:
    """How the terms of one prompt polarity line up with the score.

    ``terms`` holds one record per term that cleared ``min_images``, ordered
    by ``delta`` from lowest to highest. ``p_value`` comes from a Mann-Whitney U
    test of the images carrying the term against those that do not, ``q_value``
    is that p-value after Benjamini-Hochberg correction across the kept terms,
    and ``cliffs_delta`` is the effect size, which stays interpretable when the
    p-value does not.
    """

    polarity: str
    rows_analyzed: int
    unique_terms: int
    kept_terms: int
    dropped_below_floor: int
    terms: list[dict[str, object]]


class ParameterAnalyzer:
    """Scores grouped by generation parameter and by weighted prompt term."""

    def __init__(
        self,
        inputs: AnalysisInputs,
        text_rows: Callable[[], Iterator[dict[str, Any]]],
        output_dir: str = analysis_dir,
    ):
        self.inputs = inputs
        self._text_rows = text_rows
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def analyze_all(self) -> None:
        logger.info("Starting parameter analysis...")
        self.analyze_parameter_pairs()
        self.analyze_term_correlations()
        logger.info("Generating analysis report...")
        self.generate_report()
        logger.info("Analysis complete! Output saved to %s", self.output_dir)

    def _iter_scored_rows(self) -> Iterator[tuple[str, dict[str, Any], float]]:
        """Yield (filename, payload, score) for rows that have a score.

        Rows are keyed by filename on both sides. Pairing by position instead
        would attach each image's score to whichever image happened to sit at
        the same index, which is how the previous version silently reported
        zeros once the file layout changed.
        """
        for row in self._text_rows():
            for filename, raw in row.items():
                payload = cast("dict[str, Any]", raw)
                score = self.inputs.scores.get(str(filename))
                if score is not None:
                    yield str(filename), payload, score

    @staticmethod
    def _lora_weight(payload: dict[str, Any]) -> float:
        """Return the strongest LoRA weight for a row, or 0 when there is none."""
        return strongest(as_weight_map(payload.get("lora")))[1]

    @staticmethod
    def _category(payload: dict[str, Any], name: str) -> str:
        """Return the parameter a one-hot column selects for this row."""
        return strongest(as_weight_map(payload.get(name)))[0]

    def analyze_parameter_pairs(self) -> None:
        logger.info("  - Extracting parameters...")
        numeric: dict[str, list[float]] = {name: [] for name in NUMERIC_PARAMS}
        lora_weights: list[float] = []
        category_scores: dict[str, dict[str, list[float]]] = {
            name: {} for name in CATEGORY_PARAMS
        }

        for _filename, payload, score in self._iter_scored_rows():
            for name in NUMERIC_PARAMS:
                value = as_number(payload.get(name))
                if value is not None and value > 0:
                    numeric[name].append(value)

            lora_weight = self._lora_weight(payload)
            if lora_weight > 0:
                lora_weights.append(lora_weight)

            for name in CATEGORY_PARAMS:
                category = self._category(payload, name)
                if category:
                    category_scores[name].setdefault(category, []).append(score)

        for name, values in numeric.items():
            logger.info("    Found %d entries with %s parameter", len(values), name)
        logger.info("    Found %d entries with LORA weight", len(lora_weights))

        for name, values in numeric.items():
            if values:
                self._save_scalar_stats(f"{name}_stats.json", values)
        if lora_weights:
            self._save_scalar_stats("lora_stats.json", lora_weights)
        for name, scores in category_scores.items():
            if scores:
                self._save_category_stats(f"{name}_stats.json", scores)

    def _positive_prompt(self, filename: str, payload: dict[str, Any]) -> str:
        """Prefer the stored prompt tag, falling back to the sidecar copy."""
        tags = self.inputs.prompt_tags.get(filename)
        if tags:
            return tags
        value = payload.get("positive_prompt")
        return value if isinstance(value, str) else ""

    @staticmethod
    def _weighted_terms(text: str) -> list[tuple[str, float]]:
        if not text:
            return []
        return [(term, weight) for term, weight, _ in extract_terms(text).terms]

    def analyze_term_correlations(self) -> dict[str, TermCorrelationSummary]:
        """Score every weighted prompt term and report the effect of having it.

        Each term is measured twice: an unweighted mean score for the images that
        carry it, and the older score-times-weight mean, which reflects how
        prominently the prompt used the term. The weighted figure alone mixes
        "this term appears" with "this term is weighted up", so it cannot say
        whether a term helps.
        """
        logger.info("  - Extracting term correlations...")
        min_images = int(config["training"]["analysis_min_images_per_term"])
        positive: dict[str, list[int]] = {}
        positive_weights: dict[str, list[float]] = {}
        negative: dict[str, list[int]] = {}
        negative_weights: dict[str, list[float]] = {}
        scores: list[float] = []
        analyzed = 0

        for row_index, (filename, payload, score) in enumerate(self._iter_scored_rows()):
            scores.append(score)
            for target, weights in ((positive, positive_weights), (negative, negative_weights)):
                text = (
                    self._positive_prompt(filename, payload)
                    if target is positive
                    else payload.get("negative_prompt")
                )
                for term, weight in self._weighted_terms(
                    text if isinstance(text, str) else ""
                ):
                    target.setdefault(term, []).append(row_index)
                    weights.setdefault(term, []).append(weight)

            analyzed += 1

        summaries = {
            "positive": self._summarize(
                "positive", positive, positive_weights, scores, min_images
            ),
            "negative": self._summarize(
                "negative", negative, negative_weights, scores, min_images
            ),
        }
        logger.info("  - Analyzed %d scored rows", analyzed)
        for polarity, summary in summaries.items():
            logger.info(
                "  - %s: %d unique terms, %d above the floor of %d, %d dropped",
                polarity,
                summary.unique_terms,
                summary.kept_terms,
                min_images,
                summary.dropped_below_floor,
            )

        with open(self.output_dir / "term_correlations.json", "w") as f:
            json.dump(
                {
                    "rows_analyzed": analyzed,
                    "min_term_images": min_images,
                    **{name: asdict(summary) for name, summary in summaries.items()},
                },
                f,
                indent=2,
            )
        return summaries

    @staticmethod
    def _summarize(
        polarity: str,
        rows_by_term: dict[str, list[int]],
        weights: dict[str, list[float]],
        all_scores: list[float],
        min_images: int,
    ) -> TermCorrelationSummary:
        """Rank one term group by the score gap between carrying and not carrying it."""
        kept: dict[str, dict[str, float | int]] = {}
        for term, term_rows in rows_by_term.items():
            if len(term_rows) < min_images:
                continue
            values = np.asarray(
                [all_scores[index] for index in term_rows], dtype=np.float64
            )
            present = set(term_rows)
            rest = np.asarray(
                [value for index, value in enumerate(all_scores) if index not in present],
                dtype=np.float64,
            )
            baseline = float(np.mean(rest)) if rest.size else float(np.mean(values))
            kept[term] = {
                "count": len(term_rows),
                "avg_score": float(np.mean(values)),
                "median_score": float(np.median(values)),
                "std_dev": float(np.std(values)),
                "weighted_avg_score": float(
                    np.mean(np.asarray(weights[term], dtype=np.float64) * values)
                ),
                "max_score": float(np.max(values)),
                "min_score": float(np.min(values)),
                "baseline_avg_score": baseline,
                "delta": float(np.mean(values)) - baseline,
                "p_value": mann_whitney_pvalue(values.tolist(), rest.tolist()),
                "cliffs_delta": cliffs_delta(values.tolist(), rest.tolist()),
            }

        ordered = sorted(kept.items(), key=lambda item: item[1]["delta"])
        corrected = benjamini_hochberg(
            [float(item[1]["p_value"]) for item in ordered]
        )
        records: list[dict[str, object]] = []
        for (term, stats), q_value in zip(ordered, corrected):
            records.append({"term": term, **stats, "q_value": float(q_value)})

        return TermCorrelationSummary(
            polarity=polarity,
            rows_analyzed=len(all_scores),
            unique_terms=len(rows_by_term),
            kept_terms=len(records),
            dropped_below_floor=len(rows_by_term) - len(records),
            terms=records,
        )

    def _save_scalar_stats(self, filename: str, values: list[float]) -> None:
        with open(self.output_dir / filename, "w") as f:
            json.dump(
                {
                    "avg": float(np.mean(values)),
                    "std_dev": float(np.std(values)),
                    "count": len(values),
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                },
                f,
                indent=2,
            )

    def _save_category_stats(
        self, filename: str, scores: dict[str, list[float]]
    ) -> None:
        stats: dict[str, dict[str, float]] = {}
        for category, values in scores.items():
            if values:
                stats[category] = {
                    "avg_score": float(np.mean(values)),
                    "std_dev": float(np.std(values)),
                    "count": len(values),
                    "max": float(np.max(values)),
                    "min": float(np.min(values)),
                }
        with open(self.output_dir / filename, "w") as f:
            json.dump(stats, f, indent=2)

    def generate_report(self) -> None:
        scores = list(self.inputs.scores.values())
        if not scores:
            raise ValueError("No scores available to report on")

        report = f"""# Parameter Analysis Report

## Summary Statistics
- **Total images analyzed**: {len(scores)}
- **Average score**: {np.mean(scores):.2f}
- **Std Dev**: {np.std(scores):.2f}
- **Min score**: {np.min(scores):.2f}
- **Max score**: {np.max(scores):.2f}
"""
        with open(self.output_dir / "report.md", "w") as f:
            f.write(report)
        logger.info("  Report saved to %s", self.output_dir / "report.md")