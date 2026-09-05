"""Port interfaces for loading-related services.

These protocols describe the surface expected by domain and application
code so infrastructure implementations can be injected at adapter roots.
"""

from __future__ import annotations

from typing import Callable, Protocol

import numpy as np
from torch import nn
from torchvision.transforms import Compose


class ModelLoader(Protocol):
    def load_vision_model(self, model_key: str) -> tuple[nn.Module, int, int, Compose]: ...
    def get_model_info(self, model_key: str) -> dict[str, object]: ...
    def load_embedding_model(self) -> tuple[object, int]: ...


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
    def register_value(self, name: str, value: object) -> None: ...


class TrainingLoader(Protocol):
    def load_vectors(self) -> dict[str, np.ndarray]: ...
    def load_scores(self) -> dict[str, float]: ...
    def load_training_model(self) -> object: ...
    def load_training_model_diagnostics(self) -> dict[str, object] | None: ...
