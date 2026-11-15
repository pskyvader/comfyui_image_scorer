"""Unit tests for opponent selection and compatibility rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from comfyui_image_scorer.domain.comparison.algorithm.pair_opponents import (
    get_compatible_nodes,
)
from comfyui_image_scorer.domain.graph.node_proxy import NodeProxy


@dataclass(eq=False)
class _Node:
    filename: str
    link_count: int


def test_compatible_node_selector_returns_none_when_no_opponents_exist() -> None:
    anchor = cast("NodeProxy", _Node("anchor", 1))

    assert get_compatible_nodes([anchor], anchor) is None
