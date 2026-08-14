import torch
from typing import Any
from .....application.services.scoring_service import ScoringService
from ...services import get_scoring_service
from ...services import verify_models_present


class AestheticScoreNode:
    def __init__(self):
        # Construct ScoringService from the adapter wiring module (composition root)
        self._scoring_service: ScoringService = get_scoring_service()

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "image": ("IMAGE",),
                "threshold": (
                    "FLOAT",
                    {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05},
                ),
                "positive": ("STRING", {"multiline": True}),
                "negative": ("STRING", {"multiline": True}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 1000}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0}),
                "sampler": ("STRING", {"default": "euler"}),
                "scheduler": ("STRING", {"default": "normal"}),
                "model_name": ("STRING", {"default": "unknown"}),
                "lora_name": ("STRING", {"default": "unknown"}),
                "lora_strength": ("FLOAT", {"default": 0.0}),
                "min_images": ("INT", {"default": 1, "min": 0, "max": 100}),
                "max_images": ("INT", {"default": 10, "min": 0, "max": 100}),
            }
        }

    RETURN_TYPES = (
        "IMAGE",
        "IMAGE",
        "BOOLEAN",
        "LIST",
    )
    RETURN_NAMES = ("images", "discarded images", "Available", "score")
    FUNCTION = "calculate_score"
    CATEGORY = "Scoring"

    def calculate_score(
        self,
        image: torch.Tensor,
        threshold: float,
        positive: str,
        negative: str,
        steps: int,
        cfg: float,
        sampler: str,
        scheduler: str,
        model_name: str,
        lora_name: str,
        lora_strength: float,
        min_images: int = 1,
        max_images: int = 10,
    ) -> tuple[torch.Tensor, torch.Tensor, bool, list[float]]:
        verify_models_present()
        return self._scoring_service.score(
            image=image,
            threshold=threshold,
            positive=positive,
            negative=negative,
            steps=steps,
            cfg=cfg,
            sampler=sampler,
            scheduler=scheduler,
            model_name=model_name,
            lora_name=lora_name,
            lora_strength=lora_strength,
            min_images=min_images,
            max_images=max_images,
        )
