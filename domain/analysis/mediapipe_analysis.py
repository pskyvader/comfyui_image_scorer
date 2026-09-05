"""Pose landmark naming and face/pose analysis via the injected MediaPipePort."""

from PIL import Image

from ..ports.ml_providers import MediaPipePort

# MediaPipe Pose landmark names, in model output order (0..32).
POSE_LANDMARK_NAMES = (
    "nose",
    "left_eye_inner",
    "left_eye",
    "left_eye_outer",
    "right_eye_inner",
    "right_eye",
    "right_eye_outer",
    "left_ear",
    "right_ear",
    "mouth_left",
    "mouth_right",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_pinky",
    "right_pinky",
    "left_index",
    "right_index",
    "left_thumb",
    "right_thumb",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
)


class MediaPipeAnalyzer:
    """Detects faces and body pose through the injected MediaPipe provider."""

    def __init__(self, mediapipe: MediaPipePort) -> None:
        self._mediapipe = mediapipe

    def analyze(self, img: Image.Image) -> dict[str, list[dict[str, float]]]:
        return self._mediapipe.analyze(img)
