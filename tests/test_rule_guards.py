"""Rule cache behavior tests: width validation, digests, and fingerprinting."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import numpy as np
import pytest

from comfyui_image_scorer.domain.data_transformation.data_transformer import (
    DataTransformer,
    rule_fingerprint,
)
from comfyui_image_scorer.domain.ports.loading import ModelTrainingService
from comfyui_image_scorer.infrastructure.loading import (
    training_loader as training_loader_module,
)
from comfyui_image_scorer.infrastructure.loading.training_loader import TrainingLoader
from conftest import RAW_WIDTH, FakeTrainer

KeyedData = tuple[dict[str, np.ndarray], dict[str, float]]


def _transformer(
    rule_loader: TrainingLoader, fake_trainer: FakeTrainer
) -> DataTransformer:
    return DataTransformer(rule_loader, cast(ModelTrainingService, fake_trainer))


def test_rule_fingerprint_composition() -> None:
    assert rule_fingerprint(None, None) is None
    fingerprint = rule_fingerprint(b"a", b"b")
    assert isinstance(fingerprint, int)
    assert fingerprint == rule_fingerprint(b"a", b"b")
    assert fingerprint != rule_fingerprint(b"a", None)
    assert fingerprint != rule_fingerprint(None, b"b")
    assert fingerprint != rule_fingerprint(b"b", b"a")


def test_apply_feature_filter_requires_rule(
    rule_loader: TrainingLoader, fake_trainer: FakeTrainer
) -> None:
    transformer = _transformer(rule_loader, fake_trainer)
    with pytest.raises(FileNotFoundError):
        transformer.apply_feature_filter([np.zeros(4, dtype=np.float32)])


def test_apply_feature_filter_width_mismatch_raises(
    rule_loader: TrainingLoader, fake_trainer: FakeTrainer, raw_data: KeyedData
) -> None:
    transformer = _transformer(rule_loader, fake_trainer)
    vectors, scores = raw_data
    transformer.filter_unused_features(vectors, scores, steps=5)

    with pytest.raises(FileNotFoundError):
        transformer.apply_feature_filter([np.zeros(5, dtype=np.float32)])
    filtered = transformer.apply_feature_filter(
        [np.zeros(RAW_WIDTH, dtype=np.float32) for _ in range(3)]
    )
    assert len(filtered) == 3
    assert all(vec.shape == (2,) for vec in filtered)


def test_stale_rule_is_cache_miss_during_training(
    rule_loader: TrainingLoader,
    fake_trainer: FakeTrainer,
    raw_data: KeyedData,
    tmp_path: Path,
) -> None:
    transformer = _transformer(rule_loader, fake_trainer)
    np.savez_compressed(
        tmp_path / "models" / "feature_rule.npz",
        kept_indices=np.array([0], dtype=np.intp),
        n_features_in=np.int64(999),
    )
    vectors, scores = raw_data
    kept = transformer.filter_unused_features(vectors, scores, steps=5)

    assert kept.shape == (2,)
    assert rule_loader.load_feature_rule(RAW_WIDTH) is not None
    assert rule_loader.load_feature_rule(999) is None


def test_legacy_rule_without_width_is_cache_miss(
    rule_loader: TrainingLoader, tmp_path: Path
) -> None:
    np.savez_compressed(
        tmp_path / "models" / "feature_rule.npz",
        kept_indices=np.array([0, 1], dtype=np.intp),
    )
    assert rule_loader.load_feature_rule(RAW_WIDTH) is None


def test_apply_interaction_features_requires_rule(
    rule_loader: TrainingLoader, fake_trainer: FakeTrainer
) -> None:
    transformer = _transformer(rule_loader, fake_trainer)
    with pytest.raises(FileNotFoundError):
        transformer.apply_interaction_features(
            [np.zeros(RAW_WIDTH, dtype=np.float32)]
        )


def test_apply_interaction_features_width_mismatch_raises(
    rule_loader: TrainingLoader, fake_trainer: FakeTrainer, raw_data: KeyedData
) -> None:
    transformer = _transformer(rule_loader, fake_trainer)
    vectors, scores = raw_data
    extended = transformer.create_interaction_rule(vectors, scores, target_k=500)

    assert len(extended) == len(vectors)
    assert all(vec.shape == (RAW_WIDTH + 66,) for vec in extended.values())

    with pytest.raises(FileNotFoundError):
        transformer.apply_interaction_features([np.zeros(5, dtype=np.float32)])
    applied = transformer.apply_interaction_features(
        [np.zeros(RAW_WIDTH, dtype=np.float32) for _ in range(2)]
    )
    assert applied.shape == (2, RAW_WIDTH + 66)


def test_rule_digest_memoization(
    rule_loader: TrainingLoader, fake_trainer: FakeTrainer, raw_data: KeyedData
) -> None:
    transformer = _transformer(rule_loader, fake_trainer)
    vectors, scores = raw_data
    transformer.filter_unused_features(vectors, scores, steps=5)
    digest = rule_loader.feature_rule_digest()
    assert digest is not None and len(digest) == 16

    fresh = TrainingLoader(use_cache=True)
    assert fresh.feature_rule_digest() is None
    assert fresh.load_feature_rule(RAW_WIDTH) is not None
    assert fresh.feature_rule_digest() == digest

    fresh.save_feature_rule(np.array([3, 4, 5], dtype=np.intp), RAW_WIDTH)
    assert fresh.feature_rule_digest() != digest


def test_digest_survives_without_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    models_dir = tmp_path / "models"
    models_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(training_loader_module, "models_dir", str(models_dir))
    monkeypatch.setattr(
        training_loader_module, "feature_rule", str(models_dir / "feature_rule.npz")
    )
    loader = TrainingLoader(use_cache=False)
    loader.save_feature_rule(np.array([0], dtype=np.intp), 4)
    assert loader.feature_rule_digest() is not None
