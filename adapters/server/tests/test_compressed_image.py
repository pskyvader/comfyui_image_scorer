"""Tests for lossy WebP serving of images via the in-memory cache."""

import io
import os
from pathlib import Path

import pytest
from PIL import Image

from ....infrastructure.cache.memory_cache import InMemoryCache
from ..compressed_image import compressed_image_response


@pytest.fixture()
def image_cache() -> InMemoryCache:
    return InMemoryCache()


def _write_image(tmp_path: Path, im: Image.Image, name: str, fmt: str) -> Path:
    path = tmp_path / name
    im.save(path, fmt)
    return path


def test_png_served_as_smaller_webp(tmp_path: Path, image_cache: InMemoryCache) -> None:
    im = Image.new("RGB", (256, 256), (200, 100, 50))
    src = _write_image(tmp_path, im, "img.png", "PNG")

    response = compressed_image_response(src, "img.png", image_cache)

    assert response.mimetype == "image/webp"
    assert int(response.headers["Content-Length"]) == len(response.data)
    assert len(response.data) < src.stat().st_size
    decoded = Image.open(io.BytesIO(response.data))
    assert decoded.format == "WEBP"
    assert decoded.size == (256, 256)


def test_animated_gif_served_as_webp(tmp_path: Path, image_cache: InMemoryCache) -> None:
    frames = [Image.new("RGB", (64, 64), (i * 30, 0, 0)) for i in range(3)]
    src = tmp_path / "anim.gif"
    frames[0].save(src, "GIF", save_all=True, append_images=frames[1:])

    response = compressed_image_response(src, "anim.gif", image_cache)

    assert response.mimetype == "image/webp"
    assert len(response.data) > 0


def test_cache_served_second_call(tmp_path: Path, image_cache: InMemoryCache) -> None:
    im = Image.new("RGB", (128, 128), (10, 20, 30))
    src = _write_image(tmp_path, im, "img.png", "PNG")

    first = compressed_image_response(src, "img.png", image_cache)
    second = compressed_image_response(src, "img.png", image_cache)

    assert second.data == first.data
    key = f"img.png:{src.stat().st_mtime_ns}:{src.stat().st_size}"
    assert image_cache.get(key) is not None


def test_cache_invalidated_on_mtime_change(
    tmp_path: Path, image_cache: InMemoryCache
) -> None:
    im = Image.new("RGB", (128, 128), (10, 20, 30))
    src = _write_image(tmp_path, im, "img.png", "PNG")

    first = compressed_image_response(src, "img.png", image_cache)

    im2 = Image.new("RGB", (128, 128), (200, 20, 30))
    im2.save(src, "PNG")
    os.utime(src, (src.stat().st_atime, src.stat().st_mtime + 5))
    second = compressed_image_response(src, "img.png", image_cache)

    assert second.data != first.data
