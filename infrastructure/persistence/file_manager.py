"""Concrete filesystem adapter for graph-owned file operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from .cleanup_orphans import cleanup_orphans
from .deduplicate_scored import deduplicate_scored
from .path_handler import (
    clear_folder_cache,
    compute_path_from_filename,
    get_ranked_root,
    prewarm_folder_cache,
    sync_image_metadata_to_json,
)


class FileManager:
    """Implement the narrow filesystem port without exposing path policy."""

    def read_json(self, path: str) -> dict[str, Any]:
        with Path(path).open(encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError(f"JSON object required: {path}")
        return cast(dict[str, Any], value)

    def write_json(self, path: str, data: dict[str, Any]) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def file_exists(self, path: str) -> bool:
        return Path(path).is_file()

    def list_directory(self, path: str) -> list[str]:
        return [entry.name for entry in Path(path).iterdir() if entry.is_file()]

    def make_directory(self, path: str) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)

    def ranked_root(self) -> Path:
        return get_ranked_root()

    def compute_path(self, filename: str, score: float) -> Path:
        return compute_path_from_filename(filename, score)

    def sync_metadata(self, **kwargs: Any) -> bool:
        return sync_image_metadata_to_json(**kwargs)

    def clear_folder_cache(self) -> None:
        clear_folder_cache()

    def prewarm_folder_cache(self, path: Path) -> None:
        prewarm_folder_cache(path)

    def deduplicate_scored(self, root: Path) -> int:
        return deduplicate_scored(root)

    def cleanup_orphans(self, root: Path) -> int:
        return cleanup_orphans(root)
