"""Images table operations."""

from __future__ import annotations

from typing import Any

from ...core.observability.logger import ModuleLogger, get_logger
from .database import get_db_connection

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
    touch_timestamp: bool = True,
    last_compared_at: str | None = None,
) -> bool:
    try:
        with get_db_connection() as conn:
            if touch_timestamp:
                conn.execute(
                    """
                    UPDATE images
                    SET score=?, rating_mu=?, rating_sigma=?, comparison_count=?, last_compared_at=CURRENT_TIMESTAMP
                    WHERE filename=?
                    """,
                    (float(score), float(rating_mu), float(rating_sigma), int(comparison_count), filename),
                )
            elif last_compared_at is not None:
                conn.execute(
                    """
                    UPDATE images
                    SET score=?, rating_mu=?, rating_sigma=?, comparison_count=?, last_compared_at=?
                    WHERE filename=?
                    """,
                    (float(score), float(rating_mu), float(rating_sigma), int(comparison_count), str(last_compared_at), filename),
                )
            else:
                conn.execute(
                    """
                    UPDATE images
                    SET score=?, rating_mu=?, rating_sigma=?, comparison_count=?
                    WHERE filename=?
                    """,
                    (float(score), float(rating_mu), float(rating_sigma), int(comparison_count), filename),
                )
            conn.commit()
        return True
    except Exception as exc:
        logger.error("Failed to update rating state for %s: %s", filename, exc)
        return False


def update_image_tags(filename: str, prompt_tags: str) -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE images SET prompt_tags=? WHERE filename=?",
                (prompt_tags, filename),
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.error("Failed to update tags for %s: %s", filename, exc)
        return False


def update_image_score(filename: str, score: float) -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE images SET score=?, last_compared_at=CURRENT_TIMESTAMP WHERE filename=?",
                (float(score), filename),
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.error("Failed to update score for %s: %s", filename, exc)
        return False


def get_image_count() -> int:
    try:
        with get_db_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM images").fetchone()
            return row["cnt"] if row else 0
    except Exception as exc:
        logger.error("Failed to count images: %s", exc)
        return 0


def get_scored_images(limit: int = 100, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
    try:
        with get_db_connection() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM images WHERE score IS NOT NULL"
            ).fetchone()
            total = total_row["cnt"] if total_row else 0
            rows = conn.execute(
                "SELECT * FROM images WHERE score IS NOT NULL ORDER BY score DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [dict(row) for row in rows], total
    except Exception as exc:
        logger.error("Failed to fetch scored images: %s", exc)
        return [], 0


def get_images_by_tier(tier: int) -> list[dict[str, Any]]:
    tier_min = tier / 10.0
    tier_max = (tier + 1) / 10.0
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM images WHERE score >= ? AND score < ? ORDER BY score",
                (tier_min, tier_max),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception as exc:
        logger.error("Failed to fetch tier %s: %s", tier, exc)
        return []


def delete_image(filename: str) -> bool:
    try:
        with get_db_connection() as conn:
            cur = conn.execute("DELETE FROM images WHERE filename=?", (filename,))
            conn.commit()
        return cur.rowcount > 0
    except Exception as exc:
        logger.error("Failed to delete image %s: %s", filename, exc)
        return False


def clear_all_images() -> int:
    try:
        with get_db_connection() as conn:
            cur = conn.execute("DELETE FROM images")
            conn.commit()
        return int(cur.rowcount or 0)
    except Exception as exc:
        logger.error("Error clearing images: %s", exc)
        return 0


def reset_all_image_ratings(score: float = 0.5) -> bool:
    try:
        MU0 = 25.0
        SIGMA0 = MU0 / 3.0
        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE images
                SET score=?, rating_mu=?, rating_sigma=?, comparison_count=0, last_compared_at=NULL
                """,
                (float(score), MU0, SIGMA0),
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.error("Failed to reset ratings: %s", exc)
        return False
