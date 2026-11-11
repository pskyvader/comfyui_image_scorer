"""Opponent selection in domain/comparison/algorithm/pair_active.py.

`phase_anchor_insert` serves images that have not yet been compared much. It
must test those newcomers against the seed pool rather than against each
other, and it must spread its comparisons evenly over the pool instead of
loading the most-compared members. Both properties are asserted here against
in-memory stubs, with no graph or database involved.
"""

from __future__ import annotations

from collections import deque
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
from comfyui_image_scorer.domain.comparison.algorithm.pair_active import (
    phase_anchor_insert,
)
from comfyui_image_scorer.domain.graph.node_proxy import NodeProxy
from comfyui_image_scorer.domain.ports.comparison import PairingProcessorPort


@dataclass
class _Stub:
    """Mutable stand-in for the NodeProxy attributes this phase reads."""

    filename: str
    link_count: int
    score: float

    @property
    def position_score(self) -> float:
        return self.score

    @property
    def trueskill_score(self) -> float:
        return self.score

    @property
    def sigma_uncertainty(self) -> float:
        return 10.0


class _FakePairingProcessor:
    def __init__(self) -> None:
        self.recent_images: deque[str] = deque()
        self.recent_lock = Lock()


def _nodes(stubs: list[_Stub]) -> list[NodeProxy]:
    return [cast("NodeProxy", stub) for stub in stubs]


def _newcomer(count: int = 0, score: float = 0.5) -> _Stub:
    return _Stub("new", count, score)


def _anchor_insert(
    nodes: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]] | None = None,
    processor: PairingProcessorPort | None = None,
) -> tuple[NodeProxy, NodeProxy] | None:
    return phase_anchor_insert(
        nodes,
        existing_pair_set or set(),
        processor or cast("PairingProcessorPort", _FakePairingProcessor()),
    )


def _pick_first(nodes: list[object]) -> object:
    return nodes[0]


@pytest.fixture(autouse=True)
def patch_ranking_config(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = {
        "ranking": {
            "seed_percentage": 50,
            "seed_target_comparisons": 50,
            "sigma_range_multiplier": 3.0,
            "insertion_target_comparisons": 0,
            "reserve_count": 1,
            "lru_size": 160,
        }
    }
    monkeypatch.setattr(pair_active, "config", cfg)
    monkeypatch.setattr(pair_candidates, "config", cfg)
    monkeypatch.setattr(pair_opponents, "config", cfg)
    monkeypatch.setattr(pair_pipeline, "config", cfg)
    monkeypatch.setattr(pair_candidates.random, "choice", _pick_first)


class TestOpponentSelection:
    def test_single_newcomer_is_paired_against_the_pool(self) -> None:
        pool = [_Stub(f"pool{i:02d}", 20, 0.5) for i in range(3)]
        newcomer = _newcomer()
        pool_set = {s.filename for s in pool}

        result = _anchor_insert(_nodes([newcomer, *pool]))

        assert result is not None, "one newcomer is enough to produce a pair"
        assert result[0].filename == "new"
        assert result[1].filename in pool_set
        assert result[0] in _nodes([newcomer, *pool])
        assert result[1] in _nodes([newcomer, *pool])

    def test_seed_pool_members_outside_candidates_are_not_opponents(self) -> None:
        newcomer = _newcomer()

        assert _anchor_insert(_nodes([newcomer])) is None

    def test_opponent_comes_from_the_seed_pool(self) -> None:
        pool = [_Stub(f"pool{i:02d}", 20, 0.5) for i in range(3)]
        outsiders = [_Stub(f"outsider{i}", 4, 0.5001 * i) for i in range(1, 4)]
        newcomer = _newcomer()
        pool_set = {s.filename for s in pool}

        result = _anchor_insert(_nodes([newcomer, *pool, *outsiders]))

        assert result is not None
        assert result[1].filename in pool_set

    def test_closest_score_pool_member_is_chosen(self) -> None:
        pool = [
            _Stub("busy", 40, 0.50),
            _Stub("mid", 20, 0.62),
            _Stub("quiet", 20, 0.80),
        ]
        newcomer = _newcomer(score=0.50)

        result = _anchor_insert(_nodes([newcomer, *pool]))

        assert result is not None
        assert result[1].filename == "busy"

    def test_score_distance_breaks_link_count_ties(self) -> None:
        pool = [_Stub("near", 20, 0.51), _Stub("far", 20, 0.99)]
        newcomer = _newcomer()

        result = _anchor_insert(_nodes([newcomer, *pool]))

        assert result is not None
        assert result[1].filename == "near"

    def test_position_score_selects_anchor_when_link_counts_tie(self) -> None:
        lower_position = _newcomer(score=0.2)
        higher_position = _Stub("higher-position", 0, 0.8)
        pool = [_Stub("pool", 20, 0.5)]

        result = _anchor_insert(_nodes([higher_position, lower_position, *pool]))

        assert result is not None
        assert result[0].filename == "new"

    def test_newcomer_is_never_its_own_opponent(self) -> None:
        pool = [_Stub(f"pool{i:02d}", 20, 0.5) for i in range(3)]
        newcomer = _newcomer()

        result = _anchor_insert(_nodes([newcomer, *pool]))

        assert result is not None
        assert result[0].filename != result[1].filename

    def test_empty_lane_returns_none(self) -> None:
        pool = [_Stub(f"pool{i:02d}", 20, 0.5) for i in range(3)]

        assert _anchor_insert(_nodes(pool)) is None

    def test_already_compared_opponent_is_skipped(self) -> None:
        pool = [_Stub("pool00", 20, 0.5), _Stub("pool01", 20, 0.5)]
        newcomer = _newcomer()

        result = _anchor_insert(
            _nodes([newcomer, *pool]),
            {("new", "pool00")},
        )

        assert result is not None
        assert result[1].filename == "pool01"

    def test_comparisons_are_spread_evenly_across_the_pool(self) -> None:
        """Ordering by link_count means no pool member runs away with the load."""
        pool = [_Stub(f"pool{i:02d}", 20, 0.5) for i in range(5)]
        newcomer = _newcomer()
        index = {s.filename: s for s in pool}

        for _ in range(len(pool) * 3):
            result = _anchor_insert(_nodes([newcomer, *pool]))
            assert result is not None
            index[result[1].filename].link_count += 1

        counts = sorted(s.link_count for s in pool)
        assert counts[-1] - counts[0] <= 1, (
            f"pool load spread is {counts[-1] - counts[0]}, expected at most 1"
        )
