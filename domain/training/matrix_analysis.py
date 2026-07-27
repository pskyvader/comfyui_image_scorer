"""
2D Matrix Analysis for Text Data Parameters

Creates a symmetric matrix combining ALL parameters from text data.
Each row/column is a unique parameter value extracted from text records.
Each cell contains scores for records that have both parameters.
"""

from typing import Any
from collections import defaultdict
import numpy as np
from tqdm import tqdm
import polars as pl

from comfyui_image_scorer.core.io.serialization import write_single_jsonl


class MatrixAnalyzer:
    def __init__(
        self,
        scores: list[float],
        text_data: list[dict[str, Any]],
        memory_limit: int = 10000,
    ):
        self.scores = scores
        self.text_data = text_data
        self.memory_limit = memory_limit
        self.all_params: set[str] = set()
        self.param_id_map: dict[str, int] = {}
        self.param_list: list[str] = []
        self.matrix: dict[int, dict[int, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.cell_stats: dict[tuple[int, int], dict[str, float]] = {}

    @staticmethod
    def get_text_weight(original_text: str) -> tuple[str, float]:
        original_text = original_text.replace("(", "").replace(")", "").strip()
        parts = original_text.split(":")
        text = parts[0]
        weight = 1.0
        if len(parts) > 1:
            try:
                weight = float(parts[-1])
            except ValueError:
                weight = 1.0
        normalized_text = " ".join(str(text).split()).lower()
        return normalized_text, weight

    def _extract_all_params_from_record(self, record: dict[str, Any]) -> list[str]:
        params: list[str] = []

        lora_value = record.get("lora", None)
        if isinstance(lora_value, dict):
            for lname, lweight in lora_value.items():
                if not lname:
                    continue
                lora_norm, _ = self.get_text_weight(str(lname))
                lora_weight_rounded = round(
                    float(lweight) if isinstance(lweight, (int, float)) else 0, 2
                )
                param_str = f"lora:{lora_norm}_{lora_weight_rounded}".strip()
                if param_str:
                    params.append(param_str)
        elif isinstance(lora_value, str) and lora_value:
            lora_weight = record.get("lora_weight", 0)
            lora_norm, _ = self.get_text_weight(lora_value)
            lora_weight_rounded = round(
                float(lora_weight) if isinstance(lora_weight, (int, float)) else 0, 2
            )
            param_str = f"lora:{lora_norm}_{lora_weight_rounded}".strip()
            if param_str:
                params.append(param_str)

        for key, value in record.items():
            if key.lower() in ("lora", "lora_weight"):
                continue
            if key.lower() == "clip_skip" and value is not None:
                if isinstance(value, (int, float)):
                    value = -abs(float(value))
                    self._add_param_from_value(key, value, params)
                continue
            self._add_param_from_value(key, value, params)

        return params

    def _add_param_from_value(
        self, key: str, value: Any, params: list[str], prefix: str = ""
    ) -> None:
        if value is None or value == "":
            return
        key_norm, weight = self.get_text_weight(key)
        if isinstance(value, (str, int, float, bool)):
            if isinstance(value, float):
                value = round(value * weight, 2)
            param_str = f"{prefix}{key_norm}:{value}".strip()
            if param_str:
                params.append(param_str)
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, (str, int, float)):
                    if isinstance(item, float):
                        item = round(item * weight, 2)
                    param_str = f"{prefix}{key_norm}:{item}".strip()
                    params.append(param_str)
                elif isinstance(item, (list, tuple)) and len(item) > 0:
                    name = str(item[0])
                    tuple_weight = item[1] if len(item) > 1 else ""
                    name_norm, weight2 = self.get_text_weight(name)
                    if isinstance(tuple_weight, (int, float)):
                        tuple_weight = round(tuple_weight * weight * weight2, 2)
                    param_str = f"{prefix}{key_norm}:{name_norm}_{tuple_weight}".strip()
                    params.append(param_str)

    def build_matrix(self) -> None:
        print(f"Processing {len(self.text_data)} text records...")
        all_params_set: set[str] = set()
        with tqdm(
            total=len(self.text_data), desc="Extracting parameters", unit=" records", delay=3.0
        ) as pbar:
            for record in self.text_data:
                params = self._extract_all_params_from_record(record)
                all_params_set.update(params)
                pbar.update(1)
                if len(all_params_set) > self.memory_limit:
                    print(f"  WARNING: Parameter limit ({self.memory_limit}) reached, truncating...")
                    all_params_set = set(sorted(list(all_params_set))[:self.memory_limit])
                    break

        self.all_params = all_params_set
        self.param_list = sorted(list(all_params_set))
        for idx, param in enumerate(self.param_list):
            self.param_id_map[param] = idx
        print(f"Found {len(self.param_list)} unique parameters")

        print("Building parameter co-occurrence matrix...")
        with tqdm(
            total=len(self.text_data), desc="Building matrix", unit=" records", delay=3.0
        ) as pbar:
            for i, record in enumerate(self.text_data):
                score = self.scores[i] if i < len(self.scores) else 3.0
                params = self._extract_all_params_from_record(record)
                params = [p for p in params if p in self.param_id_map]
                for j, p1 in enumerate(params):
                    p1_id = self.param_id_map[p1]
                    for p2 in params[j:]:
                        p2_id = self.param_id_map[p2]
                        self.matrix[p1_id][p2_id].append(score)
                        if p1_id != p2_id:
                            self.matrix[p2_id][p1_id].append(score)
                pbar.update(1)
        print(f"Matrix built: {len(self.param_list)}x{len(self.param_list)} parameters")

    def calculate_statistics(self, min_count: int = 100) -> dict[tuple[int, int], dict[str, float]]:
        flattened_data: list[tuple[int, int, float]] = []
        kept_cells = 0
        dropped_cells = 0
        size = len(self.param_list)
        total_possible_cells = (size * (size + 1)) // 2

        with tqdm(total=total_possible_cells, desc="Flattening Matrix", unit="cells", delay=3.0) as pbar:
            for p1_id in range(size):
                for p2_id in range(p1_id, size):
                    scores = self.matrix[p1_id][p2_id]
                    if isinstance(scores, list) and len(scores) >= min_count:
                        for s in scores:
                            flattened_data.append((p1_id, p2_id, float(s)))
                        kept_cells += 1
                    else:
                        dropped_cells += 1
                    if (p1_id * size + p2_id) % 10000 == 0:
                        pbar.update(10000)
            pbar.n = total_possible_cells
            pbar.refresh()

        print(f"Stats: Kept {kept_cells} cells, Dropped {dropped_cells} cells (Min Count: {min_count})")
        if not flattened_data:
            print("No data met the threshold.")
            return {}

        print("Calculating Statistics via Polars (Multithreaded)...")
        df = pl.DataFrame(flattened_data, schema=[("p1", pl.Int32), ("p2", pl.Int32), ("score", pl.Float64)])
        stats_df = (
            df.lazy()
            .group_by(["p1", "p2"])
            .agg([
                pl.len().alias("count"),
                pl.col("score").mean().alias("mean"),
                pl.col("score").std().alias("std"),
                pl.col("score").min().alias("min"),
                pl.col("score").max().alias("max"),
                pl.col("score").median().alias("median"),
                pl.col("score").mode().first().alias("mode"),
                pl.col("score").quantile(0.25).alias("q1"),
                pl.col("score").quantile(0.75).alias("q3"),
            ])
            .collect()
        )

        self.cell_stats = {}
        for row in tqdm(stats_df.iter_rows(named=True), total=len(stats_df), desc="Building Final Dict", delay=3.0):
            p1, p2 = row["p1"], row["p2"]
            q1 = float(row["q1"]) if row["q1"] is not None else 0.0
            q3 = float(row["q3"]) if row["q3"] is not None else 0.0
            iqr = q3 - q1
            mean_val = float(row["mean"])
            std_val = float(row["std"]) if row["std"] is not None else 0.0
            cv = (std_val / mean_val) if mean_val != 0 else 99.9
            range_val = float(row["max"]) - float(row["min"])
            stats = {
                "count": float(row["count"]),
                "mean": mean_val,
                "std": std_val,
                "min": float(row["min"]),
                "max": float(row["max"]),
                "median": float(row["median"]),
                "mode": float(row["mode"]) if row["mode"] is not None else 0.0,
                "q1": q1,
                "q3": q3,
                "iqr": iqr,
                "cv": cv,
                "range": range_val,
            }
            self.cell_stats[(p1, p2)] = stats
            if p1 != p2:
                self.cell_stats[(p2, p1)] = stats
        return self.cell_stats

    def export_to_json(self, output_path: str) -> None:
        export_data_list: list[dict[str, Any]] = []
        with tqdm(total=len(self.cell_stats), desc="Exporting to JSON", unit=" cells", delay=3.0) as pbar:
            for (p1_id, p2_id), stats in self.cell_stats.items():
                if p1_id > p2_id:
                    pbar.update(1)
                    continue
                p1_param = self.param_list[p1_id] if p1_id < len(self.param_list) else str(p1_id)
                p2_param = self.param_list[p2_id] if p2_id < len(self.param_list) else str(p2_id)
                export_data_list.append({"parameters": f"{p1_param}|{p2_param}", **stats})
                pbar.update(1)
        write_single_jsonl(output_path, export_data_list, "w")
        print(f"Exported {len(export_data_list)} cell statistics to {output_path}")

    def print_top_correlations(self, top_n: int = 20) -> None:
        print(f"\nTop {top_n} strongest parameter correlations (by mean score):")
        print("=" * 80)
        sorted_cells = sorted(self.cell_stats.items(), key=lambda x: x[1]["mean"], reverse=True)[:top_n]
        for (p1_id, p2_id), stats in sorted_cells:
            p1_param = self.param_list[p1_id] if p1_id < len(self.param_list) else str(p1_id)
            p2_param = self.param_list[p2_id] if p2_id < len(self.param_list) else str(p2_id)
            print(f"{p1_param:40s} + {p2_param:40s}")
            print(f"  mean: {stats['mean']:.2f} | std: {stats['std']:.2f} | count: {stats['count']}")

    def get_matrix_size(self) -> tuple[int, int]:
        return (len(self.param_list), len(self.param_list))

    def get_matrix_summary(self) -> dict[str, Any]:
        all_means = [stats["mean"] for stats in self.cell_stats.values()]
        all_counts = [stats["count"] for stats in self.cell_stats.values()]
        return {
            "total_parameters": len(self.param_list),
            "matrix_cells": len(self.cell_stats),
            "total_score_entries": sum(all_counts),
            "mean_of_means": float(np.mean(all_means)) if all_means else 0.0,
            "loaded_records": len(self.text_data),
            "loaded_vectors": len(self.scores),
        }
