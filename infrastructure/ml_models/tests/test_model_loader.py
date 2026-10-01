"""Model forwards must not build an autograd graph.

ComfyUI applies ``no_grad`` per function and enables nothing process-wide, so an
unwrapped forward retains every intermediate for backward. The retained graph is
several times the activation peak and is never used: ConvNeXt-large needs about
15 GiB for a single 1024x2216 image as a result, against a 15.99 GiB card.

These drive the public wrapper methods and assert the output carries no graph,
which fails if the ``no_grad`` context is removed from any of them.
"""

from __future__ import annotations

import pytest
import torch

from .. import model_loader as ml
from ..model_loader import (
    ComfyAttributeModel,
    ComfyEmbeddingModel,
    ComfyVisionModel,
)


def _ignore_load_model_gpu(*_args: object) -> None:
    """Stand in for ComfyUI so the wrappers do not touch its memory manager."""
    return None


class _LogitsOutput:
    """Stands in for the ``.logits`` attribute-model output shape."""

    def __init__(self, logits: torch.Tensor) -> None:
        self.logits = logits

    def __getitem__(self, _key: str) -> torch.Tensor:
        return self.logits


class _RecordingModel(torch.nn.Module):
    """Returns a tensor derived from its input, so a graph would be visible.

    Accepts the input positionally or as a keyword, matching the vision and
    attribute call shapes.
    """

    def __init__(self) -> None:
        super().__init__()
        self.weight = torch.nn.Parameter(torch.ones(1))
        self.calls = 0

    def forward(
        self, x: torch.Tensor | None = None, **kwargs: torch.Tensor
    ) -> torch.Tensor | _LogitsOutput:
        self.calls += 1
        if x is None:
            x = next(iter(kwargs.values()))
        out = x * self.weight
        return _LogitsOutput(out) if "pixel_values" in kwargs else out

    def encode(self, sentences: list[str]) -> torch.Tensor:  # type: ignore[override]
        self.calls += 1
        return torch.ones(len(sentences), 2) * self.weight


class _FakePatcher:
    def __init__(self, model: torch.nn.Module) -> None:
        self.model = model
        self.load_device = torch.device("cpu")


def test_vision_forward_carries_no_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ml.comfy.model_management, "load_model_gpu", _ignore_load_model_gpu
    )
    model = _RecordingModel()
    wrapper = ComfyVisionModel(_FakePatcher(model))  # type: ignore[arg-type]
    out = wrapper(torch.ones(1, 2, requires_grad=True))
    assert model.calls == 1
    assert out.requires_grad is False
    assert out.grad_fn is None


def test_attribute_forward_carries_no_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ml.comfy.model_management, "load_model_gpu", _ignore_load_model_gpu
    )
    model = _RecordingModel()
    wrapper = ComfyAttributeModel(_FakePatcher(model))  # type: ignore[arg-type]
    out = wrapper(pixel_values=torch.ones(1, 2, requires_grad=True))
    assert model.calls == 1
    assert not out.logits.requires_grad
    assert out.logits.grad_fn is None


def test_embedding_encode_carries_no_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ml.comfy.model_management, "load_model_gpu", _ignore_load_model_gpu
    )
    model = _RecordingModel()
    wrapper = ComfyEmbeddingModel(_FakePatcher(model))  # type: ignore[arg-type]
    out = wrapper.encode(["a", "b"])
    assert model.calls == 1
    assert not torch.as_tensor(out).requires_grad