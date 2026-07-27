"""Images table operations."""

from __future__ import annotations

from typing import Any

from comfyui_image_scorer.core.observability.logger import ModuleLogger, get_logger
from comfyui_image_scorer.infrastructure.persistence.database import get_db_connection

logger: ModuleLogger = get_logger(__name__)


def get_all_images() -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM images").fetchall()
        return [dict(row) for row in rows]


def get_image(filename: str) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM images WHERE filename = ?", (filename,)
        ).fetchone()
        return dict(row) if row else None


def add_image(
    filename: str,
    score: float = 0.5,
    comparison_count: int = 0,
    prompt_tags: str | None = None,
    rating_mu: float = 25.0,
    rating_sigma: float = 25.0 / 3.0,
) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO images (filename, score, rating_mu, rating_sigma, comparison_count, prompt_tags)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (filename, score, rating_mu, rating_sigma, comparison_count, prompt_tags),
        )
        conn.commit()


def update_image_rating_state(
    filename: str,
    score: float,
    rating_mu: float,
    rating_sigma: float,
    comparison_count: int,
) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE images
            SET score = ?, rating_mu = ?, rating_sigma = ?, comparison_count = ?
            WHERE filename = ?
            """,
            (score, rating_mu, rating_sigma, comparison_count, filename),
        )
        conn.commit()
