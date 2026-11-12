"""Shared fixtures: temp rule paths, a training loader stubbed with keyed
data, and a deterministic fake trainer for the transform pipeline tests."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT.parent))

from comfyui_image_scorer.infrastructure.loading import (  # noqa: E402
    training_loader as training_loader_module,
)
from comfyui_image_scorer.infrastructure.loading.training_loader import (  # noqa: E402
    TrainingLoader,
)

RAW_WIDTH = 12
N_FILES = 6
# 12 raw features -> 12*11/2 = 66 pairwise products; the config's
# rule_number_of_interactions=500 caps at the available 66.
EXTENDED_WIDTH = RAW_WIDTH + 66


class FakeModel:
    def __init__(self) -> None:
        self.feature_importances_: np.ndarray | None = None

    def fit(
        self,
        x: np.ndarray,
        *_args: object,
        **_kwargs: object,
    ) -> None:
        gains = np.zeros(x.shape[1], dtype=np.float32)
        gains[0] = 1.0
        gains[1] = 0.5
        self.feature_importances_ = gains


class FakeTrainer:
    def __init__(self) -> None:
        self.training_model: FakeModel | None = None

    def create_training_model(self, *_args: object, **_kwargs: object) -> None:
        self.training_model = FakeModel()


@pytest.fixture
def fake_trainer() -> FakeTrainer:
    return FakeTrainer()


@pytest.fixture
def raw_data() -> tuple[dict[str, np.ndarray], dict[str, float]]:
    rng = np.random.default_rng(0)
    vectors = {
        f"img{i}": rng.standard_normal(RAW_WIDTH).astype(np.float32)
        for i in range(N_FILES)
    }
    scores = {f"img{i}": float(i) / N_FILES for i in range(N_FILES)}
    return vectors, scores


def make_stubbed_loader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    vectors: dict[str, np.ndarray],
    scores: dict[str, float],
    comparison_rows: list[dict[str, str]] | None = None,
) -> TrainingLoader:
    """Patch every loader file-path global into tmp_path and stub the keyed
    inputs, so no test ever reads or writes the real model directories."""
    models_dir = tmp_path / "models"
    models_dir.mkdir(exist_ok=True)
    for name, filename in (
        ("vectors_data", "vectors_data.npz"),
        ("scores_data", "scores_data.npz"),
        ("comparisons_data", "comparisons_data.npz"),
        ("feature_rule", "feature_rule.npz"),
        ("interaction_rule", "interaction_rule.npz"),
        ("comparison_rule", "comparison_rule.npz"),
        ("training_model", "training_model.npz"),
        ("vectors_file", "vectors.jsonl"),
        ("scores_file", "scores.jsonl"),
        ("comparisons_file", "comparisons.jsonl"),
    ):
        monkeypatch.setattr(
            training_loader_module, name, str(models_dir / filename)
        )
    monkeypatch.setattr(training_loader_module, "models_dir", str(models_dir))
    loader = TrainingLoader(use_cache=True)
    monkeypatch.setattr(loader, "load_vectors", lambda: vectors)
    monkeypatch.setattr(loader, "load_scores", lambda: scores)
    monkeypatch.setattr(
        loader, "load_comparison_rows", lambda: comparison_rows or []
    )
    return loader


@pytest.fixture
def rule_loader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    raw_data: tuple[dict[str, np.ndarray], dict[str, float]],
) -> TrainingLoader:
    """Real loader whose rule artifacts live in tmp and whose keyed inputs are
    supplied directly, so pipeline behavior is tested without file fixtures."""
    vectors, scores = raw_data
    return make_stubbed_loader(monkeypatch, tmp_path, vectors, scores)
