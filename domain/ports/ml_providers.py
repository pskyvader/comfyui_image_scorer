"""Domain ports for ML runtime providers.

This module defines protocol interfaces for ML runtime providers used across
the domain layer. These protocols enable dependency injection and mocking
of ML dependencies without coupling domain code to concrete implementations.

Each protocol is designed to be implemented in the `infrastructure/` layer
and injected into domain code through the composition roots (`CLIDeps`,
`ServerDeps`).
"""

from typing import Protocol

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