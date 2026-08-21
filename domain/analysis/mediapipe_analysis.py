import os
from typing import Any

import numpy as np
from numpy import typing as npt
from PIL import Image

import mediapipe as mp

from ...core.configuration.settings import config
from ...core.filesystem.paths import mediapipe_models_dir

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
    """Detects faces and body pose using MediaPipe.

    Output (all human-readable):
      - ``bbox``: list of face boxes, each
        ``{"x", "y", "width", "height", "confidence"}`` (relative coords)
      - one key per pose landmark (33) in ``POSE_LANDMARK_NAMES``; each value is
        a list (one per detected person) of
        ``{"x", "y", "z", "visibility"}`` (relative coords)
    """

    def __init__(self) -> None:
        self._face_detector: Any = None
        self._pose_landmarker: Any = None

    def _image_to_rgb(self, img: Image.Image) -> npt.NDArray[np.uint8]:
        return np.asarray(img.convert("RGB"))

    def _get_face_detector(self) -> Any:
        if self._face_detector is None:
            model_path = os.path.join(
                mediapipe_models_dir,
                config["prepare"]["attribute_models"]["face_detection"]["name"],
            )
            if not os.path.exists(model_path):
                raise FileNotFoundError(
                    f"MediaPipe face detector model not found: {model_path}. "
                    "Run 'comfyui-scorer files download models' first."
                )
            options = mp.tasks.vision.FaceDetectorOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                min_detection_confidence=0.5,
            )
            self._face_detector = mp.tasks.vision.FaceDetector.create_from_options(options)
        return self._face_detector

    def _get_pose_landmarker(self) -> Any:
        if self._pose_landmarker is None:
            model_path = os.path.join(
                mediapipe_models_dir,
                config["prepare"]["attribute_models"]["pose_landmarker"]["name"],
            )
            if not os.path.exists(model_path):
                raise FileNotFoundError(
                    f"MediaPipe pose landmarker model not found: {model_path}. "
                    "Run 'comfyui-scorer files download models' first."
                )
            options = mp.tasks.vision.PoseLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                min_pose_detection_confidence=0.5,
            )
            self._pose_landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)
        return self._pose_landmarker

    def analyze(self, img: Image.Image) -> dict[str, Any]:
        rgb = self._image_to_rgb(img)
        height, width = rgb.shape[0], rgb.shape[1]
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        face_detector = self._get_face_detector()
        face_result = face_detector.detect(mp_image)

        faces: list[dict[str, float]] = []
        if face_result.detections:
            for detection in face_result.detections:
                bbox = detection.bounding_box
                x = bbox.origin_x / width
                y = bbox.origin_y / height
                w = bbox.width / width
                h = bbox.height / height
                conf = detection.categories[0].score
                faces.append(
                    {
                        "x": x,
                        "y": y,
                        "width": w,
                        "height": h,
                        "confidence": conf,
                    }
                )

        pose_landmarker = self._get_pose_landmarker()
        pose_result = pose_landmarker.detect(mp_image)

        keypoints: dict[str, list[dict[str, float]]] = {
            name: [] for name in POSE_LANDMARK_NAMES
        }
        if pose_result.pose_landmarks:
            for landmarks in pose_result.pose_landmarks:
                for j, lm in enumerate(landmarks):
                    keypoints[POSE_LANDMARK_NAMES[j]].append(
                        {
                            "x": lm.x,
                            "y": lm.y,
                            "z": lm.z,
                            "visibility": lm.visibility,
                        }
                    )

        return {"bbox": faces, **keypoints}
