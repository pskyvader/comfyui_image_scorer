from typing import Any

from ....core.observability.logger import get_logger
from ....core.configuration.settings import config
from ....infrastructure.loading.training_loader import training_loader
from ....infrastructure.ml_models.training.model_trainer import model_trainer

logger = get_logger(__name__)


def train_model(steps: int = 100, **kwargs: Any) -> int:
    logger.info("Loading training data...")
    vectors = training_loader.load_vectors_array()
    scores = training_loader.load_scores_array()

    logger.info(f"Loaded {len(vectors)} samples, {vectors.shape[1]} features")

    try:
        lgb_config = dict(config["training"]["top1"])
    except KeyError:
        lgb_config = {}
    lgb_config["n_estimators"] = steps

    logger.info("Training model...")
    model, metrics = model_trainer.train_model(
        config_dict=lgb_config, X=vectors, y=scores, enable_plotting=False
    )

    logger.info(f"Training complete — score={metrics.get('score', 'N/A')}")
    training_loader.save_training_model(model, additional_data=metrics)
    return 0


def run_hpo(**kwargs: Any) -> int:
    from ....application.hyperparameters.hyperparameter_optimizer import run_hpo_cycles

    cycles = kwargs.get("cycles")
    steps_per_cycle = kwargs.get("steps_per_cycle")
    max_combos = kwargs.get("max_combos")

    result = run_hpo_cycles(
        cycles=cycles,
        steps_per_cycle=steps_per_cycle,
        max_combos=max_combos,
    )
    logger.info("HPO complete — best score=%s", result.get("best_score"))
    logger.info("Best config: %s", result.get("best_config"))
    return 0
