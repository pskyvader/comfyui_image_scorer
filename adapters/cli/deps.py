"""CLI composition root - builds injected dependencies for the CLI commands."""

from dataclasses import dataclass
from typing import Any

from ...core.configuration.settings import config
from ...domain.loading.ports import BatchSizerFactory, MapsProvider, ModelLoader
from ...domain.ports.cache import CacheProvider
from ...domain.comparison.constants import IMAGES_CACHE_TTL
from ...application.services.graph_service import CrystalGraph
from ...application.hyperparameters.hyperparameter_optimizer import HpoRunner
from ...infrastructure.ml_models.plot import PlotManager
from ...application.services.image_processor import ImageProcessor, PathOps
from ...infrastructure.persistence.comparisons_repository import (
    SQLiteComparisonsRepository,
)
from ...infrastructure.persistence.images_repository import SQLiteImagesRepository
from ...infrastructure.persistence.path_handler import (
    get_ranked_root,
    compute_path_from_filename,
    sync_image_metadata_to_json,
    clear_folder_cache,
    prewarm_folder_cache,
)
from ...infrastructure.persistence.deduplicate_scored import deduplicate_scored
from ...infrastructure.persistence.cleanup_orphans import cleanup_orphans
from ...infrastructure.persistence.database import vacuum_database
from ...infrastructure.ml_models.model_loader import (
    model_loader as _model_loader,
    download_configured_models,
    set_hub_offline,
)
from ...infrastructure.ml_models.batch_sizer import BatchSizer
from ...infrastructure.cache.memory_cache import InMemoryCache
from ...infrastructure.ml_models.mediapipe_provider import MediaPipeProvider
from ...infrastructure.external_services.mediapipe_models import (
    download_mediapipe_models,
)

# Initialize core config before any core filesystem imports
if config["image_root"] == "":
    from folder_paths import get_output_directory
    config["image_root"] = get_output_directory()


@dataclass
class CLIDeps:
    """Dependency container handed to every CLI command function."""

    processor: ImageProcessor
    graph: CrystalGraph
    model_loader: ModelLoader
    batch_sizer_factory: BatchSizerFactory
    maps_provider: MapsProvider
    training_loader: Any
    model_trainer: Any
    cache: CacheProvider
    hpo_runner: HpoRunner
    plot_manager: Any
    mediapipe: Any
    vacuum_database: Any
    deduplicate_scored: Any
    cleanup_orphans: Any
    download_configured_models: Any
    download_mediapipe_models: Any
    set_hub_offline: Any


def build_cli_deps() -> CLIDeps:
    from ...infrastructure.loading.training_loader import training_loader
    from ...infrastructure.ml_models.training.model_trainer import model_trainer
    from ...infrastructure.loading.maps_loader import maps_list

    # Long-lived cache for analysis results and split data across build runs.
    _build_cache = InMemoryCache()
    _mediapipe = MediaPipeProvider()

    graph = CrystalGraph(
        image_repo=SQLiteImagesRepository(),
        comparison_repo=SQLiteComparisonsRepository(),
        cache=InMemoryCache(default_ttl=IMAGES_CACHE_TTL),
    )

    path_ops = PathOps(
        ranked_root=get_ranked_root,
        compute_path=compute_path_from_filename,
        sync_metadata=sync_image_metadata_to_json,
        clear_folder_cache=clear_folder_cache,
        prewarm_folder_cache=prewarm_folder_cache,
        deduplicate_scored=deduplicate_scored,
        cleanup_orphans=cleanup_orphans,
    )

    processor = ImageProcessor(
        max_workers=int(config["ranking"]["max_workers"]),
        graph=graph,
        path_ops=path_ops,
    )

    return CLIDeps(
        processor=processor,
        graph=graph,
        model_loader=_model_loader,
        batch_sizer_factory=BatchSizer,
        maps_provider=maps_list,
        training_loader=training_loader,
        model_trainer=model_trainer,
        cache=_build_cache,
        hpo_runner=HpoRunner(),
        plot_manager=PlotManager,
        mediapipe=_mediapipe,
        vacuum_database=vacuum_database,
        deduplicate_scored=deduplicate_scored,
        cleanup_orphans=cleanup_orphans,
        download_configured_models=download_configured_models,
        download_mediapipe_models=download_mediapipe_models,
        set_hub_offline=set_hub_offline,
    )
