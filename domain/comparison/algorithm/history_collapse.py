"""Pure domain collapse routine for historical comparison rows.

This helper keeps the deterministic ordering, missing-node, self-link,
same-direction, and contradiction checks in the domain layer while leaving
SQLite and file I/O out of the algorithm.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone


def canonicalize_pair(filename_a: str, filename_b: str) -> tuple[str, str]:
    first = str(filename_a)
    second = str(filename_b)
    canon = sorted((first, second))
    return canon[0], canon[1]


def safe_parse_timestamp(timestamp: str | None) -> tuple[int, datetime]:
    if not timestamp:
        return 1, datetime.min.replace(tzinfo=timezone.utc)
    ts = str(timestamp).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(ts)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return 0, parsed


def _sort_key(row: dict[str, object]) -> tuple[datetime, int]:
    return (
        safe_parse_timestamp(str(row.get("timestamp") or ""))[1],
        int(row.get("id", 0)),
    )


def collapse_comparison_history(
    rows: list[dict[str, object]],
    valid_filenames: set[str],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    """Collapse comparison rows to their canonical survivor set.

    Returns the kept rows in deterministic order, along with the same
    reduction counts used by the repository disruptor semantics.
    """

    missing_nodes_removed = 0
    self_links_removed = 0
    same_direction_duplicates_removed = 0
    contradictions_removed = 0

    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        filename_a = str(row.get("filename_a", ""))
        filename_b = str(row.get("filename_b", ""))
        if filename_a not in valid_filenames or filename_b not in valid_filenames:
            missing_nodes_removed += 1
            continue
        if filename_a == filename_b:
            self_links_removed += 1
            continue
        canon_a, canon_b = canonicalize_pair(filename_a, filename_b)
        row["filename_a"] = canon_a
        row["filename_b"] = canon_b
        grouped[(canon_a, canon_b)].append(row)

    kept_rows: list[dict[str, object]] = []
    for pair_rows in grouped.values():
        by_winner: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in pair_rows:
            by_winner[str(row["winner"])].append(row)

        survivors_by_winner: list[dict[str, object]] = []
        for same_winner_rows in by_winner.values():
            ordered = sorted(same_winner_rows, key=_sort_key)
            if len(ordered) > 1:
                same_direction_duplicates_removed += len(ordered) - 1
            survivors_by_winner.append(ordered[-1])

        survivors_by_winner.sort(key=_sort_key)
        if len(survivors_by_winner) > 1:
            contradictions_removed += len(survivors_by_winner) - 1
        kept_rows.append(survivors_by_winner[-1])

    kept_rows.sort(key=_sort_key)

    counts = {
        "missing_nodes_removed": missing_nodes_removed,
        "self_links_removed": self_links_removed,
        "same_direction_duplicates_removed": same_direction_duplicates_removed,
        "contradictions_removed": contradictions_removed,
        "kept": len(kept_rows),
    }
    return kept_rows, counts
