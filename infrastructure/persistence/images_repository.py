"""Images table operations."""

from __future__ import annotations

from typing import cast

from ...core.observability.logger import ModuleLogger, get_logger
from ...domain.ports.repository import (
    ImageRow,
    ImageRowForInsert,
    RatingStateUpdate,
)
from .database import get_db_connection

logger: ModuleLogger = get_logger(__name__)


def list_nodes() -> list[ImageRow]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM images").fetchall()
        return cast(list[ImageRow], [dict(row) for row in rows])


def find_node(filename: str) -> ImageRow | None:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM images WHERE filename = ?", (filename,)
        ).fetchone()
        return cast(ImageRow, dict(row)) if row else None


def add_image(
    filename: str,
    score: float,
    comparison_count: int,
    prompt_tags: str | None,
    rating_mu: float,
    rating_sigma: float,
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


def add_images_bulk(rows: list[ImageRowForInsert]) -> int:
    """Insert many images in one transaction; return the row count."""
    if not rows:
        return 0
    with get_db_connection() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO images
            (filename, score, rating_mu, rating_sigma, comparison_count, prompt_tags)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(row["filename"]),
                    float(row["score"]),
                    float(row.get("rating_mu", 0.0)),
                    float(row.get("rating_sigma", 0.0)),
                    int(row.get("comparison_count", 0)),
                    row.get("prompt_tags"),
                )
                for row in rows
            ],
        )
        conn.commit()
    return len(rows)


def update_image_rating_state(
    filename: str,
    score: float,
    rating_mu: float,
    rating_sigma: float,
    comparison_count: int,
    touch_timestamp: bool,
    last_compared_at: str | None = None,
) -> bool:
    with get_db_connection() as conn:
        if touch_timestamp:
            conn.execute(
                """
                UPDATE images
                SET score=?, rating_mu=?, rating_sigma=?, comparison_count=?, last_compared_at=CURRENT_TIMESTAMP
                WHERE filename=?
                """,
                (
                    float(score),
                    float(rating_mu),
                    float(rating_sigma),
                    int(comparison_count),
                    filename,
                ),
            )
        elif last_compared_at is not None:
            conn.execute(
                """
                UPDATE images
                SET score=?, rating_mu=?, rating_sigma=?, comparison_count=?, last_compared_at=?
                WHERE filename=?
                """,
                (
                    float(score),
                    float(rating_mu),
                    float(rating_sigma),
                    int(comparison_count),
                    str(last_compared_at),
                    filename,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE images
                SET score=?, rating_mu=?, rating_sigma=?, comparison_count=?
                WHERE filename=?
                """,
                (
                    float(score),
                    float(rating_mu),
                    float(rating_sigma),
                    int(comparison_count),
                    filename,
                ),
            )
        conn.commit()
    return True


def update_image_rating_states_bulk(
    rows: list[RatingStateUpdate],
) -> int:
    """Apply many rating updates in one transaction; return the row count."""
    if not rows:
        return 0
    with get_db_connection() as conn:
        conn.executemany(
            """
            UPDATE images
            SET score=?, rating_mu=?, rating_sigma=?, comparison_count=?
            WHERE filename=?
            """,
            [
                (
                    float(score),
                    float(rating_mu),
                    float(rating_sigma),
                    int(comparison_count),
                    filename,
                )
                for filename, score, rating_mu, rating_sigma, comparison_count in rows
            ],
        )
        conn.commit()
    return len(rows)


def update_image_tags(filename: str, prompt_tags: str) -> bool:
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE images SET prompt_tags=? WHERE filename=?",
            (prompt_tags, filename),
        )
        conn.commit()
    return True


def get_image_count() -> int:
    with get_db_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM images").fetchone()
        return row["cnt"] if row else 0


def clear_all_images() -> int:
    with get_db_connection() as conn:
        cur = conn.execute("DELETE FROM images")
        conn.commit()
    return int(cur.rowcount or 0)


def reset_all_image_ratings(score: float) -> bool:
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


class SQLiteImagesRepository:
    """Injected implementation of the ImageRepository port."""

    def find_node(self, filename: str) -> ImageRow | None:
        return find_node(filename)

    def list_nodes(self) -> list[ImageRow]:
        return list_nodes()

    def get_image_count(self) -> int:
        return get_image_count()

    def add_image(
        self,
        filename: str,
        score: float,
        comparison_count: int,
        prompt_tags: str | None,
        rating_mu: float,
        rating_sigma: float,
    ) -> bool:
        add_image(
            filename=filename,
            score=score,
            comparison_count=comparison_count,
            prompt_tags=prompt_tags,
            rating_mu=rating_mu,
            rating_sigma=rating_sigma,
        )
        return True

    def add_images_bulk(self, rows: list[ImageRowForInsert]) -> int:
        return add_images_bulk(rows)

    def update_image_rating_states_bulk(
        self, rows: list[RatingStateUpdate]
    ) -> int:
        return update_image_rating_states_bulk(rows)

    def update_image_rating_state(
        self,
        filename: str,
        score: float,
        rating_mu: float,
        rating_sigma: float,
        comparison_count: int,
        touch_timestamp: bool,
    ) -> bool:
        return update_image_rating_state(
            filename=filename,
            score=score,
            rating_mu=rating_mu,
            rating_sigma=rating_sigma,
            comparison_count=comparison_count,
            touch_timestamp=touch_timestamp,
        )

    def update_image_tags(self, filename: str, prompt_tags: str) -> bool:
        return update_image_tags(filename, prompt_tags)
    def clear_all_images(self) -> int:
        return clear_all_images()

    def reset_all_image_ratings(self, score: float) -> bool:
        return reset_all_image_ratings(score=score)
