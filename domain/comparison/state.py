"""Centralised mutable state for the ranking algorithm."""

from typing import Any
from collections import deque
import time

from comfyui_image_scorer.core.observability.logger import get_logger, ModuleLogger
from comfyui_image_scorer.domain.comparison.constants import IMAGES_CACHE_TTL
from comfyui_image_scorer.core.configuration.settings import config
logger: ModuleLogger = get_logger(__name__)

_images_cache: dict[str, Any] = {"data": None, "timestamp": 0.0}


def get_cached_all_images(images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    global _images_cache
    now = time.time()
    if _images_cache["data"] is not None and (now - _images_cache["timestamp"]) < IMAGES_CACHE_TTL:
        return _images_cache["data"]
    _images_cache = {"data": images, "timestamp": now}
    return images


def get_cached_image(filename: str, images: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    data = images if images is not None else get_cached_all_images([])
    for img in data:
        if img["filename"] == filename:
            return img
    return None


def invalidate_images_cache() -> None:
    global _images_cache
    _images_cache = {"data": None, "timestamp": 0.0}
