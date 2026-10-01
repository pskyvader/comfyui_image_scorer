"""Reusable graph-query helpers for the ranking algorithm.

Each helper takes the graph as a parameter and avoids duplicating the same
node-grouping / filtering patterns that appear across multiple pair-selection
strategies.

Pair canonicalization and timestamp ordering are owned by
``domain.comparison.algorithm.history_collapse`` to ensure a single source of
truth (P-02).
"""

from __future__ import annotations

import time

from ....core.configuration.settings import config
from ...graph.node_proxy import NodeProxy
from ...comparison.algorithm.history_collapse import canonicalize_pair, safe_parse_timestamp

from ....domain.ports.graph import CrystalGraphPort
from ....domain.ports.repository import ImageRow


def stable_seed_pool(images: list[NodeProxy]) -> list[NodeProxy]:
    seed_percentage = int(config["ranking"]["seed_percentage"])
    seed_target_comparisons = int(config["ranking"]["seed_target_comparisons"])
    filtered_images: list[NodeProxy] = [
        node for node in images if node.comparison_count >= seed_target_comparisons
    ]
    seed_size: int = max(1, len(images) * seed_percentage // 100, len(filtered_images))
    by_comps: list[NodeProxy] = sorted(
        images, key=lambda node: node.comparison_count, reverse=True
    )
    return [node for node in by_comps[:seed_size]]


# ---------------------------------------------------------------------------
# Grouping helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Public-API helpers (exposed via merge_sort_ranker re-exports)
# ---------------------------------------------------------------------------


def is_collapsable_pair(filename_a: str, filename_b: str, cg: CrystalGraphPort) -> bool:
    """Check if a pair is collapsible (both top or both bottom in same component, no common chains)."""
    _start = time.perf_counter()
    node_a = cg.get_node(filename_a)
    node_b = cg.get_node(filename_b)
    if not node_a or not node_b:

        return False

    comp_a = cg.get_component(node_id=filename_a)
    comp_b = cg.get_component(node_id=filename_b)
    if not comp_a or not comp_b or comp_a.id != comp_b.id:

        return False

    both_top = node_a.is_top() and node_b.is_top()
    both_bottom = node_a.is_bottom() and node_b.is_bottom()

    if not (both_top or both_bottom):

        return False

    result = not cg.are_in_same_path(filename_a, filename_b)

    return result


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------


def filter_excluded_images(
    images: list[ImageRow],
    exclude_set: set[str],
) -> list[ImageRow]:
    """Remove images whose filename is in exclude_set."""
    _start = time.perf_counter()
    if not exclude_set:
        return images

    result: list[ImageRow] = []
    for img in images:
        filename = img["filename"]
        if filename not in exclude_set:
            result.append(img)

    return result


def collapse_comparisons(
    comparisons: list[dict[str, object]],
    valid_filenames: set[str],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    """Collapse comparison history to a deterministic survivor set.

    Applies missing-node removal, self-link removal, same-direction duplicate
    removal, and contradiction resolution. Returns the surviving rows and a
    dict of removed counts.
    """
    missing_nodes_removed = 0
    self_links_removed = 0
    same_direction_duplicates_removed = 0
    contradictions_removed = 0

    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in comparisons:
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
        key = (canon_a, canon_b)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(row)

    kept_rows: list[dict[str, object]] = []
    for pair_rows in grouped.values():
        by_winner: dict[str, list[dict[str, object]]] = {}
        for row in pair_rows:
            winner = str(row["winner"])
            if winner not in by_winner:
                by_winner[winner] = []
            by_winner[winner].append(row)

        survivors_by_winner: list[dict[str, object]] = []
        for same_winner_rows in by_winner.values():
            ordered = sorted(
                same_winner_rows,
                key=lambda r: (
                    safe_parse_timestamp(r.get("timestamp"))[1],
                    int(r.get("id", 0)),
                ),
            )
            if len(ordered) > 1:
                same_direction_duplicates_removed += len(ordered) - 1
            survivors_by_winner.append(ordered[-1])

        survivors_by_winner.sort(
            key=lambda r: (
                safe_parse_timestamp(r.get("timestamp"))[1],
                int(r.get("id", 0)),
            )
        )
        if len(survivors_by_winner) > 1:
            contradictions_removed += len(survivors_by_winner) - 1
        kept_rows.append(survivors_by_winner[-1])

    kept_rows.sort(
        key=lambda r: (
            safe_parse_timestamp(r.get("timestamp"))[1],
            int(r.get("id", 0)),
        )
    )

    survivors = kept_rows
    counts = {
        "missing_nodes_removed": missing_nodes_removed,
        "self_links_removed": self_links_removed,
        "same_direction_duplicates_removed": same_direction_duplicates_removed,
        "contradictions_removed": contradictions_removed,
        "kept": len(survivors),
    }
    return survivors, counts
