"""Training commands: train-model and hpo."""
import os

import matplotlib.pyplot as plt

from ....application.hyperparameters.hyperparameter_optimizer import (
    load_training_data,
)
from ....core.observability.logger import get_logger
from ....core.configuration.settings import config
from ....core.filesystem.paths import training_plots_dir
from ..deps import CLIDeps

logger = get_logger(__name__)


def train_model(deps: CLIDeps) -> int:
    logger.info("Loading training data...")
    vectors, scores = load_training_data(
        filter_comparisons=True,
        training_loader=deps.training_loader,
        model_trainer=deps.model_trainer,
    )

    logger.info(f"Loaded {len(vectors)} samples, {vectors.shape[1]} features")

    lgb_config = dict(config["training"]["top1"])

    logger.info("Training model...")
    model, metrics = deps.model_trainer.train_model(
        config_dict=lgb_config, X=vectors, y=scores
    )

    logger.info(f"Training complete — score={metrics.get('score', 'N/A')}")
    deps.training_loader.save_training_model(model, additional_data=metrics)

    vectors_full, scores_full = load_training_data(
        filter_comparisons=False,
        training_loader=deps.training_loader,
        model_trainer=deps.model_trainer,
    )
    os.makedirs(training_plots_dir, exist_ok=True)
    deps.plot_manager.plot_loss_curve(
        metrics,
        save_path=os.path.join(training_plots_dir, "training_curves.png"),
        show=True,
    )
    deps.plot_manager.plot_score_distribution(
        scores,
        save_path=os.path.join(training_plots_dir, "score_distribution.png"),
        show=True,
    )
    deps.plot_manager.compare_model_vs_data(
        vectors_full,
        scores_full,
        training_loader=deps.training_loader,
        plot=True,
        limit=1000,
        save_path=os.path.join(training_plots_dir, "prediction_accuracy.png"),
        show=True,
    )
    plt.show()
    return 0


def run_hpo(
    deps: CLIDeps,
    cycles: int | None,
    optimization_steps: int | None,
    max_combos: int | None,
) -> int:
    defaults = config["training"]
    logger.info(
        "HPO options — cycles=%s, optimization_steps=%s, max_combos=%s",
        cycles if cycles is not None else f'{defaults["cycles"]} (config default)',
        (
            optimization_steps
            if optimization_steps is not None
            else f'{defaults["optimization_steps"]} (config default)'
        ),
        (
            max_combos
            if max_combos is not None
            else f'{defaults["max_combos"]} (config default)'
        ),
    )

    result = deps.hpo_runner.run(
        cycles=cycles,
        optimization_steps=optimization_steps,
        max_combos=max_combos,
        training_loader=deps.training_loader,
        model_trainer=deps.model_trainer,
    )
    logger.info("HPO complete — %s cycles run", len(result))
    if result:
        logger.info("Best config: %s", result[-1]["configs"][0])
    return 0
