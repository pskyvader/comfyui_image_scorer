"""Centralised mutable state for the ranking algorithm."""

from typing import Any
import time

from ...core.observability.logger import get_logger, ModuleLogger
from .constants import IMAGES_CACHE_TTL

logger: ModuleLogger = get_logger(__name__)

_images_cache: dict[str, Any] = {"data": None, "timestamp": 0.0}


def get_cached_all_images(images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return cached all_images list, refreshing if stale."""
    global _images_cache
    now = time.time()
    if (
        _images_cache["data"] is not None
        and (now - _images_cache["timestamp"]) < IMAGES_CACHE_TTL
    ):
        return _images_cache["data"]

    _images_cache = {"data": images, "timestamp": now}
    return images


def get_cached_image(
    filename: str, images: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Return a single image from the cached list, or None."""
    for img in get_cached_all_images(images):
        if img["filename"] == filename:
            return img
    return None


def invalidate_images_cache() -> None:
    global _images_cache
    _images_cache = {"data": None, "timestamp": 0.0}
