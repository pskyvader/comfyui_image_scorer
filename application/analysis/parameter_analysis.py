"""Parameter analysis: relationships between generation parameters and score.

The `text_data.jsonl` rows are `{filename: payload}` one-key objects, and the
payload holds the generation parameters at the top level rather than nested
under `generation_params`. Scores live in their own artifact keyed by filename,
so every measurement here joins on the filename carried by the row instead of
trusting row order, and the text sidecar is streamed rather than materialized.
"""

import json
from pathlib import Path
from typing import Any, Callable, Iterator, cast

import numpy as np

from ...core.filesystem.paths import analysis_dir
from ...core.observability.logger import get_logger, ModuleLogger
from ...domain.vectors.terms import extract_terms
from .inputs import AnalysisInputs
from .row_fields import as_number, as_weight_map, strongest

logger: ModuleLogger = get_logger(__name__)

NUMERIC_PARAMS: tuple[str, ...] = ("steps", "cfg")
CATEGORY_PARAMS: tuple[str, ...] = ("sampler", "scheduler", "model")


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

    def analyze_term_correlations(self) -> None:
        logger.info("  - Extracting term correlations...")
        positive: dict[str, list[float]] = {}
        negative: dict[str, list[float]] = {}
        analyzed = 0

        for filename, payload, score in self._iter_scored_rows():
            for term, weight in self._weighted_terms(
                self._positive_prompt(filename, payload)
            ):
                positive.setdefault(term, []).append(score * weight)

            raw_negative = payload.get("negative_prompt")
            for term, weight in self._weighted_terms(
                raw_negative if isinstance(raw_negative, str) else ""
            ):
                negative.setdefault(term, []).append(score * weight)

            analyzed += 1

        positive_stats = self._summarize(positive)
        negative_stats = self._summarize(negative)
        logger.info("  - Analyzed %d scored rows", analyzed)
        logger.info("  - Found %d unique positive terms", positive_stats["total_unique_terms"])
        logger.info("  - Found %d unique negative terms", negative_stats["total_unique_terms"])

        with open(self.output_dir / "term_correlations.json", "w") as f:
            json.dump(
                {
                    "positive": positive_stats,
                    "negative": negative_stats,
                    "rows_analyzed": analyzed,
                },
                f,
                indent=2,
            )

    @staticmethod
    def _summarize(scores: dict[str, list[float]]) -> dict[str, Any]:
        """Rank one term group by mean weighted score, keeping both tails."""
        stats: dict[str, dict[str, float | int]] = {}
        for term, values in scores.items():
            if not values:
                continue
            stats[term] = {
                "avg_score": float(np.mean(values)),
                "std_dev": float(np.std(values)),
                "count": len(values),
                "max_score": float(np.max(values)),
                "min_score": float(np.min(values)),
            }
        ranked = sorted(
            stats.items(), key=lambda item: item[1]["avg_score"], reverse=True
        )
        return {
            "total_unique_terms": len(stats),
            "top_terms": ranked[:50],
            "bottom_terms": ranked[-50:],
        }

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