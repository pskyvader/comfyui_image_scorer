"""
Parameter Analysis Module
Analyzes relationships between parameters/terms and image scores.
"""

import json
import traceback

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import Normalize
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler
from typing import Any

from ...core.io.serialization import load_single_jsonl
from ...core.filesystem.paths import vectors_file, text_data_file

matplotlib.use("Agg")

SKLEARN_AVAILABLE = True
MATPLOTLIB_AVAILABLE = True


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
        print("Starting parameter analysis...")
        if MATPLOTLIB_AVAILABLE:
            print("Analyzing parameter relationships...")
            self.analyze_parameter_pairs()
            self.analyze_term_correlations()
            print("Parameter analysis complete")
        else:
            print("matplotlib not available - skipping visualization")
        print("Generating analysis report...")
        self.generate_report()
        print(f"Analysis complete! Output saved to {self.output_dir}")

    def analyze_parameter_pairs(self) -> None:
        if not MATPLOTLIB_AVAILABLE:
            return
        print("  - Extracting parameters...")
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

        print(f"    Found {len(steps_list)} entries with steps parameter")
        print(f"    Found {len(cfg_list)} entries with CFG parameter")
        print(f"    Found {len(lora_weight_list)} entries with LORA weight")

        if len(steps_list) > 1:
            self._create_scatter(np.array(steps_list), self.scores[:len(steps_list)], self.scores[:len(steps_list)], "steps_vs_score", "Sampling Steps", "Score", normalize=True)
        if len(cfg_list) > 1:
            self._create_scatter(np.array(cfg_list), self.scores[:len(cfg_list)], self.scores[:len(cfg_list)], "cfg_vs_score", "CFG Scale", "Score", normalize=True)
        if len(steps_list) > 1 and len(cfg_list) > 1:
            min_len = min(len(steps_list), len(cfg_list))
            self._create_2d_scatter(np.array(steps_list[:min_len]), np.array(cfg_list[:min_len]), self.scores[:min_len], "steps_vs_cfg", "Sampling Steps", "CFG Scale", "Score")
        if sampler_list:
            sampler_scores = self._get_category_scores(sampler_list)
            self._save_category_stats("sampler_stats.json", sampler_scores)
        if scheduler_list:
            scheduler_scores = self._get_category_scores(scheduler_list)
            self._save_category_stats("scheduler_stats.json", scheduler_scores)

    def analyze_term_correlations(self) -> None:
        if not MATPLOTLIB_AVAILABLE:
            return
        print("  - Extracting term correlations...")
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

        term_stats = {}
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
        print(f"  - Found {len(term_stats)} unique terms")
        print(f"  - Top positive terms: {[t[0] for t in sorted_terms[:5]]}")
        with open(self.output_dir / "term_correlations.json", "w") as f:
            json.dump({
                "top_positive_terms": sorted_terms[:50],
                "bottom_terms": sorted_terms[-50:],
                "total_unique_terms": len(term_stats),
                "summary": {"terms_analyzed": len(term_stats), "avg_score_across_all": float(np.mean(self.scores))},
            }, f, indent=2)

    def _create_scatter(self, x: np.ndarray, y: np.ndarray, colors: np.ndarray, name: str, xlabel: str, ylabel: str, normalize: bool = False) -> None:
        if not MATPLOTLIB_AVAILABLE or plt is None:
            return
        try:
            fig, ax = plt.subplots(figsize=(10, 8))
            if normalize and SKLEARN_AVAILABLE and MinMaxScaler is not None:
                scaler = MinMaxScaler()
                x_plot = scaler.fit_transform(x.reshape(-1, 1)).flatten()
            else:
                x_plot = x
            scatter = ax.scatter(x_plot, y, c=colors, cmap="viridis", s=50, alpha=0.6, edgecolors="k")
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_title(f"{xlabel} vs {ylabel}")
            plt.colorbar(scatter, ax=ax, label="Score")
            plt.tight_layout()
            plt.savefig(self.output_dir / f"{name}.png", dpi=150, bbox_inches="tight")
            plt.close()
            print(f"    Saved {name}.png")
        except Exception:
            pass

    def _create_2d_scatter(self, x: np.ndarray, y: np.ndarray, colors: np.ndarray, name: str, xlabel: str, ylabel: str, zlabel: str) -> None:
        if not MATPLOTLIB_AVAILABLE or plt is None:
            return
        try:
            fig, ax = plt.subplots(figsize=(12, 9))
            scatter = ax.scatter(x, y, c=colors, cmap="coolwarm", s=100, alpha=0.7, edgecolors="k", linewidth=0.5)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_title(f"{xlabel} vs {ylabel} (colored by {zlabel})")
            plt.colorbar(scatter, ax=ax, label=zlabel)
            if len(x) > 1:
                corr = np.corrcoef(x, y)[0, 1]
                ax.text(0.05, 0.95, f"Correlation: {corr:.3f}", transform=ax.transAxes, fontsize=11, verticalalignment="top", bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8))
            plt.tight_layout()
            plt.savefig(self.output_dir / f"{name}.png", dpi=150, bbox_inches="tight")
            plt.close()
            print(f"    Saved {name}.png")
        except Exception:
            pass

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
        print(f"  Report saved to {self.output_dir / 'report.md'}")


def main():
    print("Parameter Analysis - Standalone Mode")
    print("=" * 50)
    print("Loading data...")
    try:
        vectors_data = list(load_single_jsonl(vectors_file))
        text_data = list(load_single_jsonl(text_data_file))
        if not vectors_data:
            print("No vectors data found. Run data preparation first.")
            return
        print(f"Loaded {len(vectors_data)} vector entries")
        analyzer = ParameterAnalyzer(vectors_data, text_data)
        analyzer.analyze_all()
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
