from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from .. import feature_rows as feature_rows_module
from ..feature_rows import REQUIRED_COLUMNS, FeatureTable, feature_rows
from ....domain.analysis.mediapipe_analysis import POSE_LANDMARK_NAMES


def _landmark(x: float = 0.5, y: float = 0.5, visibility: float = 0.9) -> dict[str, float]:
    return {"x": x, "y": y, "z": 0.0, "visibility": visibility}


def _payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "cfg": "7.5",
        "steps": "25",
        "clip_skip": "-2",
        "final_width": "512",
        "final_height": "768",
        "final_aspect_ratio": "0.6667",
        "nsfw_score": "0.01",
        "denoise": "0.8",
        "model": "{'cyberrealistic_v90': 1.0}",
        "sampler": "{'euler_ancestral': 1.0}",
        "scheduler": "{'simple': 1.0}",
        "lora": "{}",
        "analysis": (
            "{'contrast': 0.4, 'sharpness': 0.2, 'noise_score': 0.1, "
            "'colorfulness': 0.3, 'artifact_score': 0.05, 'edge_density': 0.02, "
            "'texture_lbp': 0.9}"
        ),
        "age": "[{'0-2': 0.0, '20-29': 0.8}]",
        "gender": "[{'Female': 0.7, 'Male': 0.3}]",
        "race": "[{'White': 0.6, 'Black': 0.4}]",
        "bbox": "[{'x': 0.3, 'y': 0.2, 'width': 0.1, 'height': 0.2, 'confidence': 0.9}]",
    }
    # Distinct positions per landmark so the geometry is non-degenerate:
    # every landmark stacked on one point would measure zero width.
    for index, name in enumerate(POSE_LANDMARK_NAMES):
        payload[name] = f"[{_landmark(x=0.1 + 0.02 * index, y=0.05 + 0.03 * index)}]"
    payload.update(overrides)
    return payload


def _without_pose() -> dict[str, Any]:
    """A payload with every landmark and face box removed."""
    payload = _payload(bbox="[]")
    for name in POSE_LANDMARK_NAMES:
        payload[name] = "[]"
    return payload


@pytest.fixture
def sidecar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A text_data file holding one complete row, wired in as the module's source."""
    path = tmp_path / "text_data.jsonl"
    rows = [{"a.png": _payload()}]
    path.write_text(
        "\n".join(json.dumps(row) for row in rows), encoding="utf-8"
    )
    monkeypatch.setattr(feature_rows_module, "text_data_file", str(path))
    return path


# The sidecar fixture is requested for its monkeypatching, not its path, so it
# is applied through the marker rather than taken as an unused argument.
@pytest.mark.usefixtures("sidecar")
def test_feature_rows_without_scores_raises() -> None:
    with pytest.raises(ValueError, match="no scores supplied"):
        feature_rows({})


@pytest.mark.usefixtures("sidecar")
def test_feature_rows_skips_images_without_a_score() -> None:
    table = feature_rows({"b.png": 0.5})
    assert table.records == []


@pytest.mark.usefixtures("sidecar")
def test_feature_rows_decodes_every_family() -> None:
    table = feature_rows({"a.png": 0.5})
    assert len(table.records) == 1
    record = table.records[0]

    assert record["filename"] == "a.png"
    assert record["score"] == 0.5
    assert record["cfg"] == pytest.approx(7.5)
    assert record["steps"] == pytest.approx(25.0)
    assert record["clip_skip"] == pytest.approx(-2.0)
    assert record["nsfw_score"] == pytest.approx(0.01)
    assert record["denoise"] == pytest.approx(0.8)
    assert record["model"] == "cyberrealistic_v90"
    assert record["sampler"] == "euler_ancestral"
    assert record["lora"] == ""

    assert record["contrast"] == pytest.approx(0.4)
    assert record["texture_lbp"] == pytest.approx(0.9)

    assert record["face_count"] == pytest.approx(1.0)
    # The fixture puts every landmark at its own position, so the derived
    # widths are non-zero rather than a degenerate point.
    assert isinstance(record["head_width"], float)
    assert float(str(record["head_width"])) > 0.0
    assert record["landmarks_detected"] == pytest.approx(33.0)
    assert record["age_label"] == "20-29"
    assert record["gender_label"] == "Female"
    assert record["race_label"] == "White"
    assert record["pose_present"] is True
    assert record["face_present"] is True


@pytest.mark.usefixtures("sidecar")
def test_feature_rows_carries_the_chart_frames() -> None:
    table = feature_rows({"a.png": 0.5})
    assert table.faces and table.faces[0]["x"] == pytest.approx(0.3)
    assert table.faces[0]["w"] == pytest.approx(0.1)
    assert table.faces[0]["score"] == 0.5
    assert len(table.landmarks) == 33
    assert table.landmarks[0]["landmark"] in POSE_LANDMARK_NAMES
    assert table.landmarks[0]["score"] == 0.5


@pytest.mark.usefixtures("sidecar")
def test_feature_rows_splits_presence_by_detection() -> None:
    table = feature_rows({"a.png": 0.5})
    detected, undetected = table.presence_scores["pose"]
    assert detected == [0.5]
    assert undetected == []

    face_detected, face_absent = table.presence_scores["face"]
    assert face_detected == [0.5]
    assert face_absent == []


def test_feature_rows_puts_undetected_images_in_the_other_group(
    sidecar: Path,
) -> None:
    sidecar.write_text(
        json.dumps({"b.png": _without_pose()}) + "\n" + json.dumps({"a.png": _payload()}),
        encoding="utf-8",
    )
    table = feature_rows({"a.png": 0.5, "b.png": 0.9})
    assert table.presence_scores["pose"][0] == [0.5]
    assert table.presence_scores["pose"][1] == [0.9]
    assert table.presence_scores["face"][0] == [0.5]
    assert table.presence_scores["face"][1] == [0.9]
    assert table.presence_scores["left_hand"][1] == [0.9]


def test_feature_rows_raises_on_a_missing_column(sidecar: Path) -> None:
    payload = _payload()
    del payload["denoise"]
    sidecar.write_text(json.dumps({"a.png": payload}), encoding="utf-8")
    with pytest.raises(ValueError, match="denoise"):
        feature_rows({"a.png": 0.5})


def test_feature_rows_names_every_missing_column(sidecar: Path) -> None:
    payload = _payload()
    del payload["denoise"]
    del payload["cfg"]
    sidecar.write_text(json.dumps({"a.png": payload}), encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        feature_rows({"a.png": 0.5})
    assert "cfg, denoise" in str(caught.value)


def test_feature_rows_requires_every_analysis_column() -> None:
    for column in ("denoise", "analysis", "bbox", "age", "race", "nose"):
        assert column in REQUIRED_COLUMNS


@pytest.mark.usefixtures("sidecar")
def test_feature_rows_handles_an_empty_table() -> None:
    table = feature_rows({"missing.png": 0.5})
    assert isinstance(table, FeatureTable)
    assert table.records == []
    assert all(not present for present, _ in table.presence_scores.values())