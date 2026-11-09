"""Port for the pairing processor that owns recent-image bookkeeping.

The comparison engine phases touch this processor to seed and read the
recently paired image cache; adapters construct the concrete
:class:`application.services.pairing_processor.PairingProcessor` and inject it
through this port. The port mirrors the processor's full public surface.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from threading import Lock
from typing import Protocol

from ...core.io.serialization import CollectedFile


class PairingProcessorPort(Protocol):
    processed_lock: Lock
    processed_images: set[str]
    image_extensions: set[str]
    is_processing: bool
    total_discovered: int
    lru_size: int
    max_workers: int
    default_score: float
    reserve_count: int
    recent_images: deque[str]
    recent_chains: deque[str]
    recent_lock: Lock

    def process_image_file(
        self, image_path: Path
    ) -> tuple[bool, str, float | None, str | None, bool, str | None]: ...

    def sync_processed_images_from_db(self) -> None: ...

    def get_fast_total_count(self, source_dir: str) -> int: ...

    def process_next_batch(self, source_dir: str, batch_size: int) -> dict[str, object]: ...

    def rebuild_database_from_ranked(self) -> None: ...

    def sync_ranked_files_from_database(self) -> None: ...

    def sync_database_to_files(self, all_entries: list[CollectedFile]) -> None: ...

    def reorganize_folder_structure(self) -> None: ...

    def clear_old_cache(self, force: bool) -> None: ...
