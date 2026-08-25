"""Domain ports for ML runtime providers."""

from typing import Any, Protocol

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

    def analyze(self, img: Image.Image) -> dict[str, Any]: ...
