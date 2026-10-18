from __future__ import annotations

import pytest

from ..derived_features import (
    HAND_LANDMARKS,
    POSE_VISIBILITY_THRESHOLD,
    dominant_category,
    face_geometry,
    mean_visibility,
    pose_geometry,
    presence,
    prompt_features,
)
from ...vectors.terms import extract_terms

FULL_LANDMARKS: dict[str, list[dict[str, float]]] = {
    "left_eye_outer": [{"x": 0.44, "y": 0.16, "z": 0.0, "visibility": 0.9}],
    "right_eye_outer": [{"x": 0.36, "y": 0.19, "z": 0.0, "visibility": 0.8}],
    "left_shoulder": [{"x": 0.63, "y": 0.32, "z": 0.0, "visibility": 0.95}],
    "right_shoulder": [{"x": 0.32, "y": 0.34, "z": 0.0, "visibility": 0.95}],
    "left_hip": [{"x": 0.51, "y": 0.76, "z": 0.0, "visibility": 0.7}],
    "right_hip": [{"x": 0.32, "y": 0.73, "z": 0.0, "visibility": 0.7}],
    "left_ankle": [{"x": 0.43, "y": 1.34, "z": 0.0, "visibility": 0.6}],
    "right_ankle": [{"x": 0.26, "y": 1.34, "z": 0.0, "visibility": 0.6}],
    "left_wrist": [{"x": 0.64, "y": 0.33, "z": 0.0, "visibility": 0.88}],
    "right_wrist": [{"x": 0.36, "y": 0.32, "z": 0.0, "visibility": 0.86}],
    "left_index": [{"x": 0.58, "y": 0.28, "z": 0.0, "visibility": 0.84}],
    "right_index": [{"x": 0.42, "y": 0.27, "z": 0.0, "visibility": 0.82}],
    "left_thumb": [{"x": 0.58, "y": 0.30, "z": 0.0, "visibility": 0.80}],
    "right_thumb": [{"x": 0.42, "y": 0.28, "z": 0.0, "visibility": 0.78}],
}


def test_mean_visibility_ignores_missing_landmarks() -> None:
    assert mean_visibility(FULL_LANDMARKS, ("left_wrist", "missing")) == pytest.approx(
        0.88
    )


def test_mean_visibility_of_nothing_is_zero() -> None:
    assert mean_visibility({}, ("left_wrist",)) == 0.0


def test_presence_is_true_for_a_visible_pose_and_both_hands() -> None:
    detected = presence(FULL_LANDMARKS)
    assert detected == {"pose": True, "left_hand": True, "right_hand": True}


def test_presence_is_false_when_no_landmark_was_detected() -> None:
    assert presence({}) == {
        "pose": False,
        "left_hand": False,
        "right_hand": False,
    }


def test_presence_ignores_landmarks_below_the_threshold() -> None:
    guessed = {
        name: [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.2}]
        for name in FULL_LANDMARKS
    }
    assert presence(guessed)["pose"] is False


def test_presence_hands_use_their_own_landmark_groups() -> None:
    # A pose with both wrists visible but the fingers missing still counts for
    # the wrists, and the hand groups stay independent of each other.
    wrists_only = {
        "left_wrist": FULL_LANDMARKS["left_wrist"],
        "right_wrist": FULL_LANDMARKS["right_wrist"],
        "nose": [{"x": 0.4, "y": 0.2, "z": 0.0, "visibility": 1.0}],
    }
    detected = presence(wrists_only)
    assert detected["left_hand"] is True
    assert detected["right_hand"] is True
    # A nose alone still clears the pose threshold: the question is whether
    # MediaPipe placed a body in the frame, not whether it placed all of it.
    assert detected["pose"] is True


def test_hand_landmark_groups_are_disjoint_and_cover_each_hand() -> None:
    assert set(HAND_LANDMARKS) == {"left_hand", "right_hand"}
    assert set(HAND_LANDMARKS["left_hand"]).isdisjoint(HAND_LANDMARKS["right_hand"])
    assert set(HAND_LANDMARKS["left_hand"]) == {"left_wrist", "left_index", "left_thumb"}
    assert set(HAND_LANDMARKS["right_hand"]) == {
        "right_wrist",
        "right_index",
        "right_thumb",
    }


def test_pose_geometry_measures_symmetric_arms_apart() -> None:
    framing = pose_geometry(FULL_LANDMARKS)
    # Outer eyes sit 0.08 apart horizontally and 0.03 vertically, so the width
    # is the diagonal between them.
    assert framing["head_width"] == pytest.approx((0.08**2 + 0.03**2) ** 0.5)
    assert framing["shoulder_width"] == pytest.approx((0.31**2 + 0.02**2) ** 0.5)
    # Mirrored shoulders sit at 0.63 and 0.32, so the asymmetry is |0.63 - 0.68|.
    assert framing["lateral_asymmetry"] == pytest.approx(0.05, abs=1e-6)
    assert framing["torso_length"] > 0.0
    assert framing["leg_length"] > 0.0
    assert framing["head_y"] < framing["hip_y"]


def test_pose_geometry_counts_only_detected_landmarks() -> None:
    assert pose_geometry(FULL_LANDMARKS)["landmarks_detected"] == pytest.approx(14.0)
    assert pose_geometry({})["landmarks_detected"] == 0.0


def test_pose_geometry_of_an_empty_table_is_all_zero() -> None:
    framing = pose_geometry({})
    assert all(value == 0.0 for value in framing.values())


def test_pose_geometry_keeps_landmarks_outside_the_frame() -> None:
    # MediaPipe reports ankle y above 1.0 for a body extending past the crop;
    # the geometry must not clamp it or the leg length collapses.
    assert pose_geometry(FULL_LANDMARKS)["leg_length"] > 0.5


def test_face_geometry_reports_count_area_and_centre() -> None:
    geometry = face_geometry(
        [
            {"x": 0.2, "y": 0.4, "width": 0.1, "height": 0.2, "confidence": 0.9},
            {"x": 0.5, "y": 0.1, "width": 0.3, "height": 0.1, "confidence": 0.5},
        ]
    )
    assert geometry["face_count"] == 2.0
    assert geometry["face_area_mean"] == pytest.approx((0.02 + 0.03) / 2.0)
    assert geometry["face_area_max"] == pytest.approx(0.03)
    assert geometry["face_x"] == pytest.approx((0.25 + 0.65) / 2.0)
    assert geometry["face_y"] == pytest.approx((0.5 + 0.15) / 2.0)
    assert geometry["face_confidence"] == pytest.approx(0.7)


def test_face_geometry_without_detections_is_zero() -> None:
    geometry = face_geometry([])
    assert geometry["face_count"] == 0.0
    assert geometry["face_area_max"] == 0.0


def test_face_geometry_tolerates_missing_keys() -> None:
    assert face_geometry([{}])["face_area_mean"] == 0.0


def test_dominant_category_picks_the_highest_probability() -> None:
    label, confidence = dominant_category([{"Female": 0.2, "Male": 0.8}])
    assert (label, confidence) == ("Male", 0.8)


def test_dominant_category_uses_the_first_person_when_given_more() -> None:
    label, _ = dominant_category([{"a": 0.9}, {"a": 0.1}])
    assert label == "a"


def test_dominant_category_of_nothing_is_empty() -> None:
    assert dominant_category([]) == ("", 0.0)
    assert dominant_category([{}]) == ("", 0.0)


def test_prompt_features_of_an_empty_prompt() -> None:
    features = prompt_features("", extract_terms(""))
    assert features["prompt_terms"] == 0.0
    assert features["prompt_chars"] == 0.0
    assert features["prompt_mean_position"] == 0.0


def test_prompt_features_counts_terms_and_characters() -> None:
    text = "1girl, long hair, blue eyes"
    features = prompt_features(text, extract_terms(text))
    assert features["prompt_terms"] == 3.0
    assert features["prompt_chars"] == float(len(text))
    assert features["prompt_terms_per_100_chars"] > 0.0


def test_prompt_features_separates_hand_weighted_terms() -> None:
    # Implicit parenthesised groups multiply by 1.1 per level, so two levels
    # give 1.21. Only a written ":1.2" is a hand weight, and the share must not
    # count either nesting product as one.
    nested = "((hair))"
    single = "(hair)"
    explicit = "(hair:1.2)"
    assert prompt_features(nested, extract_terms(nested))[
        "prompt_weighted_share"
    ] == pytest.approx(0.0)
    assert prompt_features(single, extract_terms(single))[
        "prompt_weighted_share"
    ] == pytest.approx(0.0)
    assert prompt_features(explicit, extract_terms(explicit))[
        "prompt_weighted_share"
    ] == pytest.approx(1.0)


def test_prompt_features_measures_nesting_depth() -> None:
    text = "((a, b), c)"
    features = prompt_features(text, extract_terms(text))
    assert features["prompt_max_depth"] == 2.0
    assert prompt_features("a, b", extract_terms("a, b"))["prompt_max_depth"] == 0.0


def test_prompt_features_reports_the_highest_weight() -> None:
    text = "(hair:1.4), eyes"
    features = prompt_features(text, extract_terms(text))
    assert features["prompt_max_weight"] == pytest.approx(1.4)
    assert features["prompt_mean_weight"] > 1.0


def test_prompt_features_counts_duplicates_and_connectors() -> None:
    text = "hair, hair, and eyes"
    features = prompt_features(text, extract_terms(text))
    assert features["prompt_duplicates"] == 1.0
    # "and" survives as part of the term "and eyes", so the connector count is
    # taken over the raw prompt rather than over the extracted terms.
    assert features["prompt_connectors"] == 1.0
    assert (
        prompt_features("hair, eyes", extract_terms("hair, eyes"))[
            "prompt_connectors"
        ]
        == 0.0
    )


def test_prompt_features_mean_position_is_normalised() -> None:
    features = prompt_features("a, b, c", extract_terms("a, b, c"))
    assert 0.0 < features["prompt_mean_position"] < 1.0


def test_presence_threshold_default_is_documented() -> None:
    assert POSE_VISIBILITY_THRESHOLD == 0.5