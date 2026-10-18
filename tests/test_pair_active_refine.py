"""Opponent selection in `phase_uncertainty_refine`.

The refinement phase serves the most uncertain image that is not already in the
reference pool. Two properties matter and are asserted here:

* the sigma threshold decides *who gets refined*, not who may be an opponent.
  Applying it to the opponent side left only 3% of a real pool usable.
* opponents are drawn least-compared-first so refinement traffic spreads over
  the pool instead of piling onto whichever members sit far from the node.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from comfyui_image_scorer.domain.comparison.algorithm.pair_active import (
    phase_uncertainty_refine,
)
from comfyui_image_scorer.domain.ports.graph import CrystalGraphPort
from comfyui_image_scorer.domain.graph.node_proxy import NodeProxy

SIGMA_THRESHOLD = 3.5
INSERTION_TARGET = 3


@dataclass
class _Stub:
    filename: str
    link_count: int
    sigma: float
    mu: float = 25.0

    @property
    def trueskill_score(self) -> float:
        return self.mu - 3.0 * self.sigma

    @property
    def mu_skill(self) -> float:
        return self.mu

    @property
    def sigma_uncertainty(self) -> float:
        return self.sigma


class _Graph:
    """Only are_in_same_path is consulted by this phase."""

    def __init__(self, same: set[tuple[str, str]] | None = None) -> None:
        self._same = same or set()

    def are_in_same_path(self, a: str, b: str) -> bool:
        return (a, b) in self._same or (b, a) in self._same


def _nodes(stubs: list[_Stub]) -> list[NodeProxy]:
    return [cast("NodeProxy", stub) for stub in stubs]


def _graph(same: set[tuple[str, str]] | None = None) -> CrystalGraphPort:
    # The phase takes a full CrystalGraphPort but only calls are_in_same_path,
    # so a narrow stand-in is passed through a cast instead of a real graph.
    return cast("CrystalGraphPort", _Graph(same))


def _refine(
    stubs: list[_Stub],
    pool: set[str],
    pairs: set[tuple[str, str]] | None = None,
):
    return phase_uncertainty_refine(
        _nodes(stubs), pool, pairs or set(), _graph()
    )


class TestRefineOpponentSelection:
    def test_converged_pool_members_are_usable_as_opponents(self) -> None:
        """The sigma threshold gates node_a, never the opponents."""
        target = _Stub("target", 6, SIGMA_THRESHOLD + 1.0)
        pool = [_Stub(f"p{i}", 20, 2.0) for i in range(4)]
        assert all(s.sigma < SIGMA_THRESHOLD for s in pool), "pool is converged"

        result = _refine([target, *pool], {s.filename for s in pool})

        assert result is not None, "converged pool members must still be usable"
        assert result[0].filename == "target"
        assert result[1].filename.startswith("p")

    def test_most_uncertain_non_pool_image_is_refined(self) -> None:
        target = _Stub("target", 6, 4.0)
        also_uncertain = _Stub("other", 7, 4.8)
        pool = [_Stub("p0", 20, 2.0)]

        result = _refine(
            [target, also_uncertain, *pool], {"p0"}
        )

        assert result is not None
        assert result[0].filename == "other", "highest sigma should be refined"

    def test_pool_images_are_never_refined_themselves(self) -> None:
        target = _Stub("target", 6, 4.0)
        pool = [_Stub("p0", 20, 4.9)]

        result = _refine([target, *pool], {"p0"})

        assert result is not None
        assert result[0].filename == "target"

    def test_least_compared_pool_member_is_chosen(self) -> None:
        # The nearest score belongs to the busiest member; least-used must win.
        target = _Stub("target", 6, 4.0, mu=25.0)
        busy = _Stub("busy", 40, 2.0, mu=25.0)
        quiet = _Stub("quiet", 20, 2.0, mu=27.0)
        pool = {busy.filename, quiet.filename}

        result = _refine([target, busy, quiet], pool)

        assert result is not None
        assert result[1].filename != "busy"
        assert result[1].filename in pool

    def test_score_gap_breaks_link_count_ties(self) -> None:
        target = _Stub("target", 6, 4.0, mu=25.0)
        near = _Stub("near", 20, 2.0, mu=25.1)
        far = _Stub("far", 20, 2.0, mu=28.0)
        pool = {near.filename, far.filename}

        result = _refine([target, near, far], pool)

        assert result is not None
        assert result[1].filename == "near"

    def test_same_path_opponents_are_skipped(self) -> None:
        target = _Stub("target", 6, 4.0)
        blocked = _Stub("blocked", 10, 2.0)
        allowed = _Stub("allowed", 30, 2.0)

        result = phase_uncertainty_refine(
            _nodes([target, blocked, allowed]),
            {"blocked", "allowed"},
            set(),
            _graph({("target", "blocked")}),
        )

        assert result is not None
        assert result[1].filename == "allowed"

    def test_returns_none_without_an_eligible_target(self) -> None:
        # Below the insertion target, so never a refinement candidate.
        fresh = _Stub("fresh", 1, 9.0)
        pool = [_Stub("p0", 20, 2.0)]

        assert _refine([fresh, *pool], {"p0"}) is None

    def test_returns_none_without_a_pool(self) -> None:
        target = _Stub("target", 6, 4.0)

        assert _refine([target], set()) is None

    def test_load_is_spread_across_the_pool(self) -> None:
        pool = [_Stub(f"p{i:02d}", 20 + i, 2.0) for i in range(8)]
        pool_set = {s.filename for s in pool}
        index = {s.filename: s for s in pool}

        for _ in range(len(pool) * 2):
            target = _Stub("target", 6, 4.0)
            result = _refine([target, *pool], pool_set)
            assert result is not None
            index[result[1].filename].link_count += 1

        counts = sorted(s.link_count for s in pool)
        assert counts[-1] - counts[0] <= 2, (
            f"pool load spread is {counts[-1] - counts[0]}"
        )