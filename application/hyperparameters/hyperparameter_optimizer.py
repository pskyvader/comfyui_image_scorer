from __future__ import annotations

import copy
import itertools
import random
import time
from typing import Any

import numpy as np

from ...core.observability.logger import get_logger, ModuleLogger
from ...core.configuration.settings import config
from ...infrastructure.loading.training_loader import training_loader
from ...infrastructure.ml_models.training.model_trainer import model_trainer, grid_base, around

logger: ModuleLogger = get_logger(__name__)


def load_training_data() -> tuple[np.ndarray, np.ndarray]:
    vectors = training_loader.load_vectors_array()
    scores = training_loader.load_scores_array()
    return vectors, scores


def _sample_combinations(base_config: dict[str, Any], max_combos: int) -> list[dict[str, Any]]:
    varied: dict[str, list[Any]] = {}
    for key in ["learning_rate", "num_leaves", "max_depth", "min_child_samples",
                 "reg_alpha", "reg_lambda", "subsample", "colsample_bytree",
                 "min_split_gain", "n_estimators", "early_stopping_rounds"]:
        current = base_config.get(key)
        if current is not None:
            varied[key] = list(around(key, current))

    if not varied:
        return [base_config]

    keys, values = zip(*varied.items())
    all_combos = [dict(zip(keys, combo)) for combo in itertools.product(*values)]

    if len(all_combos) <= max_combos:
        return all_combos

    return random.sample(all_combos, max_combos)


def hpo_cycle(
    config_dict: dict[str, Any],
    X: np.ndarray,
    y: np.ndarray,
    cycle: int,
) -> dict[str, Any]:
    logger.info("HPO cycle %s: training with %s", cycle, config_dict)
    model, metrics = model_trainer.train_model(
        config_dict=config_dict, X=X, y=y, enable_plotting=False,
    )
    score = metrics.get("score", 0.0)
    logger.info("HPO cycle %s complete — score=%s", cycle, score)
    return {"config": config_dict, "metrics": metrics, "cycle": cycle}


def run_hpo_cycles(
    cycles: int | None = None,
    steps_per_cycle: int | None = None,
    max_combos: int | None = None,
) -> dict[str, Any]:
    training_config = config["training"]
    if cycles is None:
        cycles = int(training_config["cycles"])
    if steps_per_cycle is None:
        steps_per_cycle = int(training_config["steps_per_cycle"])
    if max_combos is None:
        max_combos = int(training_config["max_combos"])

    X, y = load_training_data()
    logger.info("Loaded %s samples, %s features", len(X), X.shape[1])

    top1 = training_config["top1"]
    base_config: dict[str, Any] = {
        "n_estimators": steps_per_cycle,
        "learning_rate": top1["learning_rate"],
        "num_leaves": top1["num_leaves"],
        "max_depth": top1["max_depth"],
        "min_child_samples": top1["min_child_samples"],
        "reg_alpha": top1["reg_alpha"],
        "reg_lambda": top1["reg_lambda"],
        "subsample": top1["subsample"],
        "colsample_bytree": top1["colsample_bytree"],
        "min_split_gain": top1["min_split_gain"],
        "early_stopping_rounds": top1["early_stopping_rounds"],
    }

    all_results: list[dict[str, Any]] = []
    best_score = -float("inf")
    best_config: dict[str, Any] = {}

    for cycle in range(1, cycles + 1):
        combos = _sample_combinations(base_config, max_combos)
        logger.info(
            "Cycle %s/%s: testing %s configurations",
            cycle, cycles, len(combos),
        )
        cycle_results: list[dict[str, Any]] = []
        for cfg in combos:
            cfg["n_estimators"] = steps_per_cycle
            result = hpo_cycle(cfg, X, y, cycle)
            cycle_results.append(result)

        for result in cycle_results:
            score = result["metrics"].get("score", 0.0)
            if score > best_score:
                best_score = score
                best_config = result["config"]
                logger.info("New best score: %s", score)

        all_results.extend(cycle_results)

        if best_config:
            for k, v in best_config.items():
                if k in base_config:
                    base_config[k] = v

    all_results.sort(key=lambda r: r["metrics"].get("score", 0.0), reverse=True)
    return {
        "best_score": best_score,
        "best_config": best_config,
        "total_cycles": cycles,
        "total_trials": len(all_results),
    }
