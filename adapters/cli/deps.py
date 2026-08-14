"""CLI composition root - builds injected dependencies for the CLI commands."""

from dataclasses import dataclass
from typing import Any

from ...core.configuration.settings import config
from ...domain.loading.ports import BatchSizerFactory, MapsProvider, ModelLoader
from ...infrastructure.persistence.comparisons_repository import (
    SQLiteComparisonsRepository,
)
from ...infrastructure.persistence.images_repository import SQLiteImagesRepository
from ...application.services.graph_service import CrystalGraph
from ...application.services.image_processor import ImageProcessor, PathOps
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
)
from ...infrastructure.ml_models.batch_sizer import BatchSizer
from ...infrastructure.external_services.mediapipe_models import (
    download_mediapipe_models,
)

# Initialize core config before any core filesystem imports
if config["image_root"] == "":
    from folder_paths import get_output_directory
    config["image_root"] = get_output_directory()


@dataclass
class CLIDeps:
    image_repo: Any
    comparison_repo: Any
    processor: ImageProcessor
    model_loader: ModelLoader
    batch_sizer_factory: BatchSizerFactory
    maps_provider: MapsProvider
    training_loader: Any
    model_trainer: Any
    vacuum_database: Any
    deduplicate_scored: Any
    cleanup_orphans: Any
    download_configured_models: Any
    download_mediapipe_models: Any


def build_cli_deps() -> CLIDeps:
    from ...infrastructure.loading.training_loader import training_loader
    from ...infrastructure.ml_models.training.model_trainer import model_trainer
    from ...infrastructure.loading.maps_loader import maps_list

    image_repo = SQLiteImagesRepository()
    comparison_repo = SQLiteComparisonsRepository()
    graph = CrystalGraph(image_repo=image_repo, comparison_repo=comparison_repo)

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
        image_repo=image_repo,
        comparison_repo=comparison_repo,
        graph=graph,
        path_ops=path_ops,
    )

    return CLIDeps(
        image_repo=image_repo,
        comparison_repo=comparison_repo,
        processor=processor,
        model_loader=_model_loader,
        batch_sizer_factory=BatchSizer,
        maps_provider=maps_list,
        training_loader=training_loader,
        model_trainer=model_trainer,
        vacuum_database=vacuum_database,
        deduplicate_scored=deduplicate_scored,
        cleanup_orphans=cleanup_orphans,
        download_configured_models=download_configured_models,
        download_mediapipe_models=download_mediapipe_models,
    )
