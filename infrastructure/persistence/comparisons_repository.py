"""Comparisons table operations."""

from __future__ import annotations

from datetime import datetime, timezone

from ...core.observability.logger import ModuleLogger, get_logger
from ...domain.comparison.algorithm.history_collapse import canonicalize_pair

from .database import get_db_connection

logger: ModuleLogger = get_logger(__name__)


def add_comparison(
    filename_a: str,
    filename_b: str,
    winner: str,
    timestamp: str | None,
) -> int:
    """Record a comparison result."""
    filename_a = str(filename_a)
    filename_b = str(filename_b)
    winner = str(winner)
    if winner not in (filename_a, filename_b):
        logger.error("Winner must be one of the compared images")
        return 0
    canon_a, canon_b = canonicalize_pair(filename_a, filename_b)
    timestamp_value = (
        str(timestamp) if timestamp else datetime.now(timezone.utc).isoformat()
    )

    with get_db_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO comparisons(filename_a, filename_b, winner, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (
                canon_a,
                canon_b,
                winner,
                timestamp_value,
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def comparison_exists_for_pair(filename_a: str, filename_b: str) -> bool:
    canon_a, canon_b = canonicalize_pair(filename_a, filename_b)
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM comparisons WHERE filename_a=? AND filename_b=? LIMIT 1",
            (canon_a, canon_b),
        ).fetchone()
        return row is not None


def clear_all_comparisons() -> int:
    with get_db_connection() as conn:
        cur = conn.execute("DELETE FROM comparisons")
        conn.commit()
        return max(int(cur.rowcount or 0), 0)


def get_total_comparisons() -> int:
    with get_db_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM comparisons").fetchone()
        return int(row["cnt"]) if row else 0


def list_links() -> list[dict[str, object]]:
    query = "SELECT * FROM comparisons"
    query += " ORDER BY timestamp ASC, id ASC"

    with get_db_connection() as conn:
        rows = conn.execute(query, ()).fetchall()
        return [dict(row) for row in rows]


def get_nodes_with_only_wins() -> list[str]:
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT DISTINCT winner AS filename FROM comparisons
            EXCEPT
            SELECT CASE WHEN winner = filename_a THEN filename_b ELSE filename_a END
            FROM comparisons
            """).fetchall()
        return [str(row["filename"]) for row in rows]


def get_nodes_with_only_losses() -> list[str]:
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT CASE WHEN winner = filename_a THEN filename_b ELSE filename_a END AS filename
            FROM comparisons
            EXCEPT
            SELECT DISTINCT winner FROM comparisons
            """).fetchall()
        return [str(row["filename"]) for row in rows]


def clean_comparisons() -> dict[str, int]:
    """Clean imported comparison history before any rating replay.

    Route the duplicate and contradiction collapse policy through the pure
    domain helper and keep the SQLite deletion step in the persistence adapter.
    """
    with get_db_connection() as conn:
        image_rows = conn.execute("SELECT filename FROM images").fetchall()
        valid_filenames = {str(row["filename"]) for row in image_rows}
        rows = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM comparisons ORDER BY timestamp ASC, id ASC"
            ).fetchall()
        ]

    from ...domain.comparison.algorithm.history_collapse import (
        collapse_comparison_history,
    )

    survivors, counts = collapse_comparison_history(rows, valid_filenames)
    kept_ids = {int(row["id"]) for row in survivors if row.get("id") is not None}

    with get_db_connection() as conn:
        if kept_ids:
            conn.execute(
                "CREATE TEMP TABLE IF NOT EXISTS _keep_ids (id INTEGER PRIMARY KEY)"
            )
            conn.execute("DELETE FROM _keep_ids")
            kept_list = sorted(kept_ids)
            batch_size = 900
            for i in range(0, len(kept_list), batch_size):
                batch = kept_list[i : i + batch_size]
                placeholders = ",".join("(?)" for _ in batch)
                conn.execute(f"INSERT INTO _keep_ids (id) VALUES {placeholders}", batch)
            conn.execute(
                "DELETE FROM comparisons WHERE id NOT IN (SELECT id FROM _keep_ids)"
            )
            conn.execute("DROP TABLE _keep_ids")
        else:
            conn.execute("DELETE FROM comparisons")
        conn.commit()

    return counts


class SQLiteComparisonsRepository:
    """Injected implementation of the ComparisonRepository port."""

    def add_comparison(
        self,
        filename_a: str,
        filename_b: str,
        winner: str,
        timestamp: str | None,
    ) -> int:
        return add_comparison(
            filename_a=filename_a,
            filename_b=filename_b,
            winner=winner,
            timestamp=timestamp,
        )

    def comparison_exists_for_pair(self, filename_a: str, filename_b: str) -> bool:
        return comparison_exists_for_pair(filename_a, filename_b)

    def list_links(self) -> list[dict[str, object]]:
        return list_links()

    def get_total_comparisons(self) -> int:
        return get_total_comparisons()

    def clean_comparisons(self) -> dict[str, int]:
        return clean_comparisons()

    def get_nodes_with_only_wins(self) -> list[str]:
        return get_nodes_with_only_wins()

    def get_nodes_with_only_losses(self) -> list[str]:
        return get_nodes_with_only_losses()

    def clear_all_comparisons(self) -> int:
        return clear_all_comparisons()
