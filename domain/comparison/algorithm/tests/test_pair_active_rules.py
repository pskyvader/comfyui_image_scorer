"""Tests for extracted pair-phase selection rules."""

from __future__ import annotations

import ast
from collections import deque
import inspect
from dataclasses import dataclass
from threading import Lock
from typing import cast

import pytest

from comfyui_image_scorer.domain.comparison.algorithm import (
    pair_active,
    pair_candidates,
    pair_opponents,
    pair_pipeline,
)
from comfyui_image_scorer.domain.comparison.algorithm.history_collapse import (
    canonicalize_pair,
)
from comfyui_image_scorer.domain.graph.node_proxy import NodeProxy
from comfyui_image_scorer.domain.ports.comparison import PairingProcessorPort
from comfyui_image_scorer.domain.ports.graph import CrystalGraphPort


@dataclass(eq=False)
class _Node:
    filename: str
    link_count: int
    trueskill_score: float = 0.5
    sigma_uncertainty: float = 10.0
    score: float = 0.5
    position: int = 50
    chain: _Chain | None = None
    known_better_count: int = 0
    known_worse_count: int = 0

    @property
    def mu_skill(self) -> float:
        return self.score

    @property
    def position_score(self) -> int:
        return self.position

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


@dataclass(eq=False)
class _CountNode:
    filename: str
    wins: int = 0
    losses: int = 0
    trueskill_score: float = 0.5
    sigma_uncertainty: float = 10.0
    link_count: int = 0

    def get_links(
        self, worse_than: bool = False, better_than: bool = False
    ) -> list[_CountNode]:
        if worse_than:
            return [self] * self.wins
        if better_than:
            return [self] * self.losses
        return [self] * (self.wins + self.losses)


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

    def get_position(self, node: NodeProxy) -> int | None:
        if node in self.nodes:
            return self.nodes.index(node)
        return None


class _Graph:
    def __init__(
        self, chains: list[_Chain], node_count: int | None = None
    ) -> None:
        self.chains = chains
        self._node_count = (
            node_count
            if node_count is not None
            else len({node.filename for chain in chains for node in chain.nodes})
        )

    def get_node_count(self) -> int:
        return self._node_count

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

    def are_in_same_path(self, filename_a: str, filename_b: str) -> bool:
        return filename_a == filename_b

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


class _SamePathGraph(_Graph):
    """Graph variant that reports one specific filename pair as same-path."""

    def are_in_same_path(self, filename_a: str, filename_b: str) -> bool:
        return {filename_a, filename_b} == {"best-below", "best-above"}


class _FakePairingProcessor:
    def __init__(self) -> None:
        self.recent_images: deque[str] = deque()
        self.recent_lock = Lock()


def _processor() -> PairingProcessorPort:
    return cast("PairingProcessorPort", _FakePairingProcessor())


def _nodes(*values: tuple[str, int]) -> list[NodeProxy]:
    return [
        cast("NodeProxy", _Node(filename, link_count))
        for filename, link_count in values
    ]


def _middle_node(
    filename: str, known_better: int, known_worse: int
) -> NodeProxy:
    return cast(
        "NodeProxy",
        _Node(
            filename,
            known_better + known_worse,
            known_better_count=known_better,
            known_worse_count=known_worse,
        ),
    )


def _settler_fixture() -> tuple[
    NodeProxy,
    NodeProxy,
    NodeProxy,
    NodeProxy,
    NodeProxy,
    _Chain,
    _Chain,
]:
    upper = cast("NodeProxy", _Node("upper", 0))
    anchor = cast(
        "NodeProxy", _Node("anchor", 1, trueskill_score=0.5)
    )
    above = cast("NodeProxy", _Node("above", 3))
    first_below = cast(
        "NodeProxy", _Node("first-below", 2, trueskill_score=0.1)
    )
    second_below = cast(
        "NodeProxy", _Node("second-below", 2, trueskill_score=0.49)
    )
    small_chain = _Chain([upper, anchor], id=1)
    long_chain = _Chain([above, first_below, second_below], id=2)
    cast("_Node", upper).chain = small_chain
    cast("_Node", anchor).chain = small_chain
    cast("_Node", above).chain = long_chain
    cast("_Node", first_below).chain = long_chain
    cast("_Node", second_below).chain = long_chain
    return (
        upper,
        anchor,
        above,
        first_below,
        second_below,
        small_chain,
        long_chain,
    )


def _config() -> dict[str, dict[str, object]]:
    return {
        "ranking": {
            "seed_percentage": 50,
            "seed_target_comparisons": 5,
            "sigma_range_multiplier": 3.0,
            "insertion_target_comparisons": 0,
            "reserve_count": 1,
            "lru_size": 160,
            "minimum_chains_for_pairing": 2,
            "chain_length_threshold": 10,
        }
    }


def _pick_first_node(nodes: list[NodeProxy]) -> NodeProxy:
    return nodes[0]


def _zero_pool_index(_pool_size: int) -> int:
    return 0


@pytest.fixture(autouse=True)
def patch_config(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _config()
    monkeypatch.setattr(pair_active, "config", cfg)
    monkeypatch.setattr(pair_candidates, "config", cfg)
    monkeypatch.setattr(pair_opponents, "config", cfg)
    monkeypatch.setattr(pair_pipeline, "config", cfg)


def test_seed_coverage_skips_when_ready_pool_reaches_target() -> None:
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
    monkeypatch.setattr(pair_active.random, "choice", _pick_first_node)
    candidates = _nodes(("most-ready", 4), ("less-ready", 2), ("over-target", 6))

    result = pair_active.phase_seed_coverage(candidates, set(), [], 10)

    assert result == (candidates[0], candidates[1])


def test_exact_count_selector_counts_wins_for_bottom_pool_and_allows_orphans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pair_active.random, "randrange", _zero_pool_index)
    orphan = _CountNode("orphan")
    never_won = _CountNode("never-won", wins=0, losses=2, trueskill_score=0.4)
    double_winner = _CountNode("double-winner", wins=2, losses=0)
    candidates = [
        cast("NodeProxy", orphan),
        cast("NodeProxy", never_won),
        cast("NodeProxy", double_winner),
    ]

    result = pair_active.select_exact_count_pair(
        candidates, set(), _processor(), bottom=True, count=0, closest=False, retry=0
    )

    assert result == (candidates[0], candidates[1])


def test_exact_count_selector_counts_losses_for_top_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pair_active.random, "randrange", _zero_pool_index)
    never_lost_a = _CountNode("a", wins=3, losses=0)
    never_lost_b = _CountNode("b", wins=1, losses=0)
    single_loss = _CountNode("c", wins=1, losses=1)
    candidates = [
        cast("NodeProxy", never_lost_a),
        cast("NodeProxy", never_lost_b),
        cast("NodeProxy", single_loss),
    ]

    result = pair_active.select_exact_count_pair(
        candidates, set(), _processor(), bottom=False, count=0, closest=False, retry=0
    )

    assert result == (candidates[0], candidates[1])


def test_exact_count_selector_returns_none_when_pool_too_small() -> None:
    candidates = [cast("NodeProxy", _CountNode("lonely"))]

    result = pair_active.select_exact_count_pair(
        candidates, set(), _processor(), bottom=True, count=0, closest=False, retry=0
    )

    assert result is None


def test_exact_count_selector_skips_existing_pairs_without_marking_recent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pair_active.random, "randrange", _zero_pool_index)
    processor = _FakePairingProcessor()
    candidates = [
        cast("NodeProxy", _CountNode("a")),
        cast("NodeProxy", _CountNode("b")),
        cast("NodeProxy", _CountNode("c")),
    ]
    existing_pair_set = {canonicalize_pair("a", "b")}

    result = pair_active.select_exact_count_pair(
        candidates,
        existing_pair_set,
        cast("PairingProcessorPort", processor),
        bottom=True,
        count=0,
        closest=False,
        retry=0,
    )

    assert result == (candidates[0], candidates[2])
    assert list(processor.recent_images) == []


def test_exact_count_selector_retries_then_falls_back_widest_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pair_active.random, "randrange", _zero_pool_index)
    processor = _FakePairingProcessor()
    uncertain = _CountNode(
        "uncertain", trueskill_score=0.5, sigma_uncertainty=0.01
    )
    opponent = _CountNode("opponent", trueskill_score=0.1)
    candidates = [cast("NodeProxy", uncertain), cast("NodeProxy", opponent)]

    result = pair_active.select_exact_count_pair(
        candidates,
        set(),
        cast("PairingProcessorPort", processor),
        bottom=True,
        count=0,
        closest=False,
        retry=0,
    )

    assert result == (candidates[0], candidates[1])
    assert list(processor.recent_images) == ["uncertain"]


def test_chain_small_pairs_small_chain_extreme_with_long_chain_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upper, anchor, _, first_below, second_below, small_chain, long_chain = (
        _settler_fixture()
    )
    candidates = [upper, anchor, first_below, second_below]
    graph = _Graph([small_chain, long_chain])
    cfg = _config()
    cfg["ranking"]["chain_length_threshold"] = 2
    monkeypatch.setattr(pair_active, "config", cfg)
    monkeypatch.setattr(pair_active.random, "randrange", _zero_pool_index)

    result = pair_active.phase_chain_small(
        candidates, set(), cast("CrystalGraphPort", graph), _processor()
    )

    assert result == (candidates[0], candidates[3])


def test_chain_small_returns_none_without_long_chains() -> None:
    upper, anchor, above, first_below, second_below, small_chain, long_chain = (
        _settler_fixture()
    )
    candidates = [upper, anchor, above, first_below, second_below]
    graph = _Graph([small_chain, long_chain])

    result = pair_active.phase_chain_small(
        candidates, set(), cast("CrystalGraphPort", graph), _processor()
    )

    assert result is None


def test_chain_small_marks_recent_when_every_pair_is_filtered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, anchor, _, first_below, _, small_chain, long_chain = _settler_fixture()
    candidates = [anchor, first_below]
    graph = _Graph([small_chain, long_chain])
    cfg = _config()
    cfg["ranking"]["chain_length_threshold"] = 2
    monkeypatch.setattr(pair_active, "config", cfg)
    monkeypatch.setattr(pair_active.random, "randrange", _zero_pool_index)
    processor = _FakePairingProcessor()
    existing_pair_set = {canonicalize_pair("anchor", "first-below")}

    result = pair_active.phase_chain_small(
        candidates,
        existing_pair_set,
        cast("CrystalGraphPort", graph),
        cast("PairingProcessorPort", processor),
    )

    assert result is None
    assert list(processor.recent_images) == ["anchor"]


def test_chain_middle_pairs_flankers_around_target_rank() -> None:
    below = _middle_node("below", 2, 3)
    at_rank = _middle_node("at-rank", 3, 3)
    too_losing = _middle_node("too-losing", 1, 5)
    too_winning = _middle_node("too-winning", 4, 2)
    candidates = [below, at_rank, too_losing, too_winning]
    graph = _Graph([], node_count=7)

    result = pair_active.phase_chain_middle(
        candidates, set(), cast("CrystalGraphPort", graph)
    )

    assert result == (candidates[0], candidates[1])


def test_chain_middle_returns_none_when_middle_resolved() -> None:
    only_candidate = _middle_node("only", 2, 3)
    disqualified = _middle_node("disqualified", 4, 2)
    candidates = [only_candidate, disqualified]
    graph = _Graph([], node_count=7)

    result = pair_active.phase_chain_middle(
        candidates, set(), cast("CrystalGraphPort", graph)
    )

    assert result is None


def test_chain_middle_skips_blocked_flanker_pair() -> None:
    best_below = _middle_node("best-below", 2, 3)
    other_below = _middle_node("other-below", 1, 3)
    best_above = _middle_node("best-above", 3, 3)
    other_above = _middle_node("other-above", 3, 2)
    candidates = [best_below, other_below, best_above, other_above]
    graph = _SamePathGraph([], node_count=7)

    result = pair_active.phase_chain_middle(
        candidates, set(), cast("CrystalGraphPort", graph)
    )

    assert result == (candidates[0], candidates[3])


def test_chain_middle_pairs_most_informed_candidates_when_one_sided() -> None:
    pinned = _middle_node("pinned", 3, 3)
    narrow = _middle_node("narrow", 3, 2)
    wide = _middle_node("wide", 3, 1)
    candidates = [pinned, narrow, wide]
    graph = _Graph([], node_count=7)

    result = pair_active.phase_chain_middle(
        candidates, set(), cast("CrystalGraphPort", graph)
    )

    assert result == (candidates[0], candidates[1])


def test_phase_pipeline_uses_data_arguments_instead_of_rule_callbacks() -> None:
    tree = ast.parse(inspect.getsource(pair_active))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    phase_names = [name for name in functions if name.startswith("phase_")]
    stage_helpers = {
        "get_compatible_nodes",
        "form_candidate_pairs",
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
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
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
        assert isinstance(call.func, ast.Name)
        assert call.func.id == "_log_selected_pair"
        assert [ast.unparse(arg) for arg in call.args] == ["result", "_start"]
        assert isinstance(return_statement, ast.Return)
        assert isinstance(return_statement.value, ast.Name)
        assert return_statement.value.id == "result"

    log_func = functions["_log_selected_pair"]
    log_stmt = log_func.body[1]
    assert isinstance(log_stmt, ast.Expr)
    log_call = log_stmt.value
    assert isinstance(log_call, ast.Call)
    assert isinstance(log_call.func, ast.Attribute)
    assert log_call.func.attr == "debug"
    assert ast.unparse(log_call.args[0]) == expected_message
    assert [(keyword.arg, ast.unparse(keyword.value)) for keyword in log_call.keywords] == [
        ("start_timer", "_start")
    ]


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
