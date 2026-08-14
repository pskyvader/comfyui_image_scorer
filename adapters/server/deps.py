"""Server dependency container - constructed by the adapters/server composition root."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import current_app

from ...application.services.graph_service import CrystalGraph
from ...application.services.image_processor import ImageProcessor, PathOps
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
    cleanup_orphans: Callable[..., int]
    deduplicate_scored: Callable[..., int]
