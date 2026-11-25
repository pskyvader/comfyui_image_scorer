"""Filesystem protocol port, moved from ``domain/files/ports.py``.

Only the ranked-file operations required by application services are exposed
here. Implementations live in ``infrastructure``; callers depend only on this
protocol, not on concrete paths or JSON formats.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .repository import ComparisonRow, ImageRow


class FilePort(Protocol):
    """Ranked-file filesystem protocol required by application services.

    Generic file operations live in ``core.io.operations`` and
    ``core.filesystem.operations``. Implementations of this port live in
    infrastructure; callers depend only on the protocol.
    """

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
