from typing import Any

from ....core.observability.logger import get_logger
from ....core.configuration.settings import config
from ....infrastructure.loading.training_loader import training_loader
from ....infrastructure.ml_models.training.model_trainer import model_trainer

logger = get_logger(__name__)


def train_model() -> int:
    from ....application.hyperparameters.hyperparameter_optimizer import (
        load_training_data,
    )

    logger.info("Loading training data...")
    # vectors = training_loader.load_vectors_array()
    # scores = training_loader.load_scores_array()
    vectors, scores = load_training_data()

    logger.info(f"Loaded {len(vectors)} samples, {vectors.shape[1]} features")

    lgb_config = dict(config["training"]["top1"])

    logger.info("Training model...")
    model, metrics = model_trainer.train_model(
        config_dict=lgb_config, X=vectors, y=scores, enable_plotting=True
    )

    logger.info(f"Training complete — score={metrics.get('score', 'N/A')}")
    training_loader.save_training_model(model, additional_data=metrics)
    return 0


def run_hpo(**kwargs: Any) -> int:
    from ....application.hyperparameters.hyperparameter_optimizer import run_hpo_cycles

    cycles = kwargs.get("cycles")
    optimization_steps = kwargs.get("optimization_steps")
    max_combos = kwargs.get("max_combos")

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

    result = run_hpo_cycles(
        cycles=cycles, optimization_steps=optimization_steps, max_combos=max_combos
    )
    logger.info("HPO complete — %s cycles run", len(result))
    if result:
        logger.info("Best config: %s", result[-1]["configs"][0])
    return 0
