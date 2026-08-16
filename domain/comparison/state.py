"""Centralised mutable state for the ranking algorithm."""

from typing import Any
import time

from ...core.observability.logger import get_logger, ModuleLogger
from .constants import IMAGES_CACHE_TTL

logger: ModuleLogger = get_logger(__name__)

_images_cache: dict[str, Any] = {"data": None, "timestamp": 0.0}


def set_images_cache(images: list[dict[str, Any]]) -> None:
    """Store the all_images list with a fresh timestamp."""
    global _images_cache
    _images_cache = {"data": images, "timestamp": time.time()}


def is_images_cache_valid() -> bool:
    """Return True when the cached all_images list is present and fresh."""
    return (
        _images_cache["data"] is not None
        and (time.time() - _images_cache["timestamp"]) < IMAGES_CACHE_TTL
    )


def get_cached_all_images() -> list[dict[str, Any]]:
    """Return the cached all_images list; call only when is_images_cache_valid()."""
    return _images_cache["data"]


def get_cached_image(filename: str) -> dict[str, Any] | None:
    """Return a single image from the cached list, or None."""
    for img in get_cached_all_images():
        if img["filename"] == filename:
            return img
    return None


def invalidate_images_cache() -> None:
    global _images_cache
    _images_cache = {"data": None, "timestamp": 0.0}
