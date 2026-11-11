"""Tests for ranking phase setup and pair selection."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import cast

import pytest

from comfyui_image_scorer.domain.comparison.algorithm import phase_order
from comfyui_image_scorer.domain.graph.link_proxy import LinkProxy
from comfyui_image_scorer.domain.graph.node_proxy import NodeProxy
from comfyui_image_scorer.domain.ports.comparison import PairingProcessorPort
from comfyui_image_scorer.domain.ports.graph import CrystalGraphPort
from comfyui_image_scorer.domain.ports.repository import ImageRow


@dataclass(eq=False)
class _Node:
    filename: str


class _FakePairingProcessor:
    def __init__(self) -> None:
        self.recent_images: deque[str] = deque()
        self.recent_lock = Lock()


class _Graph:
    def __init__(self, nodes: list[NodeProxy]) -> None:
        self.nodes = {node.filename: node for node in nodes}
        self.existing_pairs: set[tuple[str, str]] = set()
        self.existing_pair_reads = 0
        self.link_reads = 0
        self.skip_before = 0

    def get_node(self, filename: str) -> NodeProxy | None:
        return self.nodes.get(filename)

    def get_existing_pairs(self) -> set[tuple[str, str]]:
        self.existing_pair_reads += 1
        return self.existing_pairs

    def get_all_links(self) -> list[LinkProxy]:
        self.link_reads += 1
        return []

    def set_existing_pairs(self, pairs: set[tuple[str, str]]) -> None:
        self.existing_pairs = pairs

    def get_link_count(self) -> int:
        return 1

    def reset_selection_state(self) -> None:
        pass

    def get_skip_before(self) -> int:
        return self.skip_before

    def set_skip_before(self, value: int) -> None:
        self.skip_before = value


def _image_rows() -> list[ImageRow]:
    return cast(
        "list[ImageRow]",
        [{"filename": "a"}, {"filename": "b"}],
    )


def _keep_order(_images: list[ImageRow]) -> None:
    return None


def test_phase_metadata_names_do_not_store_function_references() -> None:
    phases = phase_order.get_phases()

    assert [phase["name"] for phase in phases] == [
        "seed",
        "anchor",
        "collapsible",
        "single_win_loss",
        "chain_middle",
        "refine",
        "fallback",
    ]
    assert [phase["phase_label"] for phase in phases] == [
        "Phase 1 / Bootstrap Seed",
        "Phase 2 / Anchor Insert",
        "Phase 4 / Collapsible",
        "Phase 5 / Single Win-Loss",
        "Phase 6 / Chain Middle",
        "Phase 7 / Uncertainty Refine",
        "Fallback",
    ]
    assert [phase["color"] for phase in phases] == [
        "#f87171",
        "#fb923c",
        "#4ade80",
        "#22d3ee",
        "#60a5fa",
        "#818cf8",
        "#9ca3af",
    ]
    assert all(not callable(value) for phase in phases for value in phase.values())


def test_early_collapsible_pair_skips_pair_history_and_seed_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nodes = [
        cast("NodeProxy", _Node("a")),
        cast("NodeProxy", _Node("b")),
    ]
    graph = _Graph(nodes)
    monkeypatch.setattr(phase_order, "config", {"ranking": {"reserve_count": 2}})
    monkeypatch.setattr(phase_order.random, "shuffle", _keep_order)

    def select_collapsible(
        candidates: list[NodeProxy],
        _cg: CrystalGraphPort,
        _pairing_processor: PairingProcessorPort,
    ) -> tuple[NodeProxy, NodeProxy]:
        return candidates[0], candidates[1]

    monkeypatch.setattr(phase_order, "PHASES", ({"name": "collapsible"},))
    monkeypatch.setattr(
        phase_order, "phase_collapsible_pairs", select_collapsible
    )

    def unexpected_seed_pool(_images: list[NodeProxy]) -> list[NodeProxy]:
        raise AssertionError("seed pool should not be built for Collapsible")

    monkeypatch.setattr(phase_order, "stable_seed_pool", unexpected_seed_pool)

    pair, phase_index = phase_order.select_pair(
        _image_rows(),
        _image_rows(),
        cast("CrystalGraphPort", graph),
        cast("PairingProcessorPort", _FakePairingProcessor()),
    )

    assert pair is not None
    assert set(pair) == {"a", "b"}
    assert phase_index == 0
    assert graph.existing_pair_reads == 0
    assert graph.link_reads == 0


def test_seed_and_anchor_reuse_lazily_prepared_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nodes = [
        cast("NodeProxy", _Node("a")),
        cast("NodeProxy", _Node("b")),
    ]
    graph = _Graph(nodes)
    seed_pool_calls = 0
    observed_seed_pool: list[NodeProxy] = []
    monkeypatch.setattr(phase_order, "config", {"ranking": {"reserve_count": 2}})
    monkeypatch.setattr(phase_order.random, "shuffle", _keep_order)

    def seed_phase(
        candidates: list[NodeProxy],
        existing_pairs: set[tuple[str, str]],
        seed_pool: list[NodeProxy],
        all_images_length: int,
    ) -> tuple[NodeProxy, NodeProxy] | None:
        assert candidates == nodes
        assert existing_pairs == set()
        assert seed_pool == nodes
        assert all_images_length == 2
        return None

    def anchor_phase(
        candidates: list[NodeProxy],
        existing_pairs: set[tuple[str, str]],
        _pairing_processor: PairingProcessorPort,
    ) -> tuple[NodeProxy, NodeProxy]:
        assert candidates == nodes
        assert existing_pairs == set()
        return candidates[0], candidates[1]

    def make_seed_pool(images: list[NodeProxy]) -> list[NodeProxy]:
        nonlocal seed_pool_calls
        seed_pool_calls += 1
        observed_seed_pool.extend(images)
        return images

    monkeypatch.setattr(phase_order, "stable_seed_pool", make_seed_pool)
    monkeypatch.setattr(
        phase_order, "PHASES", ({"name": "seed"}, {"name": "anchor"})
    )
    monkeypatch.setattr(phase_order, "phase_seed_coverage", seed_phase)
    monkeypatch.setattr(phase_order, "phase_anchor_insert", anchor_phase)

    pair, phase_index = phase_order.select_pair(
        _image_rows(),
        _image_rows(),
        cast("CrystalGraphPort", graph),
        cast("PairingProcessorPort", _FakePairingProcessor()),
    )

    assert pair is not None
    assert set(pair) == {"a", "b"}
    assert phase_index == 1
    assert seed_pool_calls == 1
    assert len(observed_seed_pool) == 2
    assert graph.existing_pair_reads == 1
    assert graph.link_reads == 1


def test_branch_probe_runs_immediately_after_anchor_insert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nodes = [
        cast("NodeProxy", _Node("a")),
        cast("NodeProxy", _Node("b")),
    ]
    graph = _Graph(nodes)
    calls: list[str] = []
    def _return_nodes(_nodes: list[NodeProxy]) -> list[NodeProxy]:
        return nodes
    monkeypatch.setattr(phase_order, "config", {"ranking": {"reserve_count": 2}})
    monkeypatch.setattr(phase_order.random, "shuffle", _keep_order)
    monkeypatch.setattr(phase_order, "stable_seed_pool", _return_nodes)
    monkeypatch.setattr(
        phase_order, "PHASES", ({"name": "anchor"}, {"name": "branch_probe"})
    )

    def anchor_phase(
        _candidates: list[NodeProxy],
        _existing_pairs: set[tuple[str, str]],
        _pairing_processor: PairingProcessorPort,
    ) -> None:
        calls.append("anchor")
        return None

    def branch_probe_phase(
        candidates: list[NodeProxy],
        existing_pairs: set[tuple[str, str]],
    ) -> tuple[NodeProxy, NodeProxy]:
        calls.append("branch_probe")
        assert candidates == nodes
        assert existing_pairs == set()
        return nodes[0], nodes[1]

    monkeypatch.setattr(phase_order, "phase_anchor_insert", anchor_phase)
    monkeypatch.setattr(phase_order, "phase_branch_probe", branch_probe_phase)

    pair, phase_index = phase_order.select_pair(
        _image_rows(),
        _image_rows(),
        cast("CrystalGraphPort", graph),
        cast("PairingProcessorPort", _FakePairingProcessor()),
    )

    assert pair == ("a", "b")
    assert phase_index == 1
    assert calls == ["anchor", "branch_probe"]
