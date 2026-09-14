"""Tests for collapse_comparisons in domain/comparison/algorithm/graph_helpers.py."""

from __future__ import annotations

import pytest

from comfyui_image_scorer.domain.comparison.algorithm.graph_helpers import (
    collapse_comparisons,
)


def _make_row(
    filename_a: str,
    filename_b: str,
    winner: str,
    timestamp: str = "2026-08-31T00:00:00Z",
    comparison_id: int = 1,
) -> dict:
    return {
        "filename_a": filename_a,
        "filename_b": filename_b,
        "winner": winner,
        "timestamp": timestamp,
        "id": comparison_id,
    }


@pytest.fixture
def valid_filenames() -> set[str]:
    return {"a.png", "b.png", "c.png", "d.png"}


class TestMissingNodes:
    def test_removes_comparisons_with_missing_winner(self, valid_filenames: set[str]) -> None:
        rows = [_make_row("missing.png", "b.png", "a.png")]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert survivors == []
        assert counts["missing_nodes_removed"] == 1

    def test_removes_comparisons_with_missing_loser(self, valid_filenames: set[str]) -> None:
        rows = [_make_row("a.png", "missing.png", "a.png")]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert survivors == []
        assert counts["missing_nodes_removed"] == 1

    def test_keeps_all_valid_comparisons(self, valid_filenames: set[str]) -> None:
        rows = [_make_row("a.png", "b.png", "a.png")]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert len(survivors) == 1
        assert counts["missing_nodes_removed"] == 0

    def test_mixed_valid_and_invalid(self, valid_filenames: set[str]) -> None:
        rows = [
            _make_row("a.png", "b.png", "a.png", comparison_id=1),
            _make_row("missing.png", "b.png", "a.png", comparison_id=2),
        ]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert len(survivors) == 1
        assert counts["missing_nodes_removed"] == 1


class TestSelfLinks:
    def test_removes_self_links(self, valid_filenames: set[str]) -> None:
        rows = [_make_row("a.png", "a.png", "a.png")]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert survivors == []
        assert counts["self_links_removed"] == 1

    def test_keeps_valid_comparisons(self, valid_filenames: set[str]) -> None:
        rows = [_make_row("a.png", "b.png", "a.png")]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert len(survivors) == 1
        assert counts["self_links_removed"] == 0


class TestSameDirectionDuplicates:
    def test_keeps_latest_same_winner(self, valid_filenames: set[str]) -> None:
        rows = [
            _make_row("a.png", "b.png", "a.png", timestamp="2026-08-30T00:00:00Z", comparison_id=1),
            _make_row("a.png", "b.png", "a.png", timestamp="2026-08-31T00:00:00Z", comparison_id=2),
        ]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert len(survivors) == 1
        assert survivors[0]["id"] == 2
        assert counts["same_direction_duplicates_removed"] == 1

    def test_keeps_latest_when_different_winners(self, valid_filenames: set[str]) -> None:
        rows = [
            _make_row("a.png", "b.png", "a.png", timestamp="2026-08-30T00:00:00Z", comparison_id=1),
            _make_row("a.png", "b.png", "b.png", timestamp="2026-08-31T00:00:00Z", comparison_id=2),
        ]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert len(survivors) == 1
        assert survivors[0]["id"] == 2
        assert counts["contradictions_removed"] == 1

    def test_keeps_only_latest_when_three_same_winner(self, valid_filenames: set[str]) -> None:
        rows = [
            _make_row("a.png", "b.png", "a.png", timestamp=f"2026-08-{d:02d}T00:00:00Z", comparison_id=d)
            for d in range(1, 4)
        ]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert len(survivors) == 1
        assert survivors[0]["id"] == 3
        assert counts["same_direction_duplicates_removed"] == 2


class TestContradictions:
    def test_resolves_contradiction_to_latest(self, valid_filenames: set[str]) -> None:
        rows = [
            _make_row("a.png", "b.png", "a.png", timestamp="2026-08-30T00:00:00Z", comparison_id=1),
            _make_row("a.png", "b.png", "b.png", timestamp="2026-08-31T00:00:00Z", comparison_id=2),
        ]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert len(survivors) == 1
        assert survivors[0]["id"] == 2
        assert counts["contradictions_removed"] == 1

    def test_no_contradiction_when_same_winner(self, valid_filenames: set[str]) -> None:
        rows = [
            _make_row("a.png", "b.png", "a.png", timestamp="2026-08-30T00:00:00Z", comparison_id=1),
            _make_row("a.png", "b.png", "a.png", timestamp="2026-08-31T00:00:00Z", comparison_id=2),
        ]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert len(survivors) == 1
        assert counts["contradictions_removed"] == 0

    def test_keeps_one_per_direction(self, valid_filenames: set[str]) -> None:
        rows = [
            _make_row("a.png", "b.png", "a.png", comparison_id=1),
            _make_row("a.png", "b.png", "b.png", comparison_id=2),
            _make_row("a.png", "b.png", "a.png", comparison_id=3),
        ]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert len(survivors) == 1


class TestFullPipeline:
    def test_empty_input(self, valid_filenames: set[str]) -> None:
        survivors, counts = collapse_comparisons([], valid_filenames)
        assert survivors == []
        assert all(v == 0 for v in counts.values())

    def test_all_rules_apply(self, valid_filenames: set[str]) -> None:
        rows = [
            _make_row("missing.png", "b.png", "a.png", comparison_id=1),
            _make_row("a.png", "a.png", "a.png", comparison_id=2),
            _make_row("a.png", "b.png", "a.png", timestamp="2026-08-30T00:00:00Z", comparison_id=3),
            _make_row("a.png", "b.png", "a.png", timestamp="2026-08-31T00:00:00Z", comparison_id=4),
            _make_row("a.png", "b.png", "b.png", timestamp="2026-08-31T00:00:00Z", comparison_id=5),
        ]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert counts["missing_nodes_removed"] == 1
        assert counts["self_links_removed"] == 1
        assert counts["same_direction_duplicates_removed"] == 1
        assert counts["contradictions_removed"] == 1
        assert counts["kept"] == 1
        assert survivors[0]["id"] == 5

    def test_deterministic_sorting(self, valid_filenames: set[str]) -> None:
        rows = [
            _make_row("a.png", "c.png", "a.png", timestamp="2026-08-31T00:00:00Z", comparison_id=2),
            _make_row("a.png", "c.png", "a.png", timestamp="2026-08-30T00:00:00Z", comparison_id=1),
        ]
        survivors, counts = collapse_comparisons(rows, valid_filenames)
        assert len(survivors) == 1
        assert survivors[0]["id"] == 2
        assert counts["same_direction_duplicates_removed"] == 1
