"""Batch calibration must judge a probe by its marginal cost, not its peak.

Driven through the public ``get()`` entry point so the whole search is covered
rather than the private helpers behind it. The allocator is replaced with a
scripted cost model, so the expected batch size can be asserted arithmetically
instead of against whatever a real probe happens to measure.

The bugs these cover: a probe's cost was compared against free memory read
*after* the probe ran, so a small marginal cost was rejected whenever other
models were resident; and a stale least-squares fit was allowed to cap the
search at a batch of two.
"""

from __future__ import annotations

from typing import Any

import pytest
import torch

from .. import batch_sizer as bs
from ..batch_sizer import BatchSizer

GB = 1024**3
MB = 1024**2

MODEL_KEY = "test_model"
MODEL_NAME = "test_model_weights"
DEVICE = "test_device"


def _no_op(*_args: object, **_kwargs: object) -> None:
    return None


class _IdentityModel(torch.nn.Module):
    """Stands in for the vision model so a probe allocates no real memory."""

    def __init__(self) -> None:
        super().__init__()
        # torch.zeros is stubbed per test, so build the parameter with ones.
        self.weight = torch.nn.Parameter(torch.ones(1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x


class _FakeProperties:
    total_memory = 16 * GB


class _FakePatcher:
    """Just enough of a ModelPatcher for the profiling path."""

    def __init__(self, model: torch.nn.Module) -> None:
        self.model = model
        self.load_device = torch.device("cuda")

    def partially_load(self, *_: object, **__: object) -> None:
        return None


class _FakeLoader:
    def load_vision_model_patcher(self, _model_key: str) -> _FakePatcher:
        return _FakePatcher(_IdentityModel())

    def load_attribute_model_patcher(self, _model_key: str) -> _FakePatcher:
        return _FakePatcher(_IdentityModel())


def _payload(**overrides: Any) -> dict[str, Any]:
    """A stored profile entry, as the session profiler expects to read."""
    base: dict[str, Any] = {
        "model_name": MODEL_NAME,
        "device_name": DEVICE,
        "device_id": "cuda",
        "total_memory": 16 * GB,
        "model_memory_bytes": 1 * GB,
        "fixed_overhead": None,
        "pixel_cost": None,
        "r_squared": None,
        "history": {},
    }
    base.update(overrides)
    return base


def _entries(pairs: list[tuple[int, int]]) -> list[dict[str, Any]]:
    return [
        {"batch_size": batch, "delta_memory": delta, "timestamp": 0.0}
        for batch, delta in pairs
    ]


class _Harness:
    """A sizer wired to a scripted allocator and a known stored profile."""

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]
    ) -> None:
        self.payload = payload
        self.saved: list[dict[str, Any]] = []
        self.resident = 0
        self.free = 14 * GB
        # Activation bytes per (batch * w * h * 3) pixel-channel, so a batch
        # costs what a convolution actually costs at that resolution.
        self.per_pixel = 512 * MB / (1024 * 1024 * 3)
        self.probed: list[int] = []
        self._candidate = 0
        self._area = 1024 * 1024 * 3

        def load_json(*_a: object, **_k: object) -> tuple[dict[str, Any], None]:
            return {"profiles": [self.payload]}, None

        def save(_path: object, data: dict[str, Any], **_k: object) -> None:
            self.saved.append(data)

        def free(*_a: object) -> int:
            return self.free

        def allocated(*_a: object) -> int:
            return self.resident

        def device_name(*_a: object) -> str:
            return DEVICE

        def properties(*_a: object) -> _FakeProperties:
            return _FakeProperties()

        def zeros(shape: tuple[int, ...], **_k: object) -> torch.Tensor:
            self._candidate = int(shape[0])
            self._area = int(shape[1]) * int(shape[2]) * int(shape[3])
            return torch.empty(0)

        def peak(*_a: object) -> int:
            self.probed.append(self._candidate)
            return self.resident + self.cost_for(self._candidate)

        monkeypatch.setattr(
            bs,
            "config",
            {
                "prepare": {
                    "vision_models": {
                        MODEL_KEY: {"name": MODEL_NAME, "device": "cuda"}
                    },
                    "attribute_models": {},
                }
            },
        )
        monkeypatch.setattr(bs, "model_loader", _FakeLoader())
        monkeypatch.setattr(bs, "load_json", load_json)
        monkeypatch.setattr(bs, "atomic_write_json", save)
        monkeypatch.setattr(bs.comfy.model_management, "load_model_gpu", _no_op)
        monkeypatch.setattr(bs.comfy.model_management, "get_free_memory", free)

        monkeypatch.setattr(torch.cuda, "empty_cache", _no_op)
        monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", _no_op)
        monkeypatch.setattr(torch.cuda, "synchronize", _no_op)
        monkeypatch.setattr(torch.cuda, "get_device_name", device_name)
        monkeypatch.setattr(torch.cuda, "get_device_properties", properties)
        monkeypatch.setattr(torch.cuda, "memory_allocated", allocated)
        monkeypatch.setattr(torch.cuda, "max_memory_allocated", peak)
        monkeypatch.setattr(torch, "zeros", zeros)

    def cost_for(self, candidate: int) -> int:
        """Activation bytes the scripted allocator reports for a batch."""
        return candidate * int(self.per_pixel * self._area)

    def sizer(self) -> BatchSizer:
        return BatchSizer(MODEL_KEY)

    def stored(self) -> dict[str, Any]:
        """The profile as it was last written back to the cache file."""
        return self.saved[-1]["profiles"][0]

    def history(self, resolution: str) -> list[dict[str, Any]]:
        return self.stored()["history"].get(resolution, [])


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> _Harness:
    return _Harness(monkeypatch, _payload())


def test_cold_resolution_returns_the_batch_the_memory_allows(
    harness: _Harness,
) -> None:
    """With 14 GiB free and 512 MiB per image at 1024x1024 the answer is 28."""
    assert harness.sizer().get(1024, 1024, rebuild=False) == 28


def test_a_stale_fit_does_not_cap_the_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """Overhead beyond the model's own weights cannot describe the model.

    This fit used to yield a ceiling of 2 here, so batch 3 and up were never
    attempted and every image at this resolution ran alone.
    """
    harness = _Harness(
        monkeypatch,
        _payload(fixed_overhead=3 * GB, pixel_cost=1822.0, model_memory_bytes=1 * GB),
    )
    # 1280x1536 is 1.875x the area of 1024x1024, so half as many images fit.
    assert harness.sizer().get(1280, 1536, rebuild=False) == 14
    assert max(harness.probed) > 2, "search never looked past a batch of two"


def test_a_trustworthy_fit_reaches_the_same_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _Harness(
        monkeypatch,
        _payload(
            fixed_overhead=0,
            pixel_cost=512 * MB / (1024 * 1024 * 3),
            model_memory_bytes=1 * GB,
        ),
    )
    assert harness.sizer().get(1024, 1024, rebuild=False) == 28


def test_resident_models_do_not_shrink_the_batch(harness: _Harness) -> None:
    """12 GiB already loaded must not make a 4 GiB probe look oversized.

    Comparing the absolute peak against what is free rejected this outright and
    floored the result at one for every resolution whenever other models were
    loaded.
    """
    harness.resident = 12 * GB
    harness.free = 4 * GB
    assert harness.sizer().get(1024, 1024, rebuild=False) == 8


def test_history_records_the_marginal_cost(harness: _Harness) -> None:
    harness.sizer().get(1024, 1024, rebuild=False)
    recorded = harness.history("1024x1024")
    assert recorded
    for entry in recorded:
        assert entry["delta_memory"] == entry["batch_size"] * 512 * MB


def test_orientation_does_not_create_a_second_key(harness: _Harness) -> None:
    sizer = harness.sizer()
    sizer.get(1280, 1536, rebuild=False)
    sizer.get(1536, 1280, rebuild=False)
    assert list(harness.stored()["history"]) == ["1280x1536"]


def test_cached_batch_is_returned_without_probing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _Harness(
        monkeypatch,
        _payload(history={"1024x1024": _entries([(7, 7 * 512 * MB)])}),
    )
    assert harness.sizer().get(1024, 1024, rebuild=False) == 7
    assert harness.probed == []


def test_cached_batch_beyond_headroom_is_reprofiled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _Harness(
        monkeypatch,
        _payload(history={"1024x1024": _entries([(40, 40 * 512 * MB)])}),
    )
    harness.free = 4 * GB
    assert harness.sizer().get(1024, 1024, rebuild=False) == 8
    assert harness.probed, "a stale batch past headroom should be re-measured"


def test_cached_batch_one_is_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = _Harness(
        monkeypatch,
        _payload(history={"1024x1024": _entries([(1, 512 * MB)])}),
    )
    harness.free = 0
    assert harness.sizer().get(1024, 1024, rebuild=False) == 1


def test_bound_limits_the_result(harness: _Harness) -> None:
    assert harness.sizer().get(1024, 1024, rebuild=False, bound=5) == 5


def test_fit_recovers_a_known_linear_cost(harness: _Harness) -> None:
    cost = 1000.0
    harness.per_pixel = cost
    sizer = harness.sizer()
    sizer.get(512, 512, rebuild=False)
    sizer.get(1024, 1024, rebuild=False)
    # The scripted allocator has no per-call overhead, so the intercept is zero.
    assert harness.stored()["fixed_overhead"] == pytest.approx(0, abs=MB)
    assert harness.stored()["pixel_cost"] == pytest.approx(cost, rel=0.01)
    assert harness.stored()["r_squared"] == pytest.approx(1.0, abs=0.01)


def test_fit_reports_no_model_without_spread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One batch size at one resolution gives no per-pixel slope to fit."""
    harness = _Harness(
        monkeypatch,
        _payload(
            fixed_overhead=0,
            pixel_cost=1000.0,
            history={"1024x1024": _entries([(1, GB), (1, 2 * GB)])},
        ),
    )
    # Nothing fits, so the search falls through to the fit with every recorded
    # point at the same batch size and resolution.
    harness.free = 0
    harness.sizer().get(1024, 1024, rebuild=True)
    assert harness.stored()["pixel_cost"] is None
    assert harness.stored()["fixed_overhead"] is None
    assert harness.stored()["r_squared"] is None