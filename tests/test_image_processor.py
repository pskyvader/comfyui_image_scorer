"""Filesystem-boundary behavior of the ranked-image processor."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import NamedTuple, cast

from comfyui_image_scorer.application.services.graph_service import CrystalGraph
from comfyui_image_scorer.application.services.image_processor import ImageProcessor
from comfyui_image_scorer.core.io.serialization import clean_json_metadata
from comfyui_image_scorer.domain.analysis.trueskill import (
    INITIAL_MEAN,
    INITIAL_UNCERTAINTY,
)
from comfyui_image_scorer.domain.ports.files import FilePort
from comfyui_image_scorer.domain.ports.repository import (
    ComparisonRepository,
    ComparisonRow,
    ImageRepository,
    ImageRow,
    ImageRowForInsert,
    RatingStateUpdate,
)


class TempFilePort:
    """FilePort rooted in a temporary directory that records every delegated call."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[str] = []
        self.sync_calls: list[tuple[str, float, float, float, int]] = []

    def read_json(self, path: str) -> dict[str, object]:
        self.calls.append("read_json")
        with Path(path).open(encoding="utf-8") as handle:
            value = json.load(handle)
        assert isinstance(value, dict)
        return cast(dict[str, object], value)

    def write_json(self, path: str, data: dict[str, object]) -> None:
        self.calls.append("write_json")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def file_exists(self, path: str) -> bool:
        self.calls.append("file_exists")
        return Path(path).is_file()

    def list_directory(self, path: str) -> list[str]:
        self.calls.append("list_directory")
        return [entry.name for entry in Path(path).iterdir() if entry.is_file()]

    def make_directory(self, path: str) -> None:
        self.calls.append("make_directory")
        Path(path).mkdir(parents=True, exist_ok=True)

    def move_file(self, src: Path, dst: Path) -> bool:
        self.calls.append("move_file")
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.replace(dst)
        return True

    def remove_file(self, path: Path) -> None:
        self.calls.append("remove_file")
        path.unlink(missing_ok=True)

    def ranked_root(self) -> Path:
        return self.root

    def compute_path(self, filename: str, score: float) -> Path:
        self.calls.append("compute_path")
        return self.root / f"scored_{score:.1f}" / filename

    def sync_metadata(
        self,
        filename: str,
        score: float,
        rating_mu: float,
        rating_sigma: float,
        comparison_count: int,
        filename_to_path: dict[str, Path],
        filename_to_comparisons: dict[str, list[ComparisonRow]],
        filename_to_image_data: dict[str, ImageRow],
        filename_to_entry: dict[str, dict[str, object]],
    ) -> bool:
        del (
            filename_to_path,
            filename_to_comparisons,
            filename_to_image_data,
            filename_to_entry,
        )
        self.calls.append("sync_metadata")
        self.sync_calls.append(
            (filename, score, rating_mu, rating_sigma, comparison_count)
        )
        return True

    def pop_sync_counters(self) -> tuple[int, int]:
        self.calls.append("pop_sync_counters")
        return (0, 0)

    def clear_folder_cache(self) -> None:
        self.calls.append("clear_folder_cache")

    def prewarm_folder_cache(self, path: Path) -> None:
        del path
        self.calls.append("prewarm_folder_cache")

    def deduplicate_scored(self, root: Path) -> int:
        del root
        self.calls.append("deduplicate_scored")
        return 0

    def cleanup_orphans(self, root: Path) -> int:
        del root
        self.calls.append("cleanup_orphans")
        return 0


class MemoryImageRepository:
    """In-memory ImageRepository so graph reloads see what the rebuild wrote."""

    def __init__(self) -> None:
        self.rows: dict[str, ImageRow] = {}
        self.tag_updates: list[tuple[str, str]] = []

    def find_node(self, filename: str) -> ImageRow | None:
        return self.rows.get(filename)

    def list_nodes(self) -> list[ImageRow]:
        return list(self.rows.values())

    def get_image_count(self) -> int:
        return len(self.rows)

    def add_image(
        self,
        filename: str,
        score: float,
        comparison_count: int,
        prompt_tags: str | None,
        rating_mu: float,
        rating_sigma: float,
    ) -> bool:
        self.rows[filename] = ImageRow(
            filename=filename,
            score=score,
            rating_mu=rating_mu,
            rating_sigma=rating_sigma,
            comparison_count=comparison_count,
            last_compared_at=None,
            ranking_generation=0,
            prompt_tags=prompt_tags,
        )
        return True

    def add_images_bulk(self, rows: list[ImageRowForInsert]) -> int:
        for row in rows:
            self.add_image(
                filename=row["filename"],
                score=row["score"],
                comparison_count=row["comparison_count"],
                prompt_tags=row["prompt_tags"],
                rating_mu=row["rating_mu"],
                rating_sigma=row["rating_sigma"],
            )
        return len(rows)

    def update_image_rating_states_bulk(
        self, rows: list[RatingStateUpdate]
    ) -> int:
        for filename, score, rating_mu, rating_sigma, comparison_count in rows:
            self.update_image_rating_state(
                filename=filename,
                score=score,
                rating_mu=rating_mu,
                rating_sigma=rating_sigma,
                comparison_count=comparison_count,
                touch_timestamp=False,
            )
        return len(rows)

    def update_image_rating_state(
        self,
        filename: str,
        score: float,
        rating_mu: float,
        rating_sigma: float,
        comparison_count: int,
        touch_timestamp: bool,
    ) -> bool:
        row = self.rows[filename]
        row["score"] = score
        row["rating_mu"] = rating_mu
        row["rating_sigma"] = rating_sigma
        row["comparison_count"] = comparison_count
        if touch_timestamp:
            row["last_compared_at"] = "2026-01-01T00:00:00+00:00"
        return True

    def update_image_tags(self, filename: str, prompt_tags: str) -> bool:
        self.tag_updates.append((filename, prompt_tags))
        row = self.rows.get(filename)
        if row is not None:
            row["prompt_tags"] = prompt_tags
        return True

    def clear_all_images(self) -> int:
        count = len(self.rows)
        self.rows.clear()
        return count

    def reset_all_image_ratings(self, score: float) -> bool:
        for row in self.rows.values():
            row["score"] = score
            row["rating_mu"] = INITIAL_MEAN
            row["rating_sigma"] = INITIAL_UNCERTAINTY
            row["comparison_count"] = 0
        return True


class MemoryComparisonRepository:
    """In-memory ComparisonRepository that assigns stable incrementing ids."""

    def __init__(self) -> None:
        self.rows: list[ComparisonRow] = []
        self._next_id = 1

    def add_comparison(
        self,
        filename_a: str,
        filename_b: str,
        winner: str,
        timestamp: str | None,
    ) -> int:
        link_id = self._next_id
        self._next_id += 1
        row: ComparisonRow = {
            "id": link_id,
            "filename_a": filename_a,
            "filename_b": filename_b,
            "winner": winner,
        }
        if timestamp is not None:
            row["timestamp"] = timestamp
        self.rows.append(row)
        return link_id

    def add_comparisons_bulk(self, rows: list[ComparisonRow]) -> list[int]:
        return [
            self.add_comparison(
                filename_a=str(row["filename_a"]),
                filename_b=str(row["filename_b"]),
                winner=str(row["winner"]),
                timestamp=str(row.get("timestamp") or "") or None,
            )
            for row in rows
        ]

    def comparison_exists_for_pair(self, filename_a: str, filename_b: str) -> bool:
        pair = {filename_a, filename_b}
        return any({row["filename_a"], row["filename_b"]} == pair for row in self.rows)

    def list_links(self) -> list[ComparisonRow]:
        return list(self.rows)

    def get_total_comparisons(self) -> int:
        return len(self.rows)

    def clean_comparisons(self) -> dict[str, int]:
        return {
            "missing_nodes_removed": 0,
            "self_links_removed": 0,
            "same_direction_duplicates_removed": 0,
            "contradictions_removed": 0,
            "kept": len(self.rows),
        }

    def get_nodes_with_only_wins(self) -> list[str]:
        return []

    def get_nodes_with_only_losses(self) -> list[str]:
        return []

    def clear_all_comparisons(self) -> int:
        count = len(self.rows)
        self.rows.clear()
        self._next_id = 1
        return count


class _RebuildHarness(NamedTuple):
    processor: ImageProcessor
    graph: CrystalGraph
    port: TempFilePort
    images: MemoryImageRepository
    comparisons: MemoryComparisonRepository


def _processor(root: Path) -> tuple[ImageProcessor, TempFilePort]:
    port = TempFilePort(root)
    processor = ImageProcessor(max_workers=1, graph=CrystalGraph(), path_ops=port)
    return processor, port


def _harness(root: Path) -> _RebuildHarness:
    port = TempFilePort(root)
    images = MemoryImageRepository()
    comparisons = MemoryComparisonRepository()
    graph = CrystalGraph(
        image_repo=cast(ImageRepository, images),
        comparison_repo=cast(ComparisonRepository, comparisons),
    )
    processor = ImageProcessor(max_workers=1, graph=graph, path_ops=port)
    return _RebuildHarness(processor, graph, port, images, comparisons)


def _write_ranked(tier: Path, filename: str, payload: dict[str, object]) -> Path:
    tier.mkdir(parents=True, exist_ok=True)
    _touch(tier / filename)
    meta = tier / (Path(filename).stem + ".json")
    meta.write_text(json.dumps(payload), encoding="utf-8")
    return meta


def _touch(path: Path, payload: bytes = b"image") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_get_fast_total_count_owns_source_scan(tmp_path: Path) -> None:
    """Image discovery stays in the application layer, not on the port."""
    source = tmp_path / "incoming"
    _touch(source / "a.png")
    _touch(source / "nested" / "b.jpg")

    processor, port = _processor(tmp_path)

    assert processor.get_fast_total_count(str(source)) == 2
    assert "list_directory" not in port.calls


def test_reorganize_folder_structure_moves_loose_files(tmp_path: Path) -> None:
    """Tier scanning is owned; the resulting moves are delegated to the port."""
    loose = tmp_path / "scored_0.5" / "loose.png"
    _touch(loose)
    (tmp_path / "scored_0.5" / "scored_0.55").mkdir(parents=True)
    loose.with_suffix(".json").write_text(
        json.dumps({"score": 0.7, "prompt_tags": "tag"}), encoding="utf-8"
    )

    processor, port = _processor(tmp_path)
    processor.reorganize_folder_structure()

    assert (tmp_path / "scored_0.7" / "loose.png").is_file()
    assert (tmp_path / "scored_0.7" / "loose.json").is_file()
    assert not loose.exists()
    assert "list_directory" not in port.calls
    assert "compute_path" in port.calls
    assert "move_file" in port.calls


def test_process_image_file_delegates_to_file_port(tmp_path: Path) -> None:
    """Reads, writes, and moves of one candidate image run through FilePort."""
    image = tmp_path / "incoming" / "shot.png"
    _touch(image)
    image.with_suffix(".json").write_text(
        json.dumps({"prompt_tags": "tag", "score": 0.4}), encoding="utf-8"
    )

    processor, port = _processor(tmp_path)
    success, message, *_rest = processor.process_image_file(image)

    assert success, message
    assert (tmp_path / "scored_0.5" / "shot.png").is_file()
    assert (tmp_path / "scored_0.5" / "shot.json").is_file()
    assert {"read_json", "write_json", "move_file", "compute_path"} <= set(port.calls)


def test_file_port_is_the_only_destructive_move_path(tmp_path: Path) -> None:
    """Deletion of a duplicate candidate is delegated rather than done inline."""
    existing = tmp_path / "scored_0.5" / "dup.png"
    _touch(existing, b"same-size")
    incoming = tmp_path / "incoming" / "dup.png"
    _touch(incoming, b"same-size")
    incoming.with_suffix(".json").write_text(
        json.dumps({"prompt_tags": "tag", "score": 0.5}), encoding="utf-8"
    )

    processor, port = _processor(tmp_path)
    success, message, *_rest = processor.process_image_file(incoming)

    assert success, message
    assert "remove_file" in port.calls
    assert not incoming.exists()


def test_port_still_satisfies_the_protocol(tmp_path: Path) -> None:
    _port: FilePort = TempFilePort(tmp_path)
    assert _port.ranked_root() == tmp_path


def test_rebuild_database_from_ranked_rebuilds_every_ranked_image(
    tmp_path: Path,
) -> None:
    """Each ranked image+JSON pair becomes an image node at the default rating."""
    _write_ranked(tmp_path / "scored_0.5", "a.png", {"positive_prompt": "tag-a"})
    _write_ranked(tmp_path / "scored_0.6", "b.png", {"positive_prompt": "tag-b"})
    _write_ranked(tmp_path / "scored_0.6", "c.png", {"positive_prompt": "tag-c"})

    harness = _harness(tmp_path)
    harness.processor.rebuild_database_from_ranked()

    assert harness.graph.get_node_count() == 3
    rows = {row["filename"]: row for row in harness.images.list_nodes()}
    assert set(rows) == {"a.png", "b.png", "c.png"}
    for name, row in rows.items():
        assert row["score"] == harness.processor.default_score
        assert row["rating_mu"] == INITIAL_MEAN
        assert row["rating_sigma"] == INITIAL_UNCERTAINTY
        assert row["comparison_count"] == 0
        assert row["prompt_tags"] == f"tag-{name[0]}"


def test_rebuild_database_from_ranked_replays_comparison_history(
    tmp_path: Path,
) -> None:
    """Self-links and unknown files never become links; the newest outcome wins."""
    tier = tmp_path / "scored_0.5"
    _write_ranked(
        tier,
        "a.png",
        {
            "positive_prompt": "tag-a",
            "comparison_history": [
                {"other": "b.png", "timestamp": "2026-01-01T01:00:00Z", "winner": True},
                {"other": "b.png", "timestamp": "2026-01-01T02:00:00Z", "winner": True},
                {"other": "a.png", "timestamp": "2026-01-01T02:30:00Z", "winner": True},
                {
                    "other": "ghost.png",
                    "timestamp": "2026-01-01T03:00:00Z",
                    "winner": True,
                },
            ],
        },
    )
    _write_ranked(
        tier,
        "b.png",
        {
            "positive_prompt": "tag-b",
            "comparison_history": [
                {"other": "a.png", "timestamp": "2026-01-01T04:00:00Z", "winner": True}
            ],
        },
    )
    _write_ranked(tier, "c.png", {"positive_prompt": "tag-c"})

    harness = _harness(tmp_path)
    harness.processor.rebuild_database_from_ranked()

    links = harness.comparisons.list_links()
    assert len(links) == 1
    assert links[0]["winner"] == "b.png"
    assert links[0].get("timestamp") == "2026-01-01T04:00:00Z"

    rows = {row["filename"]: row for row in harness.images.list_nodes()}
    assert rows["a.png"]["rating_mu"] < INITIAL_MEAN
    assert rows["b.png"]["rating_mu"] > INITIAL_MEAN
    assert rows["a.png"]["comparison_count"] == 1
    assert rows["b.png"]["comparison_count"] == 1
    assert rows["c.png"]["rating_mu"] == INITIAL_MEAN
    assert rows["c.png"]["comparison_count"] == 0


def test_rebuild_database_from_ranked_prompt_tags_match_cleaned_metadata(
    tmp_path: Path,
) -> None:
    """prompt_tags agrees with clean_json_metadata for both JSON shapes."""
    tier = tmp_path / "scored_0.5"
    flat: dict[str, object] = {"positive_prompt": "flat-tag", "steps": 20}
    wrapped: dict[str, object] = {
        "9f1c2e40-1111-2222-3333-444455556666": {
            "positive_prompt": "wrapped-tag",
            "steps": 20,
        }
    }
    _write_ranked(tier, "flat.png", flat)
    _write_ranked(tier, "wrapped.png", wrapped)

    harness = _harness(tmp_path)
    harness.processor.rebuild_database_from_ranked()

    default_score = harness.processor.default_score
    rows = {row["filename"]: row for row in harness.images.list_nodes()}
    for name, payload in (("flat.png", flat), ("wrapped.png", wrapped)):
        expected = clean_json_metadata(
            payload,
            default_score=default_score,
            filename=name,
            initial_mu=INITIAL_MEAN,
            initial_sigma=INITIAL_UNCERTAINTY,
        )["prompt_tags"]
        assert rows[name]["prompt_tags"] == expected
    assert rows["flat.png"]["prompt_tags"] == "flat-tag"
    assert rows["wrapped.png"]["prompt_tags"] == "wrapped-tag"
    assert harness.images.tag_updates == []


def test_rebuild_database_from_ranked_is_deterministic(tmp_path: Path) -> None:
    """Rebuilding identical files yields identical ratings regardless of RNG state."""
    tier = tmp_path / "scored_0.5"
    _write_ranked(
        tier,
        "a.png",
        {
            "positive_prompt": "tag-a",
            "comparison_history": [
                {"other": "b.png", "timestamp": "2026-01-01T01:00:00Z", "winner": True},
                {"other": "d.png", "timestamp": "2026-01-01T04:00:00Z", "winner": True},
            ],
        },
    )
    _write_ranked(
        tier,
        "b.png",
        {
            "positive_prompt": "tag-b",
            "comparison_history": [
                {"other": "c.png", "timestamp": "2026-01-01T02:00:00Z", "winner": True},
                {"other": "d.png", "timestamp": "2026-01-01T05:00:00Z", "winner": True},
            ],
        },
    )
    _write_ranked(
        tier,
        "c.png",
        {
            "positive_prompt": "tag-c",
            "comparison_history": [
                {"other": "d.png", "timestamp": "2026-01-01T03:00:00Z", "winner": True}
            ],
        },
    )
    _write_ranked(tier, "d.png", {"positive_prompt": "tag-d"})

    def ratings_for_seed(seed: int) -> dict[str, tuple[float, float]]:
        random.seed(seed)
        harness = _harness(tmp_path)
        harness.processor.rebuild_database_from_ranked()
        return {
            row["filename"]: (row["rating_mu"], row["rating_sigma"])
            for row in harness.images.list_nodes()
        }

    first = ratings_for_seed(1)
    second = ratings_for_seed(1)
    third = ratings_for_seed(999)
    # Distinguishes the two ways determinism can break: the JSON round trip
    # feeding different input back in, versus a shuffled replay order.
    assert first == second, "round-trip on disk changed the result"
    assert first == third, "result depends on RNG state"
    assert first["d.png"][0] < INITIAL_MEAN
    assert first["a.png"][0] > INITIAL_MEAN


def test_rebuild_database_from_ranked_syncs_json_to_disk(tmp_path: Path) -> None:
    """Every ranked image is handed to the port with its post-rebuild state."""
    tier = tmp_path / "scored_0.5"
    _write_ranked(tier, "a.png", {"positive_prompt": "tag-a"})
    _write_ranked(tier, "b.png", {"positive_prompt": "tag-b"})

    harness = _harness(tmp_path)
    harness.processor.rebuild_database_from_ranked()

    synced = {entry[0]: entry for entry in harness.port.sync_calls}
    assert set(synced) == {"a.png", "b.png"}
    for name, entry in synced.items():
        filename, score, rating_mu, rating_sigma, comparison_count = entry
        row = harness.images.rows[name]
        assert filename == name
        assert score == row["score"]
        assert rating_mu == row["rating_mu"]
        assert rating_sigma == row["rating_sigma"]
        assert comparison_count == row["comparison_count"]
