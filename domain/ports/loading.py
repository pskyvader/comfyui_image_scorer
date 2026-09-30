"""Port interfaces for loading-related services.

Moved from ``domain/loading/ports.py``. These protocols describe the surface
expected by domain and application code so infrastructure implementations can be
injected at adapter roots. All types are concrete — no ``Any``.
"""

from __future__ import annotations

from typing import Callable, KeysView, Protocol, NamedTuple

import numpy as np
import numpy.typing as npt
import torch
from PIL import Image

from .repository import ComparisonRow


class ModelInfo(NamedTuple):
    variable_input: bool
    input_size: tuple[int, int]


class VisionModel(Protocol):
    """Vision model surface. The implementation owns device placement."""

    def __call__(self, x: torch.Tensor) -> torch.Tensor: ...

    @property
    def device(self) -> torch.device: ...


class Transform(Protocol):
    """Image transform pipeline that turns a PIL image into a batch tensor."""

    def __call__(self, image: Image.Image) -> torch.Tensor: ...


class BatchTensors(Protocol):
    """Batched model inputs with device placement and keyword expansion."""

    def to(self, device: torch.device) -> BatchTensors: ...
    def keys(self) -> KeysView[str]: ...
    def __getitem__(self, key: str) -> torch.Tensor: ...


class ImageProcessor(Protocol):
    """Feature extractor that turns images into a batched tensor mapping."""

    def __call__(
        self, *, images: list[Image.Image], return_tensors: str
    ) -> BatchTensors: ...


class EmbeddingModel(Protocol):
    """Embedding model surface. The implementation owns device placement."""

    def encode(self, sentences: list[str]) -> npt.NDArray[np.float32]: ...


class AttributeOutput(Protocol):
    """Attribute model output: a per-head mapping, or ``.logits`` for the NSFW head."""

    def __getitem__(self, key: str) -> torch.Tensor: ...

    @property
    def logits(self) -> torch.Tensor: ...


class AttributeModel(Protocol):
    """Attribute model surface. The implementation owns device placement."""

    def __call__(self, **kwargs: torch.Tensor) -> AttributeOutput: ...

    @property
    def device(self) -> torch.device: ...


class ScoringModel(Protocol):
    """Surface the scoring path needs from a loaded training model.

    ``predict_proba`` only exists on classifier models, so the scoring path
    keeps an ``hasattr`` guard before calling it.
    """

    def get_params(self) -> dict[str, object]: ...
    def predict(self, X: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]: ...
    def predict_proba(self, X: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]: ...


class FeatureFilterModel(Protocol):
    """Surface the feature-importance pass needs from a freshly built model."""

    def fit(
        self,
        X: npt.NDArray[np.float32],
        y: npt.NDArray[np.float32],
        *,
        callbacks: list[Callable[..., None]] | None = None,
    ) -> object: ...

    @property
    def feature_importances_(self) -> npt.NDArray[np.float32]: ...


class ModelTrainingService(Protocol):
    """Trainer surface the feature transformer needs to build and fit a model."""

    def create_training_model(self, config_dict: dict[str, object]) -> None: ...

    @property
    def training_model(self) -> FeatureFilterModel | None: ...


class VisionModelResult(NamedTuple):
    output_dim: int
    total_memory: int


class EmbeddingModelResult(NamedTuple):
    output_dim: int


class CategoryValue(NamedTuple):
    c: int
    value: int


class ModelLoader(Protocol):
    def load_vision_model(self, model_key: str) -> tuple[VisionModel, int, int, Transform]: ...
    def get_model_info(self, model_key: str) -> ModelInfo: ...
    def load_embedding_model(self) -> tuple[EmbeddingModel, int]: ...
    def load_hf_vision_model(
        self, model_key: str
    ) -> tuple[AttributeModel, int, ImageProcessor]: ...


class BatchSizer(Protocol):
    def get(
        self,
        width: int,
        height: int,
        rebuild: bool,
        bound: int | None = None,
    ) -> int: ...


class BatchSizerFactory(Protocol):
    """Builds a batch sizer for one model.

    ``section`` selects which prepare_config map the model is configured in, so
    attribute models can be calibrated separately from vision models.
    """

    def __call__(
        self, model_key: str, section: str = ...
    ) -> BatchSizer: ...


class MapsProvider(Protocol):
    def get_value(self, name: str, value: str) -> CategoryValue: ...
    def add_value(self, name: str, value: str) -> CategoryValue: ...
    def get_all_categories(self, name: str) -> list[str]: ...
    def register_value(self, name: str, value: object) -> None: ...


class TrainingDiagnostics(NamedTuple):
    """Diagnostics returned by the training model loader."""
    final_score: float | None = None
    pairwise_accuracy: float | None = None
    score_calibration: dict[str, object] | None = None


class TrainingLoader(Protocol):
    def load_vectors(self) -> dict[str, npt.NDArray[np.float32]]: ...
    def load_scores(self) -> dict[str, float]: ...
    def load_training_model(self) -> ScoringModel: ...
    def load_training_model_diagnostics(self) -> TrainingDiagnostics | None: ...
    def load_comparison_rows(self) -> list[ComparisonRow]: ...
    def load_comparison_rule(
        self, threshold: int
    ) -> dict[str, tuple[float, int]] | None: ...
    def save_comparison_rule(
        self, threshold: int, rule: dict[str, tuple[float, int]]
    ) -> None: ...
    def load_feature_rule(self) -> npt.NDArray[np.intp] | None: ...
    def save_feature_rule(self, kept_indices: npt.NDArray[np.intp]) -> None: ...
    def load_interaction_data(
        self,
    ) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.intp]] | None: ...
    def save_interaction_data(
        self, x: npt.NDArray[np.float32], top_k_indices_local: npt.NDArray[np.intp]
    ) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.intp]]: ...