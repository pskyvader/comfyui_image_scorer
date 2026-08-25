"""ComfyUI node wiring - builds ScoringService from infrastructure singletons."""

from ...core.configuration.settings import config

# Initialize core config before any core filesystem imports
if config["image_root"] == "":
    from folder_paths import get_output_directory
    config.set_root("image_root", get_output_directory())

from ...application.services.scoring_service import ScoringService
from ...infrastructure.ml_models.model_loader import (
    verify_models_present,
    model_loader,
)
from ...infrastructure.ml_models.batch_sizer import BatchSizer
from ...infrastructure.ml_models.image_export import export_image_batch
from ...infrastructure.cache.memory_cache import InMemoryCache
from ...infrastructure.loading.training_loader import training_loader
from ...infrastructure.ml_models.training.model_trainer import model_trainer
from ...infrastructure.loading.maps_loader import maps_list

__all__ = ["get_scoring_service", "verify_models_present"]

_scoring_cache = InMemoryCache()


def get_scoring_service() -> ScoringService:
    return ScoringService(
        model_loader=model_loader,
        batch_sizer=BatchSizer,
        training_loader=training_loader,
        model_trainer=model_trainer,
        maps_provider=maps_list,
        cache=_scoring_cache,
        export_batch=export_image_batch,
    )
