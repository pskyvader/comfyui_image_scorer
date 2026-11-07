"""Rating-state sync parity in domain/comparison/comparison_recorder.py.

One comparison updates two images, and each one is persisted twice: once to
the database and once to its companion JSON. Those two writes must carry the
same rating for the same image. The JSON writer once read the loser's sigma
while naming the winner's file, so the winner's sidecar carried an opponent's
uncertainty until the next sync. These tests pin the parity directly rather
than the TrueSkill arithmetic, so they survive a change to the update rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from comfyui_image_scorer.domain.analysis.trueskill import INITIAL_MEAN
from comfyui_image_scorer.domain.comparison.comparison_recorder import (
    ComparisonRecorder,
)
from comfyui_image_scorer.domain.ports.graph import CrystalGraphPort
from comfyui_image_scorer.domain.ports.repository import (
    ComparisonRow,
    ImageRow,
    PathResolver,
)

WINNER = "winner.png"
LOSER = "loser.png"


@dataclass
class SyncCall:
    """One sync_image_metadata_to_json invocation, as the recorder issued it."""

    filename: str
    score: float
    rating_mu: float
    rating_sigma: float
    comparison_count: int
    history_len: int


class FakePathSyncer:
    """Records sync calls instead of touching the filesystem."""

    def __init__(self) -> None:
        self.calls: list[SyncCall] = []

    def sync_image_metadata_to_json(
        self,
        filename: str,
        score: float,
        rating_mu: float,
        rating_sigma: float,
        comparison_count: int,
        all_comparisons: list[ComparisonRow] | None = None,
    ) -> bool:
        self.calls.append(
            SyncCall(
                filename=filename,
                score=score,
                rating_mu=rating_mu,
                rating_sigma=rating_sigma,
                comparison_count=comparison_count,
                history_len=len(all_comparisons or []),
            )
        )
        return True


class _FakeNode:
    """Minimal stand-in for the proxy record_comparison reads .data from."""

    def __init__(self, data: ImageRow) -> None:
        self.data = data


class _FakeLink:
    """Link shape record_comparison reads .data off when building history."""

    def __init__(self, data: ComparisonRow) -> None:
        self.data = data


class FakeGraph:
    """In-memory graph holding the rating rows the recorder persists."""

    def __init__(self, rows: dict[str, ImageRow]) -> None:
        self.rows = rows
        self.links: list[_FakeLink] = []
        self.duplicate_checks: list[tuple[str, str]] = []
        self.touched = False

    def get_node(self, filename: str) -> _FakeNode | None:
        row = self.rows.get(filename)
        return _FakeNode(row) if row is not None else None

    def comparison_exists_for_pair(self, filename_a: str, filename_b: str) -> bool:
        self.duplicate_checks.append((filename_a, filename_b))
        return False

    def add_link(
        self, filename_a: str, filename_b: str, winner: str, timestamp: str
    ) -> int:
        self.links.append(
            _FakeLink(
                {
                    "filename_a": filename_a,
                    "filename_b": filename_b,
                    "winner": winner,
                    "timestamp": timestamp,
                }
            )
        )
        return len(self.links)

    def get_all_links(self) -> list[_FakeLink]:
        return list(self.links)

    def update_image_rating_state(
        self,
        filename: str,
        score: float,
        rating_mu: float,
        rating_sigma: float,
        comparison_count: int,
        touch_timestamp: bool,
    ) -> bool:
        self.touched = self.touched or touch_timestamp
        row = self.rows[filename]
        row["score"] = score
        row["rating_mu"] = rating_mu
        row["rating_sigma"] = rating_sigma
        row["comparison_count"] = comparison_count
        return True


def _row(filename: str, mu: float, sigma: float) -> ImageRow:
    return cast(
        ImageRow,
        {
            "filename": filename,
            "score": 0.5,
            "rating_mu": mu,
            "rating_sigma": sigma,
            "comparison_count": 0,
            "last_compared_at": None,
            "ranking_generation": 0,
            "prompt_tags": None,
        },
    )


@pytest.fixture
def recorded() -> tuple[FakeGraph, FakePathSyncer]:
    """Two images whose sigmas diverge after one comparison.

    Starting values are chosen so the update produces clearly different
    uncertainties; otherwise a win/lose swap could satisfy the parity assert
    by coincidence and the test would pass against the bug it guards.
    """
    graph = FakeGraph(
        {
            WINNER: _row(WINNER, INITIAL_MEAN + 4.0, 6.0),
            LOSER: _row(LOSER, INITIAL_MEAN - 2.0, 7.5),
        }
    )
    syncer = FakePathSyncer()
    # ComparisonRecorder only calls the port methods below; the ports are
    # large Protocols, so narrow stand-ins are passed through a cast rather
    # than re-declared in full.
    recorder = ComparisonRecorder(
        path_syncer=cast(PathResolver, syncer),
        graph_service=cast(CrystalGraphPort, graph),
    )
    assert recorder.record_comparison(WINNER, LOSER, WINNER)
    return graph, syncer


Recorded = tuple[FakeGraph, FakePathSyncer]


class TestRatingStateParity:
    """The rating written to each image's JSON must equal the rating written
    to its database row. Both writes read the same float out of the same
    dict, so exact equality is the correct comparison here.
    """

    def test_synced_sigma_matches_persisted_sigma_per_image(
        self, recorded: Recorded
    ) -> None:
        graph, syncer = recorded
        by_name = {call.filename: call for call in syncer.calls}

        assert set(by_name) == {WINNER, LOSER}
        for filename, call in by_name.items():
            assert call.rating_sigma == graph.rows[filename]["rating_sigma"], (
                f"{filename} JSON sigma disagrees with its database sigma"
            )

    def test_the_two_images_have_distinct_sigmas(self, recorded: Recorded) -> None:
        graph, _ = recorded
        assert graph.rows[WINNER]["rating_sigma"] != graph.rows[LOSER]["rating_sigma"]

    def test_synced_mu_score_and_count_match_persisted_values(
        self, recorded: Recorded
    ) -> None:
        graph, syncer = recorded
        by_name = {call.filename: call for call in syncer.calls}

        for filename, call in by_name.items():
            row = graph.rows[filename]
            assert call.rating_mu == row["rating_mu"]
            assert call.score == row["score"]
            assert call.comparison_count == row["comparison_count"]

    def test_winner_is_not_given_the_loser_sigma(self, recorded: Recorded) -> None:
        graph, syncer = recorded
        by_name = {call.filename: call for call in syncer.calls}

        assert by_name[WINNER].rating_sigma != by_name[LOSER].rating_sigma
        assert by_name[LOSER].rating_sigma == graph.rows[LOSER]["rating_sigma"]
