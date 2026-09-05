"""Domain ports for ML runtime providers.

This module defines protocol interfaces for ML runtime providers used across
the domain layer. These protocols enable dependency injection and mocking
of ML dependencies without coupling domain code to concrete implementations.

Each protocol is designed to be implemented in the `infrastructure/` layer
and injected into domain code through the composition roots (`CLIDeps`,
`ServerDeps`).
"""

from typing import Protocol

import numpy as np
from PIL import Image


class MediaPipePort(Protocol):
    """Face detection and pose landmark inference over RGB arrays.

    Output (all human-readable):
      - ``bbox``: list of face boxes, each
        ``{"x", "y", "width", "height", "confidence"}`` (relative coords)
      - one key per pose landmark (33) in ``POSE_LANDMARK_NAMES``; each value is
        a list (one per detected person) of
        ``{"x", "y", "z", "visibility"}`` (relative coords)
    """

    def analyze(self, img: Image.Image) -> dict[str, list[dict[str, float]]]: ...


class VisionEncodingPort(Protocol):
    """Tensor preparation for vision models.

    Responsible for converting raw image inputs (PIL.Image, numpy, torch.Tensor)
    into a format suitable for vision model encoding (e.g. resizing, normalization,
    conversion to torch.Tensor on the correct device).

    This protocol is injected through CLIDeps/ServerDeps and implemented in
    infrastructure/ml_models/ with the actual tensor preparation logic.
    """

    def encode(self, img: Image.Image | np.ndarray) -> np.ndarray: ...


class FeatureEnginePort(Protocol):
    """LightGBM / scikit-learn feature engineering and ranking.

    Responsible for generating interaction features (polynomial features,
    pairwise products) and training LightGBM models for feature importance
    ranking and Lambdarank-style scoring.

    This protocol is injected through CLIDeps/ServerDeps and implemented in
    infrastructure/ml_models/ with the actual LightGBM training logic.
    """

    def fit_ranking(self, X: np.ndarray, y: np.ndarray) -> object: ...
    def transform(self, X: np.ndarray) -> np.ndarray: ...