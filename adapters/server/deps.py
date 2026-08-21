"""Server dependency container - constructed by the adapters/server composition root."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import current_app

from ...application.services.graph_service import CrystalGraph
from ...application.services.image_processor import ImageProcessor, PathOps
from ..cli.deps import CLIDeps
from ...domain.database.ports import (
    ComparisonRepository,
    ImageRepository,
    PathResolver,
)
from ...domain.loading import BatchSizerFactory, MapsProvider, ModelLoader, TrainingLoader


def get_server_deps() -> ServerDeps:
    return current_app.extensions["server_deps"]


@dataclass
class ServerDeps:
    image_repo: ImageRepository
    comparison_repo: ComparisonRepository
    path_resolver: PathResolver
    path_ops: PathOps
    graph: CrystalGraph
    processor: ImageProcessor
    model_loader: ModelLoader
    batch_sizer_factory: BatchSizerFactory
    maps_provider: MapsProvider
    training_loader: TrainingLoader
    model_trainer: Any
    vacuum_database: Callable[..., Any]
    deduplicate_scored: Callable[..., int]
    cleanup_orphans: Callable[..., int]
    download_configured_models: Callable[..., Any]
    download_mediapipe_models: Callable[..., Any]

    def to_cli_deps(self) -> CLIDeps:
        return CLIDeps(
            image_repo=self.image_repo,
            comparison_repo=self.comparison_repo,
            processor=self.processor,
            model_loader=self.model_loader,
            batch_sizer_factory=self.batch_sizer_factory,
            maps_provider=self.maps_provider,
            training_loader=self.training_loader,
            model_trainer=self.model_trainer,
            vacuum_database=self.vacuum_database,
            deduplicate_scored=self.deduplicate_scored,
            cleanup_orphans=self.cleanup_orphans,
            download_configured_models=self.download_configured_models,
            download_mediapipe_models=self.download_mediapipe_models,
        )