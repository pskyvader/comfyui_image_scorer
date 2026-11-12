"""Port interfaces for loading-related services.

Moved from ``domain/loading/ports.py``. These protocols describe the surface
expected by domain and application code so infrastructure implementations can be
injected at adapter roots. All types are concrete — no ``Any``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, KeysView, Protocol, NamedTuple

import numpy as np
import numpy.typing as npt
import torch
from PIL import Image

from .repository import ComparisonRow

if TYPE_CHECKING:
    from comfy.model_patcher import ModelPatcher


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
    """Trainer surface for building, fitting, and reading training results.

    Mirrors the full public surface of the injected trainer so domain and
    application code can read iteration diagnostics and per-metric directions
    while the trainer owns LightGBM internals.
    """

    METRIC_DIRECTIONS: dict[str, dict[str, bool]]

    eval_metrics: list[str]

    user_verbosity: int
    n_estimators: int | None
    test_size: float | None
    early_stopping_rounds: int | None
    callbacks: list[Callable[..., object]] | None
    plot_callback: object | None

    def r2_metric(
        self, y_true: npt.NDArray[np.float32], y_pred: npt.NDArray[np.float32]
    ) -> tuple[str, float, bool]: ...

    def create_training_model(self, config_dict: dict[str, object]) -> None: ...

    def create_callbacks(self, progress_bar: object) -> None: ...

    def create_metrics(
        self,
        y_test: npt.NDArray[np.float32],
        y_pred: npt.NDArray[np.float32],
        training_time: float,
    ) -> None: ...

    def train_model_pairs(
        self,
        config_dict: dict[str, object],
        X: npt.NDArray[np.float32],
        comparisons: list[dict[str, object]],
        index_list: list[str],
    ) -> tuple[object, dict[str, object]]: ...

    def train_model(
        self,
        config_dict: dict[str, object],
        X: npt.NDArray[np.float32],
        y: npt.NDArray[np.float32],
    ) -> tuple[object, dict[str, object]]: ...

    @property
    def training_model(self) -> FeatureFilterModel | None: ...

    @property
    def result_metrics(self) -> dict[str, object]: ...


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
    def load_vision_model_patcher(self, model_key: str) -> ModelPatcher: ...
    def load_attribute_model_patcher(
        self, model_key: str
    ) -> tuple[ModelPatcher, int, int]: ...


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
    def load_maps(self) -> dict[str, list[str]]: ...


class TrainingDiagnostics(NamedTuple):
    """Diagnostics returned by the training model loader."""
    final_score: float | None = None
    pairwise_accuracy: float | None = None
    score_calibration: dict[str, object] | None = None
    n_features: int | None = None
    rule_fingerprint: int | None = None


class TrainingLoader(Protocol):
    def load_vectors(self) -> dict[str, npt.NDArray[np.float32]]: ...
    def load_scores(self) -> dict[str, float]: ...
    def load_scores_array(self) -> npt.NDArray[np.float32]: ...
    def load_training_model(self) -> ScoringModel: ...
    def load_training_model_diagnostics(self) -> TrainingDiagnostics | None: ...
    def save_training_model(
        self, model: object, additional_data: dict[str, object] | None
    ) -> None: ...
    def load_comparison_rows(self) -> list[ComparisonRow]: ...
    def load_comparison_rule(
        self, threshold: int
    ) -> dict[str, tuple[float, int]] | None: ...
    def save_comparison_rule(
        self, threshold: int, rule: dict[str, tuple[float, int]]
    ) -> None: ...
    def load_feature_rule(self, n_features_in: int) -> npt.NDArray[np.intp] | None: ...
    def save_feature_rule(
        self, kept_indices: npt.NDArray[np.intp], n_features_in: int
    ) -> None: ...
    def load_interaction_rule(
        self, n_features_in: int
    ) -> npt.NDArray[np.intp] | None: ...
    def save_interaction_rule(
        self, interaction_indices: npt.NDArray[np.intp], n_features_in: int
    ) -> None: ...
    def feature_rule_digest(self) -> bytes | None: ...
    def interaction_rule_digest(self) -> bytes | None: ...