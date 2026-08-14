"""Port interfaces for loading-related services.

These protocols describe the surface expected by domain and application
code so infrastructure implementations can be injected at adapter roots.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

import numpy as np


class ModelLoader(Protocol):
    def load_vision_model(self, model_key: str) -> tuple[Any, int, int, Any]: ...
    def get_model_info(self, model_key: str) -> dict[str, Any]: ...
    def load_embedding_model(self) -> tuple[Any, int]: ...


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
    def get_value(self, name: str, value: str) -> tuple[int, int]: ...
    def add_value(self, name: str, value: str) -> tuple[int, int]: ...
    def get_all_categories(self, name: str) -> list[str]: ...
    def register_value(self, name: str, value: Any) -> None: ...


class TrainingLoader(Protocol):
    def load_vectors(self) -> dict[str, np.ndarray]: ...
    def load_scores(self) -> dict[str, float]: ...
    def load_training_model(self) -> Any: ...
    def load_training_model_diagnostics(self) -> dict[str, Any] | None: ...
