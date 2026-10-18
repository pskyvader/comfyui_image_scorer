"""Opponent selection in domain/comparison/algorithm/pair_active.py.

`phase_anchor_insert` serves images that have not yet been compared much. It
must test those newcomers against the seed pool rather than against each
other, and it must spread its comparisons evenly over the pool instead of
loading the most-comparered members. Both properties are asserted here against
in-memory stubs, with no graph or database involved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from comfyui_image_scorer.domain.comparison.algorithm.pair_active import (
    phase_anchor_insert,
)
from comfyui_image_scorer.domain.graph.node_proxy import NodeProxy


@dataclass
class _Stub:
    """Mutable stand-in for the NodeProxy attributes this phase reads."""

    filename: str
    link_count: int
    score: float


def _nodes(stubs: list[_Stub]) -> list[NodeProxy]:
    # The phase only reads filename, link_count and score. Constructing a real
    # NodeProxy needs a ChainManager, so narrow stubs are passed through a cast
    # rather than building a graph for every test.
    return [cast("NodeProxy", stub) for stub in stubs]


def _newcomer(count: int = 0, score: float = 0.5) -> _Stub:
    return _Stub("new", count, score)


class TestOpponentSelection:
    def test_single_newcomer_is_paired_against_the_pool(self) -> None:
        pool = [_Stub(f"pool{i:02d}", 20, 0.5) for i in range(3)]
        newcomer = _newcomer()
        pool_set = {s.filename for s in pool}

        result = phase_anchor_insert(
            _nodes([newcomer, *pool]), pool_set, set()
        )

        assert result is not None, "one newcomer is enough to produce a pair"
        assert result[0].filename == "new"
        assert result[1].filename in pool_set

    def test_opponent_comes_from_the_seed_pool(self) -> None:
        pool = [_Stub(f"pool{i:02d}", 20, 0.5) for i in range(3)]
        outsiders = [_Stub(f"outsider{i}", 4, 0.5001 * i) for i in range(1, 4)]
        newcomer = _newcomer()
        pool_set = {s.filename for s in pool}

        result = phase_anchor_insert(
            _nodes([newcomer, *pool, *outsiders]), pool_set, set()
        )

        assert result is not None
        assert result[1].filename in pool_set

    def test_least_used_pool_member_is_chosen(self) -> None:
        # The nearest score belongs to the busiest member; least-used must win.
        pool = [
            _Stub("busy", 40, 0.50),
            _Stub("mid", 20, 0.62),
            _Stub("quiet", 20, 0.80),
        ]
        newcomer = _newcomer()
        pool_set = {s.filename for s in pool}

        result = phase_anchor_insert(
            _nodes([newcomer, *pool]), pool_set, set()
        )

        assert result is not None
        assert result[1].filename in {"mid", "quiet"}
        assert result[1].filename != "busy"

    def test_score_distance_breaks_link_count_ties(self) -> None:
        pool = [_Stub("near", 20, 0.51), _Stub("far", 20, 0.99)]
        newcomer = _newcomer()
        pool_set = {s.filename for s in pool}

        result = phase_anchor_insert(
            _nodes([newcomer, *pool]), pool_set, set()
        )

        assert result is not None
        assert result[1].filename == "near"

    def test_newcomer_is_never_its_own_opponent(self) -> None:
        pool = [_Stub(f"pool{i:02d}", 20, 0.5) for i in range(3)]
        newcomer = _newcomer()
        pool_set = {newcomer.filename, *(s.filename for s in pool)}

        result = phase_anchor_insert(
            _nodes([newcomer, *pool]), pool_set, set()
        )

        assert result is not None
        assert result[0].filename != result[1].filename

    def test_empty_lane_returns_none(self) -> None:
        pool = [_Stub(f"pool{i:02d}", 20, 0.5) for i in range(3)]
        pool_set = {s.filename for s in pool}

        assert phase_anchor_insert(_nodes(pool), pool_set, set()) is None

    def test_already_compared_opponent_is_skipped(self) -> None:
        pool = [_Stub("pool00", 20, 0.5), _Stub("pool01", 20, 0.5)]
        newcomer = _newcomer()
        pool_set = {s.filename for s in pool}

        result = phase_anchor_insert(
            _nodes([newcomer, *pool]),
            pool_set,
            {("new", "pool00")},
        )

        assert result is not None
        assert result[1].filename == "pool01"

    def test_comparisons_are_spread_evenly_across_the_pool(self) -> None:
        """Ordering by link_count means no pool member runs away with the load."""
        pool = [_Stub(f"pool{i:02d}", 20, 0.5) for i in range(5)]
        pool_set = {s.filename for s in pool}
        newcomer = _newcomer()
        index = {s.filename: s for s in pool}

        for _ in range(len(pool) * 3):
            result = phase_anchor_insert(
                _nodes([newcomer, *pool]), pool_set, set()
            )
            assert result is not None
            index[result[1].filename].link_count += 1

        counts = sorted(s.link_count for s in pool)
        assert counts[-1] - counts[0] <= 1, (
            f"pool load spread is {counts[-1] - counts[0]}, expected at most 1"
        )