"""Per-image analysis features read from the text sidecar.

`text_data.jsonl` holds one cell per measurement and every cell is stringified
by the writer, so this module is the boundary that decodes a row into the flat
numbers a correlation chart can use. It reads scores from the caller rather than
the database: the caller replays the comparison file and owns the target, and
this only decides which rows are in scope.

The charts split images into groups, so the table also carries the face,
landmark and detection-presence rows those plots need, instead of making the
notebook reshape them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...core.filesystem.paths import text_data_file
from ...core.io.serialization import load_single_jsonl
from ...core.observability.logger import ModuleLogger, get_logger
from ...domain.analysis.derived_features import (
    dominant_category,
    face_geometry,
    pose_geometry,
    presence,
)
from ...domain.analysis.mediapipe_analysis import POSE_LANDMARK_NAMES
from .row_fields import as_number, as_object_list, as_weight_map, strongest

logger: ModuleLogger = get_logger(__name__)

SCALAR_COLUMNS: tuple[str, ...] = (
    "cfg",
    "steps",
    "clip_skip",
    "final_width",
    "final_height",
    "final_aspect_ratio",
    "nsfw_score",
    "denoise",
)
CATEGORY_COLUMNS: tuple[str, ...] = ("model", "sampler", "scheduler", "lora")
METRIC_COLUMN: str = "analysis"
ATTRIBUTE_COLUMNS: tuple[str, ...] = ("age", "gender", "race")
FACE_COLUMN: str = "bbox"
REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        *SCALAR_COLUMNS,
        *CATEGORY_COLUMNS,
        *ATTRIBUTE_COLUMNS,
        *POSE_LANDMARK_NAMES,
        METRIC_COLUMN,
        FACE_COLUMN,
    }
)
PERSON_ATTRIBUTES: tuple[str, ...] = ("age", "gender", "race")


@dataclass
class FeatureTable:
    """Flat per-image features plus the grouped rows the charts plot."""

    records: list[dict[str, object]] = field(default_factory=list[dict[str, object]])
    faces: list[dict[str, float]] = field(default_factory=list[dict[str, float]])
    # One row per detected landmark, carrying the landmark's name alongside its
    # position and the image's score.
    landmarks: list[dict[str, object]] = field(default_factory=list[dict[str, object]])
    presence_scores: dict[str, tuple[list[float], list[float]]] = field(
        default_factory=dict[str, tuple[list[float], list[float]]]
    )


def _presence_pairs() -> dict[str, tuple[list[float], list[float]]]:
    return {
        name: ([], []) for name in ("pose", "left_hand", "right_hand", "face")
    }


def _metric_values(cell: object) -> dict[str, float]:
    # The analysis cell is a flat dict of floats, which is exactly the shape
    # as_weight_map decodes from either the real object or its repr string.
    metrics = as_weight_map(cell)
    return {name: float(value) for name, value in metrics.items()}


def _landmark_table(payload: dict[str, object]) -> dict[str, list[dict[str, Any]]]:
    return {name: as_object_list(payload.get(name)) for name in POSE_LANDMARK_NAMES}


def _attribute_labels(
    payload: dict[str, object]
) -> tuple[dict[str, str], dict[str, float]]:
    labels: dict[str, str] = {}
    confidences: dict[str, float] = {}
    for name in PERSON_ATTRIBUTES:
        people = as_object_list(payload.get(name))
        # One row per detected person; the analysis compares the first, which is
        # the most prominent face in the frame.
        label, confidence = dominant_category(people[:1])
        labels[name] = label
        confidences[name] = confidence
    return labels, confidences


def _require_columns(payload: dict[str, object], filename: str) -> None:
    missing = sorted(REQUIRED_COLUMNS - payload.keys())
    if missing:
        raise ValueError(
            f"text_data row {filename} is missing required columns: "
            f"{', '.join(missing)}"
        )


def feature_rows(scored: dict[str, float]) -> FeatureTable:
    """Build the feature table for every text_data row that carries a score.

    Raises when a row is missing a column this analysis depends on, rather than
    plotting a partial feature set that looks like a real result.
    """
    if not scored:
        raise ValueError("no scores supplied; nothing to correlate against")

    table = FeatureTable()
    table.presence_scores = _presence_pairs()
    analyzed = 0

    for row in load_single_jsonl(text_data_file):
        filename, payload = next(iter(row.items()))
        name = str(filename)
        if name not in scored:
            continue
        _require_columns(payload, name)

        score = float(scored[name])
        landmarks = _landmark_table(payload)
        detected = presence(landmarks)
        boxes = as_object_list(payload.get(FACE_COLUMN))
        faces = face_geometry(boxes)
        framing = pose_geometry(landmarks)
        labels, confidences = _attribute_labels(payload)

        record: dict[str, object] = {"filename": name, "score": score}
        for column in SCALAR_COLUMNS:
            record[column] = as_number(payload.get(column))
        for column in CATEGORY_COLUMNS:
            # strongest is the module's own one-hot reader: the highest-weighted
            # key, or an empty name when the column carried no map.
            record[column] = strongest(as_weight_map(payload.get(column)))[0]
        record.update(_metric_values(payload.get(METRIC_COLUMN)))
        record.update(faces)
        record.update(framing)
        for column in PERSON_ATTRIBUTES:
            record[f"{column}_label"] = labels[column]
            record[f"{column}_confidence"] = confidences[column]
        record["face_present"] = faces["face_count"] > 0.0
        for key, detected_flag in detected.items():
            record[f"{key}_present"] = detected_flag
        table.records.append(record)

        for box in boxes:
            table.faces.append(
                {
                    "x": float(box.get("x", 0.0)),
                    "y": float(box.get("y", 0.0)),
                    "w": float(box.get("width", 0.0)),
                    "h": float(box.get("height", 0.0)),
                    "conf": float(box.get("confidence", 0.0)),
                    "score": score,
                }
            )

        for landmark_name, points in landmarks.items():
            for point in points:
                table.landmarks.append(
                    {
                        "x": float(point.get("x", 0.0)),
                        "y": float(point.get("y", 0.0)),
                        "score": score,
                        # Added under the chart's own key rather than mixed
                        # into the numeric columns the frame shares with faces.
                        "landmark": landmark_name,
                    }
                )

        groups = dict(detected)
        groups["face"] = bool(record["face_present"])
        for key, is_detected in groups.items():
            present, absent = table.presence_scores[key]
            (present if is_detected else absent).append(score)

        analyzed += 1

    logger.info(
        "feature rows: %d analyzed, %d scored images total", analyzed, len(scored)
    )
    logger.info(
        "presence split sizes: %s",
        {name: (len(present), len(absent)) for name, (present, absent) in table.presence_scores.items()},
    )
    return table
