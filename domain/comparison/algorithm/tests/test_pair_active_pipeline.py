"""Candidate-boundary coverage for active pair phases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from comfyui_image_scorer.domain.comparison.algorithm.pair_active import (
    phase_fallback,
)
from comfyui_image_scorer.domain.comparison.algorithm.history_collapse import (
    canonicalize_pair,
)
from comfyui_image_scorer.domain.graph.node_proxy import NodeProxy


@dataclass
class _Node:
    filename: str
    link_count: int


def _nodes(*nodes: tuple[str, int]) -> list[NodeProxy]:
    return [cast("NodeProxy", _Node(name, link_count)) for name, link_count in nodes]


def test_fallback_returns_only_candidate_nodes_and_skips_existing_pairs() -> None:
    candidates = _nodes(("anchor", 1), ("first", 2), ("next", 3))

    result = phase_fallback(
        candidates,
        {canonicalize_pair("anchor", "first")},
    )

    assert result is not None
    assert result == (candidates[0], candidates[2])
    assert all(any(node is candidate for candidate in candidates) for node in result)
