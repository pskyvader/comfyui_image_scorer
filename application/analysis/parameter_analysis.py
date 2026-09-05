"""
Parameter Analysis Module

Analyzes relationships between parameters/terms and image scores.
"""

import json

import numpy as np
from pathlib import Path

from typing import Any
from ...core.io.serialization import load_single_jsonl
from ...core.observability.logger import get_logger, ModuleLogger
from ...core.filesystem.paths import vectors_file, text_data_file

logger: ModuleLogger = get_logger(__name__)

SKLEARN_AVAILABLE = True

MATPLOTLIB_AVAILABLE = False


class ParameterAnalyzer:
    def __init__(
        self,
        vectors_data: list[dict[str, Any]],
        text_data: list[dict[str, Any]],
        output_dir: str = "output/analysis",
    ):
        self.vectors = vectors_data
        self.text_data = text_data
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.scores = np.array([v.get("score", 0) for v in vectors_data])

    def analyze_all(self) -> None:
        logger.info("Starting parameter analysis...")
        self.analyze_parameter_pairs()
        self.analyze_term_correlations()
        logger.info("Parameter analysis complete")
        logger.info("Generating analysis report...")
        self.generate_report()
        logger.info("Analysis complete! Output saved to %s", self.output_dir)

    def analyze_parameter_pairs(self) -> None:
        logger.info("  - Extracting parameters...")
        steps_list, cfg_list, lora_weight_list = [], [], []
        sampler_list, scheduler_list, model_list = [], [], []

        for vector in self.vectors:
            steps = vector.get("generation_params", {}).get("steps", 0)
            cfg = vector.get("generation_params", {}).get("cfg_scale", 0)
            lora_val = vector.get("lora")
            if isinstance(lora_val, dict):
                lora_weights = [float(w) for w in lora_val.values() if isinstance(w, (int, float))]
                lora_w = max(lora_weights) if lora_weights else 0.0
            else:
                lora_w = vector.get("lora_weight", 0) or vector.get("generation_params", {}).get("lora_weight", 0)
            sampler = vector.get("generation_params", {}).get("sampler_name", "unknown")
            scheduler = vector.get("generation_params", {}).get("scheduler", "unknown")
            model = vector.get("generation_params", {}).get("model", "unknown")
            if steps > 0:
                steps_list.append(steps)
            if cfg > 0:
                cfg_list.append(cfg)
            if lora_w > 0:
                lora_weight_list.append(lora_w)
            if sampler != "unknown":
                sampler_list.append(sampler)
            if scheduler != "unknown":
                scheduler_list.append(scheduler)
            if model != "unknown":
                model_list.append(model)

        logger.info("    Found %d entries with steps parameter", len(steps_list))
        logger.info("    Found %d entries with CFG parameter", len(cfg_list))
        logger.info("    Found %d entries with LORA weight", len(lora_weight_list))

        if sampler_list:
            sampler_scores = self._get_category_scores(sampler_list)
            self._save_category_stats("sampler_stats.json", sampler_scores)
        if scheduler_list:
            scheduler_scores = self._get_category_scores(scheduler_list)
            self._save_category_stats("scheduler_stats.json", scheduler_scores)

    def analyze_term_correlations(self) -> None:
        logger.info("  - Extracting term correlations...")
        term_scores: dict[str, list[float]] = {}
        for idx, text_entry in enumerate(self.text_data):
            if idx >= len(self.scores):
                continue
            score = self.scores[idx]
            pos_terms = text_entry.get("positive_terms", [])
            neg_terms = text_entry.get("negative_terms", [])
            for term_data in pos_terms:
                if isinstance(term_data, (list, tuple)):
                    term, weight = term_data[0], (term_data[1] if len(term_data) > 1 else 1.0)
                else:
                    term, weight = str(term_data), 1.0
                if term not in term_scores:
                    term_scores[term] = []
                term_scores[term].append(score * weight)
            for term_data in neg_terms:
                if isinstance(term_data, (list, tuple)):
                    term, weight = term_data[0], (term_data[1] if len(term_data) > 1 else 1.0)
                else:
                    term, weight = str(term_data), 1.0
                if term not in term_scores:
                    term_scores[term] = []
                term_scores[term].append(score * (1 - weight))

        term_stats: dict[str, dict[str, float | int]] = {}
        for term, scores in term_scores.items():
            if scores:
                term_stats[term] = {
                    "avg_score": float(np.mean(scores)),
                    "std_dev": float(np.std(scores)),
                    "count": len(scores),
                    "max_score": float(np.max(scores)),
                    "min_score": float(np.min(scores)),
                }
        sorted_terms = sorted(term_stats.items(), key=lambda x: x[1]["avg_score"], reverse=True)
        logger.info("  - Found %d unique terms", len(term_stats))
        logger.info("  - Top positive terms: %s", [t[0] for t in sorted_terms[:5]])
        with open(self.output_dir / "term_correlations.json", "w") as f:
            json.dump(
                {
                    "top_positive_terms": sorted_terms[:50],
                    "bottom_terms": sorted_terms[-50:],
                    "total_unique_terms": len(term_stats),
                    "summary": {
                        "terms_analyzed": len(term_stats),
                        "avg_score_across_all": float(np.mean(self.scores)),
                    },
                },
                f,
                indent=2,
            )

    def _get_category_scores(self, categories: list[str]) -> dict[str, list[float]]:
        category_scores: dict[str, list[float]] = {}
        for cat, score in zip(categories, self.scores[:len(categories)]):
            if cat not in category_scores:
                category_scores[cat] = []
            category_scores[cat].append(float(score))
        return category_scores

    def _save_category_stats(self, filename: str, category_scores: dict[str, list[float]]) -> None:
        stats = {}
        for category, scores in category_scores.items():
            if scores:
                stats[category] = {
                    "avg_score": float(np.mean(scores)),
                    "std_dev": float(np.std(scores)),
                    "count": len(scores),
                    "max": float(np.max(scores)),
                    "min": float(np.min(scores)),
                }
        with open(self.output_dir / filename, "w") as f:
            json.dump(stats, f, indent=2)

    def generate_report(self) -> None:
        report = f"""# Parameter Analysis Report

## Summary Statistics
- **Total images analyzed**: {len(self.vectors)}
- **Average score**: {np.mean(self.scores):.2f}
- **Std Dev**: {np.std(self.scores):.2f}
- **Min score**: {np.min(self.scores):.2f}
- **Max score**: {np.max(self.scores):.2f}
"""
        with open(self.output_dir / "report.md", "w") as f:
            f.write(report)
        logger.info("  Report saved to %s", self.output_dir / "report.md")


def main():
    logger.info("Parameter Analysis - Standalone Mode")
    logger.info("=" * 50)
    logger.info("Loading data...")
    vectors_data = list(load_single_jsonl(vectors_file))
    text_data = list(load_single_jsonl(text_data_file))
    if not vectors_data:
        logger.warning("No vectors data found. Run data preparation first.")
        return
    logger.info("Loaded %d vector entries", len(vectors_data))
    analyzer = ParameterAnalyzer(vectors_data, text_data)
    analyzer.analyze_all()


if __name__ == "__main__":
    main()