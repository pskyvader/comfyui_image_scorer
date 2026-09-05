from __future__ import annotations

from pathlib import Path
from typing import Protocol


class FilePort(Protocol):
    """Narrow filesystem protocol required by CrystalGraph.

    Only the operations CrystalGraph truly needs are exposed here.
    Implementations live in infrastructure; callers depend only on this
    protocol, not on concrete paths or JSON formats.
    """

    def read_json(self, path: str) -> dict[str, object]:
        """Read a JSON file, returning empty dict if not found."""

    def write_json(self, path: str, data: dict[str, object]) -> None:
        """Write data as JSON to the given path."""

    def file_exists(self, path: str) -> bool:
        """Check whether a file exists at the given path."""

    def list_directory(self, path: str) -> list[str]:
        """List filenames (not full paths) directly under *path*.

        Returns an empty list if the directory does not exist.
        """

    def make_directory(self, path: str) -> None:
        """Create *path* including any missing parents; no-op if it exists."""

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
        filename_to_comparisons: dict[str, list[dict[str, object]]],
        filename_to_image_data: dict[str, dict[str, object]],
        filename_to_entry: dict[str, dict[str, object]],
    ) -> bool: ...
    def clear_folder_cache(self) -> None: ...
    def prewarm_folder_cache(self, path: Path) -> None: ...
    def deduplicate_scored(self, root: Path) -> int: ...
    def cleanup_orphans(self, root: Path) -> int: ...
