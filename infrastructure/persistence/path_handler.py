"""Path handler - compute tier structure from scores and sync companion JSON."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from ...core.observability.logger import get_logger, ModuleLogger
from ...core.configuration.settings import config
from ...core.io.serialization import atomic_write_json, load_json
from ...core.filesystem.paths import image_root_processed
from ..cache.memory_cache import InMemoryCache
from .images_repository import (
    find_node as get_node_data,
)

logger: ModuleLogger = get_logger(__name__)

_folder_listdir_cache = InMemoryCache()


def prewarm_folder_cache(ranked_root: Path) -> None:
    """Eagerly populate tier folder cache for all scored_X.X directories."""
    for i in range(11):
        base = ranked_root / f"scored_{i / 10:.1f}"
        if not base.exists():
            continue
        items = os.listdir(base)
        has_subfolders = any(
            item.startswith("scored_") and (base / item).is_dir() for item in items
        )
        _folder_listdir_cache.set(str(base), (len(items), has_subfolders))


def clear_folder_cache() -> None:
    _folder_listdir_cache.clear()


def get_ranked_root() -> Path:
    root_path = Path(image_root_processed)
    if not root_path.is_absolute():
        root_path = Path(__file__).resolve().parent.parent.parent.parent / root_path
    root_path.mkdir(parents=True, exist_ok=True)
    return root_path


def compute_path_from_filename(filename: str, score: float) -> Path:
    ranked_root = get_ranked_root()
    clamped_score = max(0.0, min(1.0, float(score)))
    score_truncated = math.floor(clamped_score * 10) / 10.0
    base_folder = ranked_root / f"scored_{score_truncated:.1f}"
    threshold = int(config["ranking"]["subfolder_threshold"])

    cache_key = str(base_folder)
    cached = _folder_listdir_cache.get(cache_key)
    if cached is not None:
        file_count, has_subfolders = cached
    elif base_folder.exists():
        items = os.listdir(base_folder)
        file_count = len(items)
        has_subfolders = any(
            item.startswith("scored_") and (base_folder / item).is_dir()
            for item in items
        )
        _folder_listdir_cache.set(cache_key, (file_count, has_subfolders))
    else:
        file_count = 0
        has_subfolders = False

    if (file_count < threshold and not has_subfolders) or score_truncated >= 1.0:
        return base_folder / filename

    score_second = math.floor(clamped_score * 100) / 100.0
    return base_folder / f"scored_{score_second:.2f}" / filename


def find_image_path(filename: str) -> Path | None:
    ranked_root = get_ranked_root()
    for root, _, files in os.walk(ranked_root):
        if filename in files:
            return Path(root) / filename
    return None


def _build_history_for_filename(
    filename: str,
    all_comparisons: list[dict[str, Any]] | None = None,
    filename_to_comparisons: dict[str, list[dict[str, Any]]] | None = None,
    filename_to_image_data: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if filename_to_comparisons is not None:
        comps = filename_to_comparisons[filename]
    elif all_comparisons is not None:
        comps = [
            c
            for c in all_comparisons
            if c["filename_a"] == filename or c["filename_b"] == filename
        ]
    else:
        comps = []

    history: list[dict[str, Any]] = []
    for comp in comps:
        is_winner = comp["winner"] == filename
        other = (
            comp["filename_b"] if comp["filename_a"] == filename else comp["filename_a"]
        )
        if filename_to_image_data is not None:
            other_data = filename_to_image_data[other]
        else:
            other_data = get_node_data(other)
        history.append(
                {
                    "comparison_id": comp["id"],
                    "other": other,
                    "opponent_score": other_data["score"] if other_data else 0.5,
                    "winner": is_winner,
                    "timestamp": comp["timestamp"],
                }
            )
    history.sort(key=lambda item: (item["timestamp"], item["comparison_id"]))
    return history


def _move_image_and_json(current_image: Path, current_json: Path, score: float) -> None:
    target_path = compute_path_from_filename(current_image.name, score)
    if target_path.parent == current_image.parent:
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_json = target_path.with_suffix(".json")
    os.replace(str(current_image), str(target_path))
    os.replace(str(current_json), str(target_json))


def sync_image_metadata_to_json(
    filename: str,
    score: float,
    rating_mu: float,
    rating_sigma: float,
    comparison_count: int,
    all_comparisons: list[dict[str, Any]] | None = None,
    filename_to_path: dict[str, Path] | None = None,
    filename_to_comparisons: dict[str, list[dict[str, Any]]] | None = None,
    filename_to_image_data: dict[str, dict[str, Any]] | None = None,
    filename_to_entry: dict[str, dict[str, Any]] | None = None,
) -> bool:
    """Rewrite one JSON companion file from DB-backed state."""

    if filename_to_path is not None and filename in filename_to_path:
        img_path = filename_to_path[filename]
    else:
        img_path = find_image_path(filename)
    if not img_path:
        logger.warning("Image file not found for %s, cannot sync JSON.", filename)
        return False
    json_path = img_path.with_suffix(".json")

    if filename_to_entry is not None:
        data = filename_to_entry.get(filename)
        if data is None:
            return False
    else:
        if not json_path.exists():
            return False
        data, err = load_json(str(json_path), expect=dict)
        if err is not None or data is None:
            return False

    if filename_to_comparisons is None and all_comparisons is None:
        raise RuntimeError("Comparison history must be supplied by CrystalGraph")

    history = _build_history_for_filename(
        filename,
        all_comparisons=all_comparisons,
        filename_to_comparisons=filename_to_comparisons,
        filename_to_image_data=filename_to_image_data,
    )

    old_score = data.get("score")
    old_mu = data.get("rating_mu")
    old_sigma = data.get("rating_sigma")
    old_count = data.get("comparison_count")
    old_history = data.get("comparison_history") or []

    data["score"] = float(score)
    data["rating_mu"] = float(rating_mu)
    data["rating_sigma"] = float(rating_sigma)
    data["comparison_count"] = int(comparison_count)
    data["comparison_history"] = history
    data.pop("confidence", None)

    if (
        old_score == data["score"]
        and old_mu == data["rating_mu"]
        and old_sigma == data["rating_sigma"]
        and old_count == data["comparison_count"]
        and old_history == data["comparison_history"]
    ):
        return True

    atomic_write_json(str(json_path), data, indent=2)
    _move_image_and_json(img_path, json_path, score)
    return True
