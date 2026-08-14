"""Port interfaces for loading-related services.

These protocols describe the surface expected by domain and application
code so infrastructure implementations can be injected at adapter roots.
"""

from __future__ import annotations

from typing import Protocol, Iterable, Any, Sequence


class ModelLoader(Protocol):
    def load_model(self, name: str) -> Any: ...
    def list_models(self) -> Iterable[str]: ...


class BatchSizer(Protocol):
    def estimate_batch_size(self, item_shape: Sequence[int]) -> int: ...


class MapsProvider(Protocol):
    def get_map(self, name: str) -> Any: ...
    def list_maps(self) -> Iterable[str]: ...


class TrainingLoader(Protocol):
    def load_training_set(self, name: str) -> Iterable[Any]: ...
