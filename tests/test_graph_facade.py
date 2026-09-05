from pathlib import Path
from typing import Any, cast

import pytest

from comfyui_image_scorer.infrastructure.persistence.file_manager import FileManager
from comfyui_image_scorer.application.services.graph_service import CrystalGraph


class ComparisonStore:
    def __init__(self) -> None:
        self.cleared = False

    def clear_all_comparisons(self) -> int:
        self.cleared = True
        return 0


class LinkStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str]] = []

    def add_comparison(
        self, filename_a: str, filename_b: str, winner: str, timestamp: str
    ) -> int:
        self.calls.append((filename_a, filename_b, winner, timestamp))
        return 17


class FailingLinkStore:
    def add_comparison(self, **_: str) -> int:
        raise RuntimeError("database unavailable")


def test_file_manager_round_trip(tmp_path: Path) -> None:
    manager = FileManager()
    target = tmp_path / "nested" / "record.json"

    manager.write_json(str(target), {"value": 3})

    assert manager.file_exists(str(target))
    assert manager.read_json(str(target)) == {"value": 3}
    assert manager.list_directory(str(target.parent)) == ["record.json"]


def test_clearing_comparisons_unloads_graph() -> None:
    store = ComparisonStore()
    graph = CrystalGraph(comparison_repo=cast(Any, store))
    graph.rebuild_from_database(images=[], comparisons=[])

    assert graph.is_loaded()
    graph.clear_all_comparisons()

    assert store.cleared
    assert not graph.is_loaded()
    assert graph.get_node_count() == 0
    assert graph.get_link_count() == 0


def test_add_link_persists_before_updating_graph_history() -> None:
    store = LinkStore()
    graph = CrystalGraph(comparison_repo=cast(Any, store))

    link_id = graph.add_link("a.png", "b.png", "a.png", "2026-08-31T00:00:00Z")

    assert link_id == 17
    assert store.calls == [("a.png", "b.png", "a.png", "2026-08-31T00:00:00Z")]
    assert [link.data for link in graph.get_all_links()] == [
        {
            "id": 17,
            "filename_a": "a.png",
            "filename_b": "b.png",
            "winner": "a.png",
            "timestamp": "2026-08-31T00:00:00Z",
        }
    ]


def test_add_link_does_not_mutate_graph_when_persistence_fails() -> None:
    graph = CrystalGraph(comparison_repo=cast(Any, FailingLinkStore()))

    with pytest.raises(RuntimeError, match="database unavailable"):
        graph.add_link("a.png", "b.png", "a.png", "2026-08-31T00:00:00Z")

    assert graph.get_link_count() == 0
