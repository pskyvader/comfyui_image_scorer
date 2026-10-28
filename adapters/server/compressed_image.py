"""Serve images re-encoded to WebP (q90, fastest method) with an in-memory cache."""

import io
from os import stat_result
from pathlib import Path

from flask import Response
from PIL import Image
import time


from ...core.configuration.settings import config
from ...core.observability.logger import (
    get_logger,
    ModuleLogger,
)
from ...domain.ports.cache import CacheProvider

logger: ModuleLogger = get_logger(__name__)


def compressed_image_response(src: Path, fname: str, cache: CacheProvider) -> Response:
    webp_quality = int(config["ranking"]["webp_quality"])
    webp_effort = int(config["ranking"]["webp_effort"])
    _start: float = time.perf_counter()
    st: stat_result = src.stat()
    key: str = f"{fname}:{st.st_mtime_ns}:{st.st_size}"

    cached = cache.get(key)
    data: bytes | None = cached if isinstance(cached, bytes) else None
    if data is None:
        with Image.open(src) as im:
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=webp_quality, method=webp_effort)
        data = buf.getvalue()
        cache.set(key, data)

    response = Response(data, mimetype="image/webp")
    response.headers["Content-Length"] = str(len(data))
    response.headers["Cache-Control"] = "private, max-age=86400"
    return response
