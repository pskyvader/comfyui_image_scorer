"""Concrete filesystem adapter for graph-owned file operations."""

from __future__ import annotations

from pathlib import Path

from ...domain.ports.repository import ComparisonRow, ImageRow
from .cleanup_orphans import cleanup_orphans
from .deduplicate_scored import deduplicate_scored
from .path_handler import (
    clear_folder_cache,
    compute_path_from_filename,
    get_ranked_root,
    pop_sync_counters,
    prewarm_folder_cache,
    sync_image_metadata_to_json,
)


class FileManager:
    """Implement the ranked-file port without exposing path policy."""

    def ranked_root(self) -> Path:
        return get_ranked_root()

    def compute_path(self, filename: str, score: float) -> Path:
        return compute_path_from_filename(filename, score)

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
        return sync_image_metadata_to_json(
            filename=filename,
            score=score,
            rating_mu=rating_mu,
            rating_sigma=rating_sigma,
            comparison_count=comparison_count,
            filename_to_path=filename_to_path,
            filename_to_comparisons=filename_to_comparisons,
            filename_to_image_data=filename_to_image_data,
            filename_to_entry=filename_to_entry,
        )

    def pop_sync_counters(self) -> tuple[int, int]:
        return pop_sync_counters()

    def clear_folder_cache(self) -> None:
        clear_folder_cache()

    def prewarm_folder_cache(self, path: Path) -> None:
        prewarm_folder_cache(path)

    def deduplicate_scored(self, root: Path) -> int:
        return deduplicate_scored(root)

    def cleanup_orphans(self, root: Path) -> int:
        return cleanup_orphans(root)
