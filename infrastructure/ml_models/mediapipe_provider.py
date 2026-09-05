"""MediaPipe face/pose inference provider (implements domain MediaPipePort)."""

import os

import mediapipe as mp
import numpy as np
from numpy import typing as npt
from PIL import Image

from ...core.configuration.settings import config
from ...core.filesystem.paths import mediapipe_models_dir
from ...domain.analysis.mediapipe_analysis import POSE_LANDMARK_NAMES


class MediaPipeProvider:
    def __init__(self) -> None:
        self._face_detector: mp.tasks.vision.FaceDetector | None = None
        self._pose_landmarker: mp.tasks.vision.PoseLandmarker | None = None

    def _image_to_rgb(self, img: Image.Image) -> npt.NDArray[np.uint8]:
        return np.asarray(img.convert("RGB"))

    def _get_face_detector(self) -> mp.tasks.vision.FaceDetector:
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

    def _get_pose_landmarker(self) -> mp.tasks.vision.PoseLandmarker:
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

    def analyze(self, img: Image.Image) -> dict[str, list[dict[str, float]]]:
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
