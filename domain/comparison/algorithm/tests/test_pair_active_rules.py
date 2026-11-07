"""Tests for extracted pair-phase selection rules."""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from typing import cast

import pytest

from comfyui_image_scorer.domain.comparison.algorithm import pair_active
from comfyui_image_scorer.domain.graph.node_proxy import NodeProxy
from comfyui_image_scorer.domain.ports.graph import CrystalGraphPort


@dataclass(eq=False)
class _Node:
    filename: str
    link_count: int
    trueskill_score: float = 0.5
    sigma_uncertainty: float = 10.0
    score: float = 0.5
    chain: _Chain | None = None

    @property
    def mu_skill(self) -> float:
        return self.score

    def get_links(
        self, worse_than: bool = False, better_than: bool = False
    ) -> list[_Node]:
        return [self] if worse_than or better_than else []

    def get_chain(self) -> list[_Chain]:
        return [self.chain] if self.chain is not None else []

    def is_bottom(self) -> bool:
        return True

    def is_top(self) -> bool:
        return True


class _CountingNode(_Node):
    def __init__(self, filename: str, link_count: int) -> None:
        super().__init__(filename, link_count)
        self.link_queries: list[bool] = []

    def get_links(
        self, worse_than: bool = False, better_than: bool = False
    ) -> list[_Node]:
        self.link_queries.append(worse_than)
        return super().get_links(worse_than, better_than)


@dataclass
class _Chain:
    nodes: list[NodeProxy]
    id: int = 0

    @property
    def first(self) -> NodeProxy | None:
        return self.nodes[0] if self.nodes else None

    @property
    def last(self) -> NodeProxy | None:
        return self.nodes[-1] if self.nodes else None

    @property
    def main_nodes(self) -> list[NodeProxy]:
        return self.nodes

    @property
    def main_length(self) -> int:
        return len(self.nodes)

    def main_node_at(self, position: int) -> NodeProxy | None:
        if 0 <= position < len(self.nodes):
            return self.nodes[position]
        return None


class _Graph:
    def __init__(self, chains: list[_Chain]) -> None:
        self.chains = chains
        self.recent_chain_ids: list[int] = []

    def get_all_chains(
        self, min_length: int = 0, sort_order: str = "asc"
    ) -> list[_Chain]:
        chains = [
            chain for chain in self.chains if len(chain.nodes) >= min_length
        ]
        return sorted(
            chains,
            key=lambda chain: len(chain.nodes),
            reverse=sort_order == "desc",
        )

    def get_recent_chain_ids(self) -> list[int]:
        return list(self.recent_chain_ids)

    def set_recent_chain_ids(self, chain_ids: list[int]) -> None:
        self.recent_chain_ids = list(chain_ids)

    def are_in_same_path(self, filename_a: str, filename_b: str) -> bool:
        return filename_a == filename_b

    def get_loser_only_nodes(self) -> list[NodeProxy]:
        return [node for chain in self.chains for node in chain.nodes]

    def get_winner_only_nodes(self) -> list[NodeProxy]:
        return []

    def get_node(self, filename: str) -> NodeProxy | None:
        return next(
            (
                node
                for chain in self.chains
                for node in chain.nodes
                if node.filename == filename
            ),
            None,
        )


def _nodes(*values: tuple[str, int]) -> list[NodeProxy]:
    return [
        cast("NodeProxy", _Node(filename, link_count))
        for filename, link_count in values
    ]


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


def _config():
    return {
        "ranking": {
            "seed_percentage": 50,
            "seed_target_comparisons": 5,
            "sigma_range_multiplier": 3.0,
            "insertion_target_comparisons": 0,
            "reserve_count": 1,
            "minimum_chains_for_pairing": 2,
            "chain_middle_min_chain_length": 10,
        }
    }


def test_seed_coverage_skips_when_ready_pool_reaches_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pair_active, "config", _config())
    seed_pool = _nodes(
        ("ready-a", 5),
        ("ready-b", 6),
        ("ready-c", 7),
        ("ready-d", 8),
        ("ready-e", 9),
    )

    assert pair_active.phase_seed_coverage([], set(), seed_pool, 10) is None


def test_seed_coverage_selects_anchor_from_candidate_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pair_active, "config", _config())
    candidates = _nodes(("most-ready", 4), ("less-ready", 2), ("over-target", 6))

    result = pair_active.phase_seed_coverage(candidates, set(), [], 10)

    assert result == (candidates[0], candidates[1])


def test_single_win_loss_candidate_lanes_yield_on_demand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pair_active, "config", _config())
    candidates = [
        cast("NodeProxy", _CountingNode("first", 1)),
        cast("NodeProxy", _CountingNode("second", 1)),
    ]

    result = pair_active.phase_single_win_loss(candidates, set())

    assert result == (candidates[0], candidates[1])
    assert [cast("_CountingNode", node).link_queries for node in candidates] == [
        [True],
        [True],
    ]


def test_single_win_loss_keeps_pair_members_in_candidate_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pair_active, "config", _config())
    candidates = _nodes(("anchor", 5), ("opponent", 6))

    result = pair_active.phase_single_win_loss(candidates, set())

    assert result == (candidates[0], candidates[1])


def test_chain_merge_selects_only_candidate_nodes_and_updates_recent_chains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pair_active, "config", _config())
    candidates = [
        cast("NodeProxy", _Node("a0", 2, score=0.0)),
        cast("NodeProxy", _Node("a1", 2, score=0.1)),
        cast("NodeProxy", _Node("b0", 2, score=0.02)),
        cast("NodeProxy", _Node("b1", 2, score=0.15)),
    ]
    graph = _Graph([_Chain(candidates[:2]), _Chain(candidates[2:])])

    result = pair_active.phase_chain_merge(
        candidates, cast("CrystalGraphPort", graph)
    )

    assert result is not None
    assert result == (candidates[0], candidates[2])
    assert all(any(node is candidate for candidate in candidates) for node in result)
    assert graph.recent_chain_ids == [0, 1]


def test_collapsible_pairs_select_only_candidate_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pair_active, "config", _config())
    candidates = _nodes(("least-compared", 1), ("other", 2))
    graph = _Graph([_Chain([node]) for node in candidates])

    result = pair_active.phase_collapsible_pairs(
        candidates, cast("CrystalGraphPort", graph)
    )

    assert result == (candidates[0], candidates[1])


def test_chain_middle_filters_pairs_after_candidate_formation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pair_active, "config", _config())
    anchor, _, _, opponent, _, _, anchor_chain, branch_chain = (
        _branch_chain_fixture()
    )
    candidates = [anchor, opponent]
    graph = _Graph([anchor_chain, branch_chain])

    result = pair_active.phase_chain_middle(
        candidates, set(), cast("CrystalGraphPort", graph)
    )

    assert result == (anchor, opponent)


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

    compatible_nodes = pair_active._get_branch_chain_compatible_nodes(
        candidates, anchor
    )

    assert compatible_nodes is not None
    assert compatible_nodes == [first_below, second_below, third_below]
    assert all(node in candidates for node in compatible_nodes)


def test_compatible_node_selector_returns_none_when_no_opponents_exist() -> None:
    anchor = cast("NodeProxy", _Node("anchor", 1))

    assert pair_active._get_compatible_nodes([anchor], anchor) is None


def test_branch_probe_filters_then_selects_closest_score_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pair_active, "config", _config())
    first = _branch_chain_fixture()
    second = _branch_chain_fixture("other-")
    candidate_nodes = [
        *first[:6],
        *second[:6],
    ]
    node_a = first[0]
    monkeypatch.setattr(pair_active.random, "choice", lambda _nodes: node_a)
    existing_pair_set = {
        pair_active.canonicalize_pair(node_a.filename, first[3].filename)
    }

    result = pair_active.phase_branch_probe(candidate_nodes, existing_pair_set)

    assert result == (node_a, first[4])


def test_branch_chain_compatible_nodes_return_empty_without_upper_node() -> None:
    anchor = cast("NodeProxy", _Node("anchor", 1))
    anchor_chain = _Chain([anchor], id=1)
    cast("_Node", anchor).chain = anchor_chain

    compatible_nodes = pair_active._get_branch_chain_compatible_nodes(
        [anchor], anchor
    )

    assert compatible_nodes is None


def test_branch_chain_compatible_nodes_return_empty_without_distinct_branch() -> None:
    upper = cast("NodeProxy", _Node("upper", 1))
    anchor = cast("NodeProxy", _Node("anchor", 2))
    anchor_chain = _Chain([upper, anchor], id=1)
    cast("_Node", upper).chain = anchor_chain
    cast("_Node", anchor).chain = anchor_chain

    compatible_nodes = pair_active._get_branch_chain_compatible_nodes(
        [anchor, upper], anchor
    )

    assert compatible_nodes is None


def test_branch_chain_compatible_nodes_return_empty_without_candidate_matches() -> None:
    anchor, upper, above, _, _, _, _, _ = _branch_chain_fixture()

    compatible_nodes = pair_active._get_branch_chain_compatible_nodes(
        [anchor, upper, above], anchor
    )

    assert compatible_nodes is None


def test_phase_pipeline_uses_data_arguments_instead_of_rule_callbacks() -> None:
    tree = ast.parse(inspect.getsource(pair_active))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    phase_names = [name for name in functions if name.startswith("phase_")]
    stage_helpers = {
        "_find_candidate_node",
        "_get_compatible_nodes",
        "_form_candidate_pairs",
    }

    for phase_name in phase_names:
        phase = functions[phase_name]
        assert not any(
            isinstance(node, ast.Lambda)
            for node in ast.walk(phase)
        )
        final_statement = phase.body[-1]
        assert isinstance(final_statement, ast.Return)
        assert isinstance(final_statement.value, ast.Name)
        assert final_statement.value.id == "result"
        assert any(
            isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Name)
            and node.left.id == "result"
            and any(isinstance(operator, ast.Is) for operator in node.ops)
            and any(
                isinstance(comparator, ast.Constant)
                and comparator.value is None
                for comparator in node.comparators
            )
            for node in ast.walk(phase)
        )
        assert not any(
            isinstance(node, ast.Return) and isinstance(node.value, ast.Call)
            for node in ast.walk(phase)
        )

    function_names = set(functions)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in stage_helpers:
            continue
        assert all(
            not isinstance(argument, ast.Lambda)
            and not (
                isinstance(argument, ast.Name)
                and argument.id in function_names
            )
            for argument in node.args
        )


def test_each_phase_logs_selected_pair_before_returning() -> None:
    tree = ast.parse(inspect.getsource(pair_active))
    expected_message = (
        "f'selected pair: {result[0].filename}({result[0].link_count}) vs "
        "{result[1].filename}({result[1].link_count})'"
    )
    phases = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("phase_")
    ]

    for phase in phases:
        log_statement, return_statement = phase.body[-2:]
        assert isinstance(log_statement, ast.Expr)
        assert isinstance(log_statement.value, ast.Call)
        call = log_statement.value
        assert isinstance(call.func, ast.Attribute)
        assert isinstance(call.func.value, ast.Name)
        assert call.func.value.id == "logger"
        assert call.func.attr == "debug"
        assert ast.unparse(call.args[0]) == expected_message
        assert [(keyword.arg, ast.unparse(keyword.value)) for keyword in call.keywords] == [
            ("start_timer", "_start")
        ]
        assert isinstance(return_statement, ast.Return)
        assert isinstance(return_statement.value, ast.Name)
        assert return_statement.value.id == "result"


def test_phases_do_not_emit_temporary_step_timing_logs() -> None:
    assert "phase step" not in inspect.getsource(pair_active)


def test_pair_active_calls_assign_inner_results_before_outer_calls() -> None:
    tree = ast.parse(inspect.getsource(pair_active))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
        assert not any(isinstance(argument, ast.Call) for argument in arguments), (
            f"nested call passed to {ast.unparse(node.func)} at line {node.lineno}"
        )
