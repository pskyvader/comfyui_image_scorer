"""Port interfaces for loading-related services.

Moved from ``domain/loading/ports.py``. These protocols describe the surface
expected by domain and application code so infrastructure implementations can be
injected at adapter roots. All types are concrete — no ``Any``.
"""

from __future__ import annotations

from typing import Callable, Protocol, NamedTuple


class _VisionModel(Protocol):
    """Abstract interface for vision model objects."""


class _Transform(Protocol):
    """Abstract interface for image transform pipelines."""


class _EmbeddingModel(Protocol):
    """Abstract interface for embedding model objects."""


class _ModelTrainer(Protocol):
    """Abstract interface for trained model objects."""


class VisionModelResult(NamedTuple):
    output_dim: int
    total_memory: int


class EmbeddingModelResult(NamedTuple):
    output_dim: int


class CategoryValue(NamedTuple):
    count: int
    value: int


class ModelLoader(Protocol):
    def load_vision_model(self, model_key: str) -> tuple[_VisionModel, int, int, _Transform]: ...
    def get_model_info(self, model_key: str) -> dict[str, object]: ...
    def load_embedding_model(self) -> tuple[_EmbeddingModel, int]: ...


class BatchSizer(Protocol):
    def get(
        self,
        width: int,
        height: int,
        rebuild: bool,
        bound: int | None,
    ) -> int: ...


BatchSizerFactory = Callable[[str], BatchSizer]


class MapsProvider(Protocol):
    def get_value(self, name: str, value: str) -> CategoryValue: ...
    def add_value(self, name: str, value: str) -> CategoryValue: ...
    def get_all_categories(self, name: str) -> list[str]: ...
    def register_value(self, name: str, value: object) -> None: ...


class TrainingLoader(Protocol):
    def load_vectors(self) -> dict[str, object]: ...
    def load_scores(self) -> dict[str, object]: ...
    def load_training_model(self) -> _ModelTrainer: ...
    def load_training_model_diagnostics(self) -> dict[str, object] | None: ...