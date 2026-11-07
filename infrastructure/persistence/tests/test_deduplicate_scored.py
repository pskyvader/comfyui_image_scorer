"""Deduplication behavior over a temporary ranked tree.

The cross-stem pass hashes every surviving file, so it is also guarded by a
byte-size prefilter. These tests pin the cases that prefilter must not break:
identical bytes under different names, and near-identical metadata under the
same name.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from comfyui_image_scorer.infrastructure.persistence.deduplicate_scored import (
    deduplicate_scored,
)


def _entry(
    tier: Path,
    name: str,
    payload: bytes,
    mtime: float,
    history: list[dict[str, object]] | None = None,
) -> tuple[Path, Path]:
    """Write an image/JSON pair into a tier folder with a controlled mtime."""
    folder = Path(tier)
    folder.mkdir(parents=True, exist_ok=True)
    image = folder / name
    image.write_bytes(payload)
    meta = image.with_suffix(".json")
    meta.write_text(
        json.dumps(
            {
                "score": 0.5,
                "rating_mu": 25.0,
                "comparison_history": list(history or []),
            }
        ),
        encoding="utf-8",
    )
    stamp = (mtime, mtime)
    os.utime(image, stamp)
    os.utime(meta, stamp)
    return image, meta


def test_same_size_identical_bytes_different_names_collapses_to_newest(
    tmp_path: Path,
) -> None:
    """A same-size, identical-bytes pair is still caught by the cross-stem pass."""
    older_img, _ = _entry(tmp_path / "scored_0.5", "older.png", b"identical", 1000.0)
    newer_img, _ = _entry(tmp_path / "scored_0.6", "newer.png", b"identical", 2000.0)

    removed = deduplicate_scored(root=tmp_path)

    assert removed == 1
    assert newer_img.is_file()
    assert not older_img.exists()
    assert not older_img.with_suffix(".json").exists()


def test_different_size_identical_looking_files_are_both_kept(tmp_path: Path) -> None:
    """Distinct byte sizes are not duplicates, so neither file is removed."""
    small, _ = _entry(tmp_path / "scored_0.5", "small.png", b"ab", 1000.0)
    large, _ = _entry(tmp_path / "scored_0.6", "large.png", b"abcd", 2000.0)

    assert deduplicate_scored(root=tmp_path) == 0
    assert small.is_file()
    assert large.is_file()


def test_same_name_identical_bytes_keeps_newest_and_merges_history(
    tmp_path: Path,
) -> None:
    """The same-stem pass keeps the newest copy and folds in its history."""
    history: list[dict[str, object]] = [
        {
            "other": "other.png",
            "timestamp": "2026-01-02T00:00:00Z",
            "winner": True,
        }
    ]
    older_img, _ = _entry(
        tmp_path / "scored_0.5", "shot.png", b"same", 1000.0, history=history
    )
    _newer_img, newer_meta = _entry(
        tmp_path / "scored_0.6", "shot.png", b"same", 2000.0
    )

    assert deduplicate_scored(root=tmp_path) == 1
    assert not older_img.exists()
    merged = json.loads(newer_meta.read_text(encoding="utf-8"))
    assert merged["comparison_history"][0]["other"] == "other.png"
    assert merged["comparison_count"] == 1


def test_same_name_different_bytes_renames_newer_copy(tmp_path: Path) -> None:
    """A filename collision with different content keeps both, via a _2 suffix."""
    older_img, older_meta = _entry(
        tmp_path / "scored_0.5", "shot.png", b"first", 1000.0
    )
    newer_img, newer_meta = _entry(
        tmp_path / "scored_0.6", "shot.png", b"second", 2000.0
    )

    assert deduplicate_scored(root=tmp_path) == 1
    assert older_img.is_file()
    assert older_meta.is_file()
    assert newer_img.with_name("shot_2.png").is_file()
    assert newer_img.with_name("shot_2.json").is_file()
    assert not newer_img.exists()
    assert not newer_meta.exists()


def test_unique_files_are_never_hashed_or_removed(tmp_path: Path) -> None:
    """Distinct sizes across distinct names leave the tree untouched."""
    names = ["a.png", "b.png", "c.png", "d.png"]
    images = [
        _entry(tmp_path / "scored_0.5", name, bytes([index]) * (index + 1), 1000.0 + index)
        for index, name in enumerate(names)
    ]

    assert deduplicate_scored(root=tmp_path) == 0
    for image, _meta in images:
        assert image.is_file()
