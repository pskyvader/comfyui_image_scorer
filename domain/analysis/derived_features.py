"""Scalar features derived from the stored per-image analysis.

The build stores one cell per measurement: seven metric floats, a list of face
boxes, 33 landmark lists, and one probability map per person attribute. Those
are the right shapes for the vector columns, but they read badly as analysis
input, so this module reduces each of them to the handful of scalars a chart
needs: landmark geometry, face framing, attribute dominance, and detection
presence. Everything here is pure, so the same numbers come out of a sidecar, a
text_data row, or a test fixture.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import hypot, isclose
import re

from ...core.configuration.settings import config
from .mediapipe_analysis import POSE_LANDMARK_NAMES
from ..vectors.terms import ExtractionResult, implicit_parentheses_multiplier

CONNECTOR_TOKENS: tuple[str, ...] = ("and", "or", "but", "not")
_CONNECTOR_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:" + "|".join(CONNECTOR_TOKENS) + r")\b", re.IGNORECASE
)


def _is_hand_weighted(weight: float) -> bool:
    """Whether a term weight came from the prompt rather than from nesting.

    `extract_terms` multiplies every implicit group by the
    ``implicit_parentheses_multiplier`` vector setting, so nested groups
    produce 1.1, 1.21, 1.331 and so on. A weight outside that sequence was
    written by hand as ``term:1.2``.
    """
    multiplier = implicit_parentheses_multiplier()
    level = 0
    candidate = 1.0
    while candidate <= weight + 1e-9:
        if isclose(candidate, weight, rel_tol=1e-6):
            return False
        level += 1
        candidate = multiplier**level
    return True

LandmarkPoints = Sequence[Mapping[str, float]]
LandmarkTable = Mapping[str, LandmarkPoints]

HAND_LANDMARKS: dict[str, tuple[str, ...]] = {
    "left_hand": ("left_wrist", "left_index", "left_thumb"),
    "right_hand": ("right_wrist", "right_index", "right_thumb"),
}


def _point(landmarks: LandmarkTable, name: str) -> tuple[float, float] | None:
    """The first visible-enough landmark position, in the analyzer's own units."""
    for entry in landmarks.get(name, ()):
        x = entry.get("x")
        y = entry.get("y")
        if x is None or y is None:
            continue
        return float(x), float(y)
    return None


def _distance(
    landmarks: LandmarkTable, first: str, second: str
) -> float:
    start = _point(landmarks, first)
    end = _point(landmarks, second)
    if start is None or end is None:
        return 0.0
    return hypot(start[0] - end[0], start[1] - end[1])


def _midpoint(
    landmarks: LandmarkTable, first: str, second: str
) -> tuple[float, float] | None:
    start = _point(landmarks, first)
    end = _point(landmarks, second)
    if start is None or end is None:
        return None
    return (start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0


def mean_visibility(landmarks: LandmarkTable, names: Sequence[str]) -> float:
    """Mean visibility over the named landmarks, ignoring the ones not detected."""
    values = [
        float(entry["visibility"])
        for name in names
        for entry in landmarks.get(name, ())
        if "visibility" in entry
    ]
    if not values:
        return 0.0
    return sum(values) / len(values)


def presence(landmarks: LandmarkTable) -> dict[str, bool]:
    """Whether a pose, a left hand and a right hand were actually detected.

    Presence is a visibility question rather than an existence question:
    MediaPipe reports landmarks it only guessed at, and counting those as
    detections would put every image in the "pose" group. `plot_detection_presence`
    compares the scores of the images on both sides of each split.
    """
    threshold = float(config["training"]["analysis_pose_visibility_threshold"])
    return {
        "pose": mean_visibility(landmarks, POSE_LANDMARK_NAMES) > threshold,
        "left_hand": mean_visibility(landmarks, HAND_LANDMARKS["left_hand"])
        > threshold,
        "right_hand": mean_visibility(landmarks, HAND_LANDMARKS["right_hand"])
        > threshold,
    }


def pose_geometry(landmarks: LandmarkTable) -> dict[str, float]:
    """Framing scalars from the 33 landmarks.

    Lengths are in the units MediaPipe reports, which are image fractions for
    x and y but can exceed 1.0 when a body extends past the frame, so nothing
    here clamps to the image box.
    """
    shoulder_mid = _midpoint(landmarks, "left_shoulder", "right_shoulder")
    hip_mid = _midpoint(landmarks, "left_hip", "right_hip")
    ankle_mid = _midpoint(landmarks, "left_ankle", "right_ankle")
    head_mid = _midpoint(landmarks, "left_eye_outer", "right_eye_outer")

    torso = (
        hypot(shoulder_mid[0] - hip_mid[0], shoulder_mid[1] - hip_mid[1])
        if shoulder_mid and hip_mid
        else 0.0
    )
    legs = (
        hypot(hip_mid[0] - ankle_mid[0], hip_mid[1] - ankle_mid[1])
        if hip_mid and ankle_mid
        else 0.0
    )
    left_shoulder = _point(landmarks, "left_shoulder")
    right_shoulder = _point(landmarks, "right_shoulder")
    asymmetry = (
        abs(left_shoulder[0] - (1.0 - right_shoulder[0]))
        if left_shoulder and right_shoulder
        else 0.0
    )

    detected = sum(
        1
        for name in POSE_LANDMARK_NAMES
        if mean_visibility(landmarks, (name,)) > 0.0
    )

    return {
        "head_width": _distance(landmarks, "left_eye_outer", "right_eye_outer"),
        "shoulder_width": _distance(landmarks, "left_shoulder", "right_shoulder"),
        "hip_width": _distance(landmarks, "left_hip", "right_hip"),
        "torso_length": torso,
        "leg_length": legs,
        "head_x": head_mid[0] if head_mid else 0.0,
        "head_y": head_mid[1] if head_mid else 0.0,
        "shoulder_x": shoulder_mid[0] if shoulder_mid else 0.0,
        "hip_y": hip_mid[1] if hip_mid else 0.0,
        "lateral_asymmetry": asymmetry,
        "landmarks_detected": float(detected),
    }


def face_geometry(boxes: Sequence[Mapping[str, float]]) -> dict[str, float]:
    """Face count, framing and detector confidence from the bbox cells."""
    count = len(boxes)
    if count == 0:
        return {
            "face_count": 0.0,
            "face_area_mean": 0.0,
            "face_area_max": 0.0,
            "face_x": 0.0,
            "face_y": 0.0,
            "face_confidence": 0.0,
        }

    areas = [float(box.get("width", 0.0)) * float(box.get("height", 0.0)) for box in boxes]
    centre_x = [float(box.get("x", 0.0)) + float(box.get("width", 0.0)) / 2.0 for box in boxes]
    centre_y = [float(box.get("y", 0.0)) + float(box.get("height", 0.0)) / 2.0 for box in boxes]
    confidence = [float(box.get("confidence", 0.0)) for box in boxes]

    return {
        "face_count": float(count),
        "face_area_mean": sum(areas) / count,
        "face_area_max": max(areas),
        "face_x": sum(centre_x) / count,
        "face_y": sum(centre_y) / count,
        "face_confidence": sum(confidence) / count,
    }


def dominant_category(
    distribution: Sequence[Mapping[str, float]],
) -> tuple[str, float]:
    """The most probable label and its probability, or ``("", 0.0)`` when empty."""
    best_label = ""
    best_value = 0.0
    for entry in distribution:
        for label, value in entry.items():
            if float(value) > best_value:
                best_label = str(label)
                best_value = float(value)
    return best_label, best_value


def _max_paren_depth(text: str) -> int:
    depth = 0
    deepest = 0
    for character in text:
        if character == "(":
            depth += 1
            deepest = max(deepest, depth)
        elif character == ")":
            depth = max(0, depth - 1)
    return deepest


def prompt_features(text: str, extraction: ExtractionResult) -> dict[str, float]:
    """Structure of one prompt: size, weighting, nesting and ordering.

    The term weights come from `extract_terms`, which multiplies them through
    nested parentheses and marks an implicit group with the
    ``implicit_parentheses_multiplier`` vector setting, so a term weighted
    anything other than 1.0 or that sequence root was weighted by hand.
    """
    terms = extraction.terms
    term_count = len(terms)
    weights = [float(weight) for _term, weight, _index in terms]
    positions = [index for _term, _weight, index in terms]

    # Counted over the whole prompt rather than over the extracted terms,
    # because a connector glued to its neighbour ("and eyes") survives as one
    # term and would otherwise never be seen.
    connector_count = len(_CONNECTOR_PATTERN.findall(text))
    weighted_share = (
        sum(1 for weight in weights if _is_hand_weighted(weight)) / term_count
        if term_count
        else 0.0
    )

    return {
        "prompt_chars": float(len(text)),
        "prompt_terms": float(term_count),
        "prompt_terms_per_100_chars": term_count / len(text) * 100.0 if text else 0.0,
        "prompt_mean_weight": sum(weights) / term_count if term_count else 0.0,
        "prompt_max_weight": max(weights) if weights else 0.0,
        "prompt_weighted_share": weighted_share,
        "prompt_max_depth": float(_max_paren_depth(text)),
        "prompt_connectors": float(connector_count),
        "prompt_duplicates": float(len(extraction.duplicates)),
        "prompt_mean_position": (
            sum(positions) / term_count / term_count if term_count else 0.0
        ),
    }
