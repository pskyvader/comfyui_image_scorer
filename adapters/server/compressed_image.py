"""Serve images re-encoded to WebP (q90, fastest method) with an in-memory cache."""

import io
from os import stat_result
from pathlib import Path

from flask import Response
from PIL import Image
import time


from ...core.observability.logger import (
    get_logger,
    ModuleLogger,
)
from ...domain.ports.cache import CacheProvider

logger: ModuleLogger = get_logger(__name__)

WEBP_QUALITY = 90
WEBP_METHOD = 0


def compressed_image_response(src: Path, fname: str, cache: CacheProvider) -> Response:
    _start: float = time.perf_counter()
    st: stat_result = src.stat()
    key: str = f"{fname}:{st.st_mtime_ns}:{st.st_size}"

    data: bytes | None = cache.get(key)
    if data is None:
        with Image.open(src) as im:
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
        data = buf.getvalue()
        cache.set(key, data)

    response = Response(data, mimetype="image/webp")
    response.headers["Content-Length"] = str(len(data))
    response.headers["Cache-Control"] = "private, max-age=86400"
    return response
