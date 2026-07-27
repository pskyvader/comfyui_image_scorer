from typing import Any


def run_training(steps: int = 100, **kwargs: Any) -> int:
    from comfyui_image_scorer.infrastructure.ml_models.training.model_trainer import model_trainer

    return 0