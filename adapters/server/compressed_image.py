"""Serve images re-encoded to WebP (q90, fastest method) with an in-memory cache."""

import io
from collections import OrderedDict
from os import stat_result
from pathlib import Path

from flask import Response
from PIL import Image
import time


from ...core.observability.logger import (
    get_logger,
    ModuleLogger,
)

logger: ModuleLogger = get_logger(__name__)

WEBP_QUALITY = 90
WEBP_METHOD = 0


class _InMemoryImageCache:
    def __init__(self, max_bytes: int = 256 * 1024 * 1024) -> None:
        self._items: OrderedDict[tuple[str, int, int], bytes] = OrderedDict()
        self._max_bytes: int = max_bytes
        self._size = 0

    def get(self, key: tuple[str, int, int]) -> bytes | None:
        if key not in self._items:
            return None
        self._items.move_to_end(key)
        return self._items[key]

    def put(self, key: tuple[str, int, int], value: bytes) -> None:
        self._items[key] = value
        self._size += len(value)
        while self._size > self._max_bytes and self._items:
            _, evicted = self._items.popitem(last=False)
            self._size -= len(evicted)

    def clear(self) -> None:
        self._items.clear()
        self._size = 0


image_cache = _InMemoryImageCache()


def compressed_image_response(src: Path, fname: str) -> Response:
    _start: float = time.perf_counter()
    st: stat_result = src.stat()
    key: tuple[str, int, int] = (fname, st.st_mtime_ns, st.st_size)

    data: bytes | None = image_cache.get(key)
    if data is None:
        with Image.open(src) as im:
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
        data = buf.getvalue()
        image_cache.put(key, data)

    response = Response(data, mimetype="image/webp")
    response.headers["Content-Length"] = str(len(data))
    response.headers["Cache-Control"] = "private, max-age=86400"
    # logger.debug(
    #     "compressed %s: %d -> %d bytes (%.1f%% smaller)",
    #     fname,
    #     st.st_size,
    #     len(data),
    #     (1 - len(data) / st.st_size) * 100,
    #     start_timer=_start,
    # )
    return response
