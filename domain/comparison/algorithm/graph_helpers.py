"""Reusable graph-query helpers for the ranking algorithm.

Each helper takes the graph as a parameter and avoids duplicating the same
node-grouping / filtering patterns that appear across multiple pair-selection
strategies.
"""

from __future__ import annotations

import time

from ....core.configuration.settings import config
from ...graph.node_proxy import NodeProxy
from ....domain.ports.graph import CrystalGraphPort
from ....domain.ports.repository import ImageRow


def stable_seed_pool(images: list[NodeProxy]) -> list[NodeProxy]:
    seed_percentage = int(config["ranking"]["seed_percentage"])
    seed_target_comparisons = int(config["ranking"]["seed_target_comparisons"])
    filtered_images: list[NodeProxy] = [
        node for node in images if node.link_count >= seed_target_comparisons
    ]
    seed_size: int = max(1, len(images) * seed_percentage // 100, len(filtered_images))
    by_comps: list[NodeProxy] = sorted(
        images, key=lambda node: node.link_count, reverse=True
    )
    return [node for node in by_comps[:seed_size]]


def count_exact_result_nodes(cg: CrystalGraphPort, bottom: bool, count: int) -> int:
    """Count candidate nodes with exactly `count` wins (bottom) or losses."""
    total: int = 0
    for node in cg.get_all_nodes():
        links: list[NodeProxy] = (
            node.get_links(worse_than=True)
            if bottom
            else node.get_links(better_than=True)
        )
        if len(links) == count:
            total += 1
    return total


def describe_median_status(cg: CrystalGraphPort) -> dict[str, object]:
    """Report the exact-middle resolution state over all graph images.

    The middle image is the one whose provable rank interval is the only one
    containing the target rank ``(image_count - 1) // 2``; the interval of an
    image spans its known better/worse counts. The most-informed remaining
    candidate (narrowest interval) provides the reported better/worse balance.
    """
    total_images: int = cg.get_node_count()
    target_rank: int = (total_images - 1) // 2
    worse_rank_limit: int = total_images - 1 - target_rank
    remaining: list[NodeProxy] = []
    for node in cg.get_all_nodes():
        known_better: int = node.known_better_count
        known_worse: int = node.known_worse_count
        if known_better <= target_rank and known_worse <= worse_rank_limit:
            remaining.append(node)
    best: NodeProxy | None = None
    best_width: int | None = None
    for node in remaining:
        interval_width: int = (
            total_images - 1 - node.known_worse_count - node.known_better_count
        )
        if best_width is None or interval_width < best_width:
            best = node
            best_width = interval_width
    resolved: bool = len(remaining) == 1
    middle_node: NodeProxy | None = best if resolved else None
    return {
        "resolved": resolved,
        "candidate_filename": (
            middle_node.filename if middle_node is not None else None
        ),
        "remaining_count": len(remaining),
        "known_better": best.known_better_count if best is not None else 0,
        "known_worse": best.known_worse_count if best is not None else 0,
    }


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
