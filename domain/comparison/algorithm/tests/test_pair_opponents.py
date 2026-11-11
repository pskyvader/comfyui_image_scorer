"""Unit tests for opponent selection and compatibility rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from comfyui_image_scorer.domain.comparison.algorithm.pair_opponents import (
    get_branch_chain_compatible_nodes,
    get_compatible_nodes,
)
from comfyui_image_scorer.domain.graph.node_proxy import NodeProxy


@dataclass(eq=False)
class _Node:
    filename: str
    link_count: int
    trueskill_score: float = 0.5
    chain: _Chain | None = None

    def get_chain(self) -> list[_Chain]:
        return [self.chain] if self.chain is not None else []


@dataclass
class _Chain:
    nodes: list[NodeProxy]
    id: int = 0


def _branch_chain_fixture(prefix: str = "") -> tuple[
    NodeProxy,
    NodeProxy,
    NodeProxy,
    NodeProxy,
    NodeProxy,
    NodeProxy,
    _Chain,
    _Chain,
]:
    upper = cast("NodeProxy", _Node(f"{prefix}upper", 0))
    anchor = cast(
        "NodeProxy", _Node(f"{prefix}anchor", 1, trueskill_score=0.5)
    )
    above = cast("NodeProxy", _Node(f"{prefix}above", 3))
    first_below = cast(
        "NodeProxy", _Node(f"{prefix}first-below", 2, trueskill_score=0.1)
    )
    second_below = cast(
        "NodeProxy", _Node(f"{prefix}second-below", 2, trueskill_score=0.49)
    )
    third_below = cast(
        "NodeProxy", _Node(f"{prefix}third-below", 2, trueskill_score=0.3)
    )
    anchor_chain = _Chain([upper, anchor], id=1)
    branch_chain = _Chain(
        [above, upper, first_below, second_below, third_below], id=2
    )
    cast("_Node", upper).chain = branch_chain
    cast("_Node", anchor).chain = anchor_chain
    cast("_Node", above).chain = branch_chain
    cast("_Node", first_below).chain = branch_chain
    cast("_Node", second_below).chain = branch_chain
    cast("_Node", third_below).chain = branch_chain
    return (
        anchor,
        upper,
        above,
        first_below,
        second_below,
        third_below,
        anchor_chain,
        branch_chain,
    )


def test_compatible_node_selector_returns_none_when_no_opponents_exist() -> None:
    anchor = cast("NodeProxy", _Node("anchor", 1))

    assert get_compatible_nodes([anchor], anchor) is None


def test_branch_chain_compatible_nodes_use_candidates_below_upper_node() -> None:
    anchor, upper, above, first_below, second_below, third_below, _, _ = (
        _branch_chain_fixture()
    )
    candidates = [
        above,
        upper,
        anchor,
        first_below,
        second_below,
        third_below,
    ]

    compatible_nodes = get_branch_chain_compatible_nodes(candidates, anchor)

    assert compatible_nodes is not None
    assert compatible_nodes == [first_below, second_below, third_below]
    assert all(node in candidates for node in compatible_nodes)


def test_branch_chain_compatible_nodes_return_empty_without_upper_node() -> None:
    anchor = cast("NodeProxy", _Node("anchor", 1))
    anchor_chain = _Chain([anchor], id=1)
    cast("_Node", anchor).chain = anchor_chain

    compatible_nodes = get_branch_chain_compatible_nodes([anchor], anchor)

    assert compatible_nodes is None


def test_branch_chain_compatible_nodes_return_empty_without_distinct_branch() -> None:
    upper = cast("NodeProxy", _Node("upper", 1))
    anchor = cast("NodeProxy", _Node("anchor", 2))
    anchor_chain = _Chain([upper, anchor], id=1)
    cast("_Node", upper).chain = anchor_chain
    cast("_Node", anchor).chain = anchor_chain

    compatible_nodes = get_branch_chain_compatible_nodes([anchor, upper], anchor)

    assert compatible_nodes is None


def test_branch_chain_compatible_nodes_return_empty_without_candidate_matches() -> None:
    anchor, upper, above, _, _, _, _, _ = _branch_chain_fixture()

    compatible_nodes = get_branch_chain_compatible_nodes(
        [anchor, upper, above], anchor
    )

    assert compatible_nodes is None

