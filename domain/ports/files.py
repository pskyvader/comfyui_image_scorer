"""Filesystem protocol port, moved from ``domain/files/ports.py``.

Only the narrow filesystem operations required by ``CrystalGraph`` are exposed
here. Implementations live in ``infrastructure``; callers depend only on this
protocol, not on concrete paths or JSON formats.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .repository import ComparisonRow, ImageRow


class FilePort(Protocol):
    """Narrow filesystem protocol required by CrystalGraph.

    Only the operations CrystalGraph truly needs are exposed here.
    Implementations live in infrastructure; callers depend only on this
    protocol, not on concrete paths or JSON formats.
    """

    def read_json(self, path: str) -> dict[str, object]: ...
    def write_json(self, path: str, data: dict[str, object]) -> None: ...
    def file_exists(self, path: str) -> bool: ...
    def list_directory(self, path: str) -> list[str]: ...
    def make_directory(self, path: str) -> None: ...

    def move_file(self, src: Path, dst: Path) -> bool:
        """Move a file from src to dst through the filesystem port."""
        ...

    def remove_file(self, path: Path) -> None:
        """Delete a file through the filesystem port."""

    def ranked_root(self) -> Path: ...

    def compute_path(self, filename: str, score: float) -> Path: ...

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
    ) -> bool: ...

    def pop_sync_counters(self) -> tuple[int, int]: ...

    def clear_folder_cache(self) -> None: ...

    def prewarm_folder_cache(self, path: Path) -> None: ...

    def deduplicate_scored(self, root: Path) -> int: ...

    def cleanup_orphans(self, root: Path) -> int: ...
