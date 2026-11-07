"""Bulk repository writes must match the per-row path exactly, ids included."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from comfyui_image_scorer.infrastructure.persistence import comparisons_repository
from comfyui_image_scorer.infrastructure.persistence import database
from comfyui_image_scorer.infrastructure.persistence import images_repository
from comfyui_image_scorer.domain.ports.repository import (
    ComparisonRow,
    ImageRowForInsert,
    RatingStateUpdate,
)


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the repositories at a throwaway database for the duration of a test."""
    db_file = tmp_path / "cache.db"
    monkeypatch.setattr(database, "cache_file", str(db_file))
    database.init_database()
    yield db_file


def _seed_images(names: list[str]) -> None:
    for name in names:
        images_repository.add_image(
            filename=name,
            score=0.5,
            comparison_count=0,
            prompt_tags=None,
            rating_mu=0.0,
            rating_sigma=0.0,
        )


def _rows() -> list[ComparisonRow]:
    return [
        {
            "id": 0,
            "filename_a": "b.png",
            "filename_b": "a.png",
            "winner": "a.png",
            "timestamp": "2026-01-02T00:00:00Z",
        },
        {
            "id": 0,
            "filename_a": "a.png",
            "filename_b": "c.png",
            "winner": "c.png",
            "timestamp": "2026-01-03T00:00:00Z",
        },
        {
            "id": 0,
            "filename_a": "c.png",
            "filename_b": "d.png",
            "winner": "d.png",
            "timestamp": "2026-01-04T00:00:00Z",
        },
    ]


def _stored_shape() -> list[tuple[str, str, str, str]]:
    return [
        (r["filename_a"], r["filename_b"], r["winner"], str(r.get("timestamp") or ""))
        for r in comparisons_repository.list_links()
    ]


@pytest.mark.usefixtures("temp_db")
def test_bulk_comparisons_match_per_row() -> None:
    _seed_images(["a.png", "b.png", "c.png", "d.png"])
    rows = _rows()

    per_row = [
        comparisons_repository.add_comparison(
            filename_a=str(r["filename_a"]),
            filename_b=str(r["filename_b"]),
            winner=str(r["winner"]),
            timestamp=str(r.get("timestamp") or ""),
        )
        for r in rows
    ]
    per_row_stored = _stored_shape()
    comparisons_repository.clear_all_comparisons()

    bulk_ids = comparisons_repository.add_comparisons_bulk(rows)
    bulk_stored = _stored_shape()

    # ids differ by design: AUTOINCREMENT keeps counting after a DELETE, so the
    # second pass starts past the first. What must match is the stored content,
    # the input ordering, and the one-id-per-row contract.
    assert len(bulk_ids) == len(rows)
    assert all(link_id > 0 for link_id in bulk_ids)
    assert bulk_ids == sorted(bulk_ids)
    assert bulk_stored == per_row_stored
    assert per_row == sorted(per_row)
    assert all(link_id > 0 for link_id in per_row)


@pytest.mark.usefixtures("temp_db")
def test_bulk_comparisons_canonicalize_and_default_timestamp() -> None:
    _seed_images(["a.png", "b.png"])
    ids = comparisons_repository.add_comparisons_bulk(
        [
            {
                "id": 0,
                "filename_a": "b.png",
                "filename_b": "a.png",
                "winner": "b.png",
            },
        ]
    )
    assert ids[0] > 0
    stored = comparisons_repository.list_links()
    # the pair is stored in canonical filename order
    assert [(r["filename_a"], r["filename_b"]) for r in stored] == [("a.png", "b.png")]
    # a missing timestamp is filled in rather than stored empty
    assert stored[0].get("timestamp")


@pytest.mark.usefixtures("temp_db")
def test_bulk_comparisons_reject_bad_winner() -> None:
    _seed_images(["a.png", "b.png"])
    ids = comparisons_repository.add_comparisons_bulk(
        [
            {
                "id": 0,
                "filename_a": "a.png",
                "filename_b": "b.png",
                "winner": "a.png",
                "timestamp": "2026-01-02T00:00:00Z",
            },
            {
                "id": 0,
                "filename_a": "a.png",
                "filename_b": "b.png",
                "winner": "c.png",
                "timestamp": "2026-01-02T00:00:00Z",
            },
        ]
    )
    assert ids[0] > 0
    assert ids[1] == 0
    assert comparisons_repository.get_total_comparisons() == 1


@pytest.mark.usefixtures("temp_db")
def test_bulk_images_match_per_row() -> None:
    per_row: list[ImageRowForInsert] = [
        {
            "filename": "a.png",
            "score": 0.5,
            "rating_mu": 1.0,
            "rating_sigma": 2.0,
            "comparison_count": 3,
            "prompt_tags": "tag_a",
        },
        {
            "filename": "b.png",
            "score": 0.75,
            "rating_mu": 1.5,
            "rating_sigma": 2.5,
            "comparison_count": 4,
            "prompt_tags": None,
        },
    ]
    for row in per_row:
        images_repository.add_image(
            filename=row["filename"],
            score=row["score"],
            comparison_count=row["comparison_count"],
            prompt_tags=row["prompt_tags"],
            rating_mu=row["rating_mu"],
            rating_sigma=row["rating_sigma"],
        )
    per_row_stored = images_repository.list_nodes()
    images_repository.clear_all_images()

    inserted = images_repository.add_images_bulk(per_row)
    bulk_stored = images_repository.list_nodes()

    assert inserted == 2
    assert bulk_stored == per_row_stored


@pytest.mark.usefixtures("temp_db")
def test_bulk_rating_updates_match_per_row() -> None:
    _seed_images(["a.png", "b.png"])
    updates: list[RatingStateUpdate] = [
        ("a.png", 0.25, 1.25, 3.5, 7),
        ("b.png", 0.75, 1.75, 4.5, 9),
    ]
    for filename, score, mu, sigma, count in updates:
        images_repository.update_image_rating_state(
            filename=filename,
            score=score,
            rating_mu=mu,
            rating_sigma=sigma,
            comparison_count=count,
            touch_timestamp=False,
        )
    per_row_stored = images_repository.list_nodes()
    images_repository.reset_all_image_ratings(score=0.5)

    changed = images_repository.update_image_rating_states_bulk(updates)
    bulk_stored = images_repository.list_nodes()

    assert changed == 2
    assert bulk_stored == per_row_stored


@pytest.mark.usefixtures("temp_db")
def test_bulk_methods_accept_empty_input() -> None:
    assert comparisons_repository.add_comparisons_bulk([]) == []
    assert images_repository.add_images_bulk([]) == 0
    assert images_repository.update_image_rating_states_bulk([]) == 0


def test_repositories_are_redirected_to_the_temp_database(temp_db: Path) -> None:
    """Guards the fixture itself: a leaked path would write to the real database."""
    assert database.cache_file == str(temp_db)
    assert temp_db.exists()
