"""CLI composition root - builds injected dependencies for the CLI commands."""

from dataclasses import dataclass

from ...core.configuration.settings import config
from ...domain.ports.loading import (
    BatchSizerFactory,
    MapsProvider,
    ModelLoader,
    TrainingLoader,
)
from ...domain.ports.cache import CacheProvider
from ...domain.comparison.constants import IMAGES_CACHE_TTL
from ...application.services.graph_service import CrystalGraph
from ...application.hyperparameters.hyperparameter_optimizer import HpoRunner
from ...infrastructure.ml_models.plot import PlotManager
from ...application.services.image_processor import ImageProcessor
from ...infrastructure.persistence.comparisons_repository import (
    SQLiteComparisonsRepository,
)
from ...infrastructure.persistence.images_repository import SQLiteImagesRepository
from ...infrastructure.persistence.deduplicate_scored import deduplicate_scored
from ...infrastructure.persistence.cleanup_orphans import cleanup_orphans
from ...infrastructure.persistence.file_manager import FileManager
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
from ...infrastructure.ml_models.training.model_trainer import ModelTrainer
from ...infrastructure.loading.training_loader import training_loader
from ...infrastructure.loading.maps_loader import maps_list
from ...domain.ports.ml_providers import MediaPipePort

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
    training_loader: TrainingLoader
    model_trainer: ModelTrainer
    cache: CacheProvider
    hpo_runner: HpoRunner
    plot_manager: type[PlotManager]
    mediapipe: MediaPipePort
    vacuum_database: callable
    deduplicate_scored: callable
    cleanup_orphans: callable
    download_configured_models: callable
    download_mediapipe_models: callable
    set_hub_offline: callable


def build_cli_deps() -> CLIDeps:
    # Long-lived cache for analysis results and split data across build runs.
    _build_cache = InMemoryCache()
    _mediapipe = MediaPipeProvider()

    graph = CrystalGraph(
        image_repo=SQLiteImagesRepository(),
        comparison_repo=SQLiteComparisonsRepository(),
        cache=InMemoryCache(default_ttl=IMAGES_CACHE_TTL),
        file_port=FileManager(),
    )

    path_ops = FileManager()

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
        model_trainer=ModelTrainer(),
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
