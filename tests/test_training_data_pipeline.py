"""load_training_data flag-matrix tests over the real loader + fake trainer."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import numpy as np
import pytest

from comfyui_image_scorer.application.hyperparameters.hyperparameter_optimizer import (
    load_training_data,
)
from comfyui_image_scorer.domain.ports.loading import ModelTrainingService
from comfyui_image_scorer.infrastructure.loading.training_loader import TrainingLoader
from conftest import (
    EXTENDED_WIDTH,
    FakeTrainer,
    N_FILES,
    RAW_WIDTH,
    make_stubbed_loader,
)


def test_all_flags_false_returns_raw_data(
    rule_loader: TrainingLoader, fake_trainer: FakeTrainer
) -> None:
    data = load_training_data(
        False,
        False,
        False,
        rule_loader,
        cast(ModelTrainingService, fake_trainer),
    )

    assert data.x.shape == (N_FILES, RAW_WIDTH)
    np.testing.assert_allclose(
        data.y, [i / N_FILES for i in range(N_FILES)], rtol=1e-6
    )
    assert data.rule_fingerprint is None


def test_feature_filter_only(
    rule_loader: TrainingLoader, fake_trainer: FakeTrainer
) -> None:
    data = load_training_data(
        False, True, False, rule_loader, cast(ModelTrainingService, fake_trainer)
    )

    # FakeModel reports gain on the first two features only; the config's
    # keep-proportion of 1.0 keeps every survivor.
    assert data.x.shape == (N_FILES, 2)
    assert data.rule_fingerprint is not None


def test_interactions_only(
    rule_loader: TrainingLoader, fake_trainer: FakeTrainer
) -> None:
    data = load_training_data(
        True, False, False, rule_loader, cast(ModelTrainingService, fake_trainer)
    )

    assert data.x.shape == (N_FILES, EXTENDED_WIDTH)
    assert data.rule_fingerprint is not None


def test_interactions_run_before_feature_filter(
    rule_loader: TrainingLoader, fake_trainer: FakeTrainer, tmp_path: Path
) -> None:
    data = load_training_data(
        True, True, False, rule_loader, cast(ModelTrainingService, fake_trainer)
    )

    # The feature filter runs over the extended layout: the saved rule must
    # record the 78-wide matrix, not the raw one.
    with np.load(tmp_path / "models" / "feature_rule.npz") as npz:
        assert int(npz["n_features_in"]) == EXTENDED_WIDTH
    assert data.x.shape == (N_FILES, 2)
    assert data.rule_fingerprint is not None


def test_comparison_filter_keeps_only_files_above_threshold(
    monkeypatch: pytest.MonkeyPatch,
    rule_loader: TrainingLoader,
    fake_trainer: FakeTrainer,
) -> None:
    rows = [
        {"filename_a": "img0", "filename_b": "img3", "winner": "img0"},
        {"filename_a": "img3", "filename_b": "img0", "winner": "img3"},
        {"filename_a": "img4", "filename_b": "img0", "winner": "img4"},
    ]
    monkeypatch.setattr(rule_loader, "load_comparison_rows", lambda: rows)
    data = load_training_data(
        False, False, True, rule_loader, cast(ModelTrainingService, fake_trainer)
    )

    # Counts: img0=3, img3=2, img4=1; the config threshold of 2 keeps img0/img3.
    assert data.x.shape == (2, RAW_WIDTH)
    assert data.rule_fingerprint is None


def test_fingerprint_tracks_rule_changes(
    monkeypatch: pytest.MonkeyPatch,
    rule_loader: TrainingLoader,
    fake_trainer: FakeTrainer,
    raw_data: tuple[dict[str, np.ndarray], dict[str, float]],
    tmp_path: Path,
) -> None:
    first = load_training_data(
        False, True, False, rule_loader, cast(ModelTrainingService, fake_trainer)
    )
    assert first.rule_fingerprint is not None

    np.savez_compressed(
        tmp_path / "models" / "feature_rule.npz",
        kept_indices=np.array([0, 1, 2], dtype=np.intp),
        n_features_in=np.int64(RAW_WIDTH),
    )
    # A fresh loader reads the swapped file; the first loader's in-session
    # memo legitimately shadows it.
    vectors, scores = raw_data
    second = load_training_data(
        False,
        True,
        False,
        make_stubbed_loader(monkeypatch, tmp_path, vectors, scores),
        cast(ModelTrainingService, fake_trainer),
    )

    assert second.x.shape == (N_FILES, 3)
    assert second.rule_fingerprint != first.rule_fingerprint
