from __future__ import annotations

import random
from itertools import product, islice
from typing import Any

import numpy as np

from ...core.configuration.settings import config
from ...core.observability.logger import get_logger, ModuleLogger
from ...domain.data_transformation.data_transformer import (
    DataTransformer,
    list_filtered_features,
)
from ...domain.loading import TrainingLoader
from ...domain.training.grid import around, grid_base

logger: ModuleLogger = get_logger(__name__)

NUM_CONFIGS = 5

# Guard to prevent re-entrant or concurrent HPO loop runs. The HPO loop must
# be started explicitly and may not be invoked more than once at a time.
_hpo_running = False


def generate_random_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {"best_score": -1000000.0, "training_time": 0.0}
    for key, cell in grid_base.items():
        if cell["type"] == "int":
            cfg[key] = int(random.randint(int(cell["min"]), int(cell["max"])))
        else:
            cfg[key] = float(random.uniform(cell["min"], cell["max"]))
    return cfg


def generate_fastest_setup() -> dict[str, Any]:
    """Generates a config likely to be fast (fewer estimators, shallow trees)."""
    cfg: dict[str, Any] = {"best_score": -1000000.0, "training_time": 99999.0}
    force_max = {
        "min_child_samples",
        "reg_alpha",
        "reg_lambda",
        "min_split_gain",
        "learning_rate",
    }
    for key, cell in grid_base.items():
        bound_key = "max" if key in force_max else "min"
        if cell["type"] == "int":
            cfg[key] = int(cell[bound_key])
        else:
            cfg[key] = float(cell[bound_key])
    return cfg


def generate_slowest_setup() -> dict[str, Any]:
    """Generates a config likely to be slow (max estimators, deep trees)."""
    cfg: dict[str, Any] = {"best_score": -1000000.0, "training_time": 99999.0}
    force_min = {
        "min_child_samples",
        "reg_alpha",
        "reg_lambda",
        "min_split_gain",
        "learning_rate",
    }
    for key, cell in grid_base.items():
        bound_key = "min" if key in force_min else "max"
        if cell["type"] == "int":
            cfg[key] = int(cell[bound_key])
        else:
            cfg[key] = float(cell[bound_key])
    return cfg


def crossover_config(cfg1: dict[str, Any], cfg2: dict[str, Any]) -> dict[str, Any]:
    """Merge two configs into a new child by picking each key from one parent."""
    new_cfg: dict[str, Any] = {"best_score": -1000000.0, "training_time": 0.0}
    for key in grid_base.keys():
        new_cfg[key] = cfg1[key] if random.random() < 0.5 else cfg2[key]
    return new_cfg


def _load_state() -> dict[str, Any]:
    training_config = config["training"]
    return {
        "configs": [
            dict(training_config[f"top{i}"]) for i in range(1, NUM_CONFIGS + 1)
        ],
        "step": 0,
        "cycle": 0,
        "used_keys": (
            training_config["used_keys"] if "used_keys" in training_config else []
        ),
    }


def _save_state(state: dict[str, Any]) -> None:
    training_config = config["training"]
    for i in range(NUM_CONFIGS):
        training_config[f"top{i + 1}"] = state["configs"][i]
    training_config["used_keys"] = state["used_keys"]


def reset_hyperparameters() -> dict[str, Any]:
    configs = [
        generate_random_config(),
        generate_random_config(),
        generate_slowest_setup(),
        generate_fastest_setup(),
        generate_random_config(),
    ]
    state = {"configs": configs, "step": 0, "cycle": 0, "used_keys": []}
    _save_state(state)
    return state


def load_training_data(
    filter_comparisons: bool, training_loader: TrainingLoader, model_trainer: Any
) -> tuple[np.ndarray, np.ndarray]:
    """Load keyed vectors/scores and compress unused features. When
    filter_comparisons is True, keep only files with enough comparisons
    (scores replayed on the kept subset); otherwise keep every scored file
    with its full-history score."""
    transformer = DataTransformer(training_loader, model_trainer)
    vectors_keyed = training_loader.load_vectors()
    scores_keyed = training_loader.load_scores()
    n_features_total = next(iter(vectors_keyed.values())).shape[0]
    logger.info(
        "raw data loaded: %s vectors, %s scores, %s features",
        len(vectors_keyed),
        len(scores_keyed),
        n_features_total,
    )

    filter_steps = 1000
    logger.info("filtering unused features after %s steps...", filter_steps)
    kept_feature_idx = transformer.filter_unused_features(
        vectors_keyed, scores_keyed, steps=filter_steps
    )
    list_filtered_features(transformer)
    logger.info(
        "Feature filtering: kept %s features (%.1f%%), dropped %s.",
        len(kept_feature_idx),
        100 * len(kept_feature_idx) / n_features_total,
        n_features_total - len(kept_feature_idx),
    )

    threshold = config["training"]["min_comparisons_threshold"]
    kept_filenames: set[str] | None = None
    scores_subset: dict[str, float] | None = None
    if filter_comparisons:
        logger.info("filtering low comparison data (threshold=%s) ...", threshold)
        rule = transformer.filter_low_comparisons(threshold=threshold)
        kept_filenames = set(rule)
        scores_subset = {fid: score for fid, (score, _count) in rule.items()}
        logger.info(
            "Comparison filtering: kept %s filenames (threshold=%s), dropped %s.",
            len(kept_filenames),
            threshold,
            len(scores_keyed) - len(kept_filenames),
        )

    x_rows: list[np.ndarray] = []
    y_rows: list[float] = []
    for fid in scores_keyed:
        if kept_filenames is not None and fid not in kept_filenames:
            continue
        vec = vectors_keyed.get(fid)
        if vec is None:
            continue
        x_rows.append(vec[kept_feature_idx])
        y_rows.append(
            scores_subset[fid] if scores_subset is not None else scores_keyed[fid]
        )

    x = np.array(x_rows, dtype=np.float32)
    y = np.array(y_rows, dtype=np.float32)
    logger.info("Training data ready: X=%s, Y=%s", x.shape, y.shape)
    return x, y


def _evaluate_config(
    cfg: dict[str, Any], X: np.ndarray, y: np.ndarray, model_trainer: Any
) -> tuple[float, float, str]:
    _, metrics = model_trainer.train_model(
        config_dict=cfg, X=X, y=y
    )
    return (
        float(metrics["score"]),
        float(metrics["training_time"]),
        str(metrics["primary_metric"]),
    )


def _run_step_on_config(
    cfg: dict[str, Any],
    used_keys: list[str],
    X: np.ndarray,
    y: np.ndarray,
    max_combos: int,
    model_trainer: Any,
) -> tuple[dict[str, Any], list[str]]:
    all_keys = list(grid_base.keys())
    random.shuffle(all_keys)

    chosen_key = None
    for key in all_keys:
        if key not in used_keys:
            chosen_key = key
            break
    if chosen_key is None:
        chosen_key = all_keys[0]
        used_keys = []

    varied_vals = around(chosen_key, cfg[chosen_key])
    logger.info(
        "    Varying: %s (current=%s) -> %s",
        chosen_key,
        f"{cfg[chosen_key]:.6g}",
        [round(v, 6) for v in varied_vals],
    )
    logger.info("    Recently used params: %s", used_keys)

    param_grid = {k: [cfg[k]] for k in all_keys}
    param_grid[chosen_key] = varied_vals

    keys_grid = list(param_grid.keys())
    value_lists = [list(param_grid[k]) for k in keys_grid]
    all_combos = [dict(zip(keys_grid, vals)) for vals in product(*value_lists)]
    combos = list(islice(iter(all_combos), max_combos))

    best_cfg = cfg.copy()
    best_score = cfg.get("best_score")
    best_time = cfg.get("training_time")
    training_objective = config["training"]["objective"]
    improved = False

    for i, combo in enumerate(combos):
        logger.info("---" * 10)
        merged = {**cfg, **combo}
        score, t_time, primary_metric = _evaluate_config(merged, X, y, model_trainer)
        directions = model_trainer.METRIC_DIRECTIONS.get(training_objective, {})
        higher_is_better = directions.get(primary_metric, True)

        arrow = ""
        if (higher_is_better and score > best_score) or (
            not higher_is_better and score < best_score
        ):
            best_score = score
            best_time = t_time
            best_cfg = {**merged, "best_score": score, "training_time": t_time}
            arrow = "  <-- NEW BEST"
            improved = True

        logger.info(
            "      Combo %s/%s: %s=%s  score=%.6f  time=%.2fs%s",
            i + 1,
            len(combos),
            chosen_key,
            f"{combo[chosen_key]:.6g}",
            score,
            t_time,
            arrow,
        )

    if improved:
        logger.info(
            "    Config improved: score=%.6f, time=%.2fs", best_score, best_time
        )
    else:
        logger.info("    Config unchanged: best score remains %s", best_score)
        used_keys.append(chosen_key)

    if len(used_keys) > len(all_keys):
        used_keys = used_keys[-len(all_keys) // 3 :]

    return best_cfg, used_keys


def hpo_cycle(
    X: np.ndarray,
    y: np.ndarray,
    model_trainer: Any,
    optimization_steps: int,
    max_combos: int,
    cycle: int,
) -> dict[str, Any]:
    global _hpo_running
    if _hpo_running:
        raise RuntimeError(
            "HPO loop is already running. Concurrent or nested runs are not allowed."
        )
    _hpo_running = True
    try:
        state = _load_state()
        if (
            not state
            or "configs" not in state
            or len(state.get("configs", [])) != NUM_CONFIGS
        ):
            raise RuntimeError(
                "HPO state missing or invalid. Call reset_hyperparameters() to initialize."
            )

        configs = state["configs"]
        used_keys = state.get("used_keys", [])
        step_start = state.get("step", 0)

        logger.info("\n" + "=" * 80)
        logger.info(
            "HPO Cycle %s — Starting from step %s/%s",
            cycle + 1,
            step_start,
            optimization_steps,
        )

        for i in range(step_start, optimization_steps):
            idx = i % NUM_CONFIGS
            logger.info("\n" + "---" * 25)
            logger.info("Step %s/%s  —  Config %s", i + 1, optimization_steps, idx + 1)
            cfg = configs[idx]
            logger.info(
                "best_score=%s  training_time=%.2fs",
                f"{cfg['best_score']:.6f}",
                cfg.get("training_time"),
            )
            logger.info(" %s", cfg)

            configs[idx], used_keys = _run_step_on_config(
                configs[idx], used_keys, X, y, max_combos, model_trainer
            )
            state["step"] = i + 1
            state["configs"] = configs
            state["used_keys"] = used_keys
            _save_state(state)

        logger.info("\n" + "=" * 80)
        logger.info("Cycle complete — Sorting configs by score")

        training_objective = config["training"]["objective"]
        directions = model_trainer.METRIC_DIRECTIONS.get(training_objective, {})
        if directions:
            higher_is_better = any(bool(v) for v in directions.values())
        else:
            higher_is_better = True

        logger.info(
            "Sorting configs with higher_is_better=%s (objective=%s)",
            higher_is_better,
            training_objective,
        )
        configs.sort(
            key=lambda c: c.get("best_score", -1000000.0),
            reverse=higher_is_better,
        )
        for i, c in enumerate(configs):
            logger.info(
                "  Rank %s: score=%s  time=%.2fs",
                i + 1,
                f"{c.get('best_score', -1):.6f}",
                c.get("training_time", 0),
            )

        logger.info(
            "\nBreeding next generation — keeping top 2, creating 2 children via crossover"
        )
        parents = [configs[0], configs[1]]
        child1 = crossover_config(dict(parents[0]), dict(parents[1]))
        child2 = crossover_config(dict(parents[0]), dict(parents[1]))
        random_child = generate_random_config()
        logger.info("  Parent 1:  score=%s", f"{parents[0].get('best_score', -1):.6f}")
        logger.info("  Parent 2:  score=%s", f"{parents[1].get('best_score', -1):.6f}")

        new_configs = [parents[0], parents[1], child1, child2, random_child]
        new_state = {
            "configs": new_configs,
            "step": 0,
            "cycle": cycle + 1,
            "used_keys": used_keys,
        }
        _save_state(new_state)

        logger.info(
            "\nCycle %s complete. Trigger again to start next cycle.", cycle + 1
        )
        logger.info("=" * 80 + "\n")
        return new_state
    finally:
        _hpo_running = False


def run_hpo_cycles(
    cycles: int | None,
    optimization_steps: int | None,
    max_combos: int | None,
    training_loader: TrainingLoader | None,
    model_trainer: Any,
) -> list[dict[str, Any]]:
    """Run multiple HPO cycles. Each cycle runs optimization_steps steps
    over the top1..top5 configs and breeds the next generation."""
    training_config = config["training"]
    if cycles is None:
        cycles = int(training_config["cycles"])
    if optimization_steps is None:
        optimization_steps = int(training_config["optimization_steps"])
    if max_combos is None:
        max_combos = int(training_config["max_combos"])
    if training_loader is None or model_trainer is None:
        raise RuntimeError("training_loader and model_trainer must be provided")

    X, y = load_training_data(
        filter_comparisons=True,
        training_loader=training_loader,
        model_trainer=model_trainer,
    )

    results = []
    for i in range(cycles):
        logger.info("[run_hpo_cycles] Starting cycle %s/%s", i + 1, cycles)
        res = hpo_cycle(
            X,
            y,
            model_trainer=model_trainer,
            optimization_steps=optimization_steps,
            max_combos=max_combos,
            cycle=i,
        )
        results.append(res)
    return results
