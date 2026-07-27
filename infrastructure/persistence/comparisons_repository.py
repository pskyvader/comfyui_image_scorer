"""Comparisons table operations."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from comfyui_image_scorer.core.observability.logger import ModuleLogger, get_logger

from comfyui_image_scorer.infrastructure.persistence.database import get_db_connection

logger: ModuleLogger = get_logger(__name__)


def _canonicalize_pair(filename_a: str, filename_b: str) -> tuple[str, str]:
    first = str(filename_a)
    second = str(filename_b)
    canon = sorted((first, second))
    return canon[0], canon[1]


def _safe_parse_timestamp(timestamp: str | None) -> tuple[int, datetime]:
    if not timestamp:
        return 1, datetime.min.replace(tzinfo=timezone.utc)
    ts = str(timestamp).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(ts)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return 0, parsed


def add_historical_comparison(
    filename_a: str,
    filename_b: str,
    winner: str,
    timestamp: str,
    weight: float = 1.0,
    transitive_depth: int = 0,
) -> int:
    """Insert one historical comparison row if an exact copy does not already exist."""
    filename_a = str(filename_a)
    filename_b = str(filename_b)
    winner = str(winner)
    if winner not in (filename_a, filename_b):
        return 0
    canon_a, canon_b = _canonicalize_pair(filename_a, filename_b)
    timestamp_value = str(timestamp)

    with get_db_connection() as conn:
        exists = conn.execute(
            """
            SELECT id FROM comparisons
            WHERE filename_a=? AND filename_b=? AND winner=? AND timestamp=? AND weight=? AND transitive_depth=?
            """,
            (
                canon_a,
                canon_b,
                winner,
                timestamp_value,
                float(weight),
                int(transitive_depth),
            ),
        ).fetchone()
        if exists:
            return int(exists["id"])

        cur = conn.execute(
            """
            INSERT INTO comparisons(filename_a, filename_b, winner, timestamp, weight, transitive_depth)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                canon_a,
                canon_b,
                winner,
                timestamp_value,
                float(weight),
                int(transitive_depth),
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def add_comparison(
    filename_a: str,
    filename_b: str,
    winner: str,
    weight: float = 1.0,
    transitive_depth: int = 0,
    timestamp: str | None = None,
) -> int:
    """Record a comparison result."""
    filename_a = str(filename_a)
    filename_b = str(filename_b)
    winner = str(winner)
    if winner not in (filename_a, filename_b):
        logger.error("Winner must be one of the compared images")
        return 0
    canon_a, canon_b = _canonicalize_pair(filename_a, filename_b)
    timestamp_value = (
        str(timestamp) if timestamp else datetime.now(timezone.utc).isoformat()
    )

    with get_db_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO comparisons(filename_a, filename_b, winner, timestamp, weight, transitive_depth)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                canon_a,
                canon_b,
                winner,
                timestamp_value,
                float(weight),
                int(transitive_depth),
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def comparison_exists_for_pair(filename_a: str, filename_b: str) -> bool:
    canon_a, canon_b = _canonicalize_pair(filename_a, filename_b)
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


def get_recent_comparisons(
    filename: str, days: int = 30, limit: int = 100
) -> list[dict[str, Any]]:
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM comparisons
            WHERE (filename_a=? OR filename_b=?)
            AND timestamp > ?
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            (filename, filename, cutoff_date.isoformat(), limit),
        ).fetchall()
        return [dict(row) for row in rows]


def get_comparison_count(filename: str) -> int:
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM comparisons
            WHERE filename_a=? OR filename_b=?
            """,
            (filename, filename),
        ).fetchone()
        return int(row["cnt"]) if row else 0


def get_total_comparisons() -> int:
    with get_db_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM comparisons").fetchone()
        return int(row["cnt"]) if row else 0


def get_skipped_comparison_count() -> int:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM comparisons WHERE weight < 1.0"
        ).fetchone()
        return int(row["cnt"]) if row else 0


def get_all_comparisons(weight: float | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM comparisons"
    values: list[Any] = []
    if weight is not None:
        query += " WHERE weight=?"
        values.append(float(weight))
    query += " ORDER BY timestamp ASC, id ASC"

    with get_db_connection() as conn:
        rows = conn.execute(query, tuple(values)).fetchall()
        return [dict(row) for row in rows]


def get_images_with_only_wins() -> list[str]:
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT DISTINCT winner AS filename FROM comparisons
            EXCEPT
            SELECT CASE WHEN winner = filename_a THEN filename_b ELSE filename_a END
            FROM comparisons
            """).fetchall()
        return [str(row["filename"]) for row in rows]


def get_images_with_only_losses() -> list[str]:
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT CASE WHEN winner = filename_a THEN filename_b ELSE filename_a END AS filename
            FROM comparisons
            EXCEPT
            SELECT DISTINCT winner FROM comparisons
            """).fetchall()
        return [str(row["filename"]) for row in rows]


def delete_comparisons_for_image(filename: str) -> int:
    with get_db_connection() as conn:
        cur = conn.execute(
            "DELETE FROM comparisons WHERE filename_a=? OR filename_b=?",
            (filename, filename),
        )
        conn.commit()
        return max(int(cur.rowcount or 0), 0)


def delete_comparison_by_id(comp_id: int) -> int:
    with get_db_connection() as conn:
        cur = conn.execute("DELETE FROM comparisons WHERE id = ?", (int(comp_id),))
        conn.commit()
        return max(int(cur.rowcount or 0), 0)


def delete_comparison(filename_a: str, filename_b: str, winner: str) -> int:
    filename_a = str(filename_a)
    filename_b = str(filename_b)
    winner = str(winner)
    if winner not in (filename_a, filename_b):
        logger.error("Winner must be one of the compared images")
        return 0
    canon_a, canon_b = _canonicalize_pair(filename_a, filename_b)
    with get_db_connection() as conn:
        cur = conn.execute(
            """
            DELETE FROM comparisons
            WHERE filename_a=? AND filename_b=? AND winner=?
            """,
            (canon_a, canon_b, winner),
        )
        conn.commit()
        return max(int(cur.rowcount or 0), 0)


def clean_comparisons() -> dict[str, int]:
    """Clean imported comparison history before any rating replay."""
    with get_db_connection() as conn:
        image_rows = conn.execute("SELECT filename FROM images").fetchall()
        valid_filenames = {str(row["filename"]) for row in image_rows}
        rows = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM comparisons ORDER BY timestamp ASC, id ASC"
            ).fetchall()
        ]

    missing_nodes_removed = 0
    self_links_removed = 0
    same_direction_duplicates_removed = 0
    contradictions_removed = 0

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        filename_a = str(row.get("filename_a", ""))
        filename_b = str(row.get("filename_b", ""))
        if filename_a not in valid_filenames or filename_b not in valid_filenames:
            missing_nodes_removed += 1
            continue
        if filename_a == filename_b:
            self_links_removed += 1
            continue
        canon_a, canon_b = _canonicalize_pair(filename_a, filename_b)
        row["filename_a"] = canon_a
        row["filename_b"] = canon_b
        grouped[(canon_a, canon_b)].append(row)

    kept_rows: list[dict[str, Any]] = []
    for pair_rows in grouped.values():
        by_winner: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in pair_rows:
            by_winner[str(row["winner"])].append(row)

        survivors_by_winner: list[dict[str, Any]] = []
        for same_winner_rows in by_winner.values():
            ordered = sorted(
                same_winner_rows,
                key=lambda row: (
                    _safe_parse_timestamp(row.get("timestamp"))[1],
                    int(row.get("id", 0)),
                ),
            )
            if len(ordered) > 1:
                same_direction_duplicates_removed += len(ordered) - 1
            survivors_by_winner.append(ordered[-1])

        survivors_by_winner.sort(
            key=lambda row: (
                _safe_parse_timestamp(row.get("timestamp"))[1],
                int(row.get("id", 0)),
            )
        )
        if len(survivors_by_winner) > 1:
            contradictions_removed += len(survivors_by_winner) - 1
        kept_rows.append(survivors_by_winner[-1])

    kept_rows.sort(
        key=lambda row: (
            _safe_parse_timestamp(row.get("timestamp"))[1],
            int(row.get("id", 0)),
        )
    )
    kept_ids = {int(row["id"]) for row in kept_rows if row.get("id") is not None}

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
                conn.execute(
                    f"INSERT INTO _keep_ids (id) VALUES {placeholders}", batch
                )
            conn.execute(
                "DELETE FROM comparisons WHERE id NOT IN (SELECT id FROM _keep_ids)"
            )
            conn.execute("DROP TABLE _keep_ids")
        else:
            conn.execute("DELETE FROM comparisons")
        conn.commit()

    return {
        "missing_nodes_removed": missing_nodes_removed,
        "self_links_removed": self_links_removed,
        "same_direction_duplicates_removed": same_direction_duplicates_removed,
        "contradictions_removed": contradictions_removed,
        "kept": len(kept_rows),
    }
