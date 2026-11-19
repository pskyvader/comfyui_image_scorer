"""Reusable graph-query helpers for the ranking algorithm.

Each helper takes the graph as a parameter and avoids duplicating the same
node-grouping / filtering patterns that appear across multiple pair-selection
strategies.
"""

from __future__ import annotations

import math
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
    """Report how many images can still be the middle and how many are ruled out.

    The middle bound is half the images. An image stays eligible while both its
    proven-better and proven-worse counts are at or below that bound. Those
    counts only grow, so the eligible pool only shrinks and the excluded count
    only grows.
    """
    total_images: int = cg.get_node_count()
    middle_bound: int = total_images // 2
    remaining: list[NodeProxy] = []
    highest_known_better: int = 0
    highest_known_worse: int = 0
    for node in cg.get_all_nodes():
        known_better: int = node.known_better_count
        known_worse: int = node.known_worse_count
        if known_better <= middle_bound and known_worse <= middle_bound:
            remaining.append(node)
            highest_known_better = max(highest_known_better, known_better)
            highest_known_worse = max(highest_known_worse, known_worse)
    remaining_count: int = len(remaining)
    resolved: bool = remaining_count == 1
    middle_node: NodeProxy | None = remaining[0] if resolved else None
    est_comparisons_min: int = (
        math.ceil(math.log2(remaining_count)) if remaining_count > 1 else 0
    )
    est_comparisons_max: int = max(0, remaining_count - 1)
    return {
        "resolved": resolved,
        "candidate_filename": (
            middle_node.filename if middle_node is not None else None
        ),
        "target_rank": middle_bound,
        "middle_bound": middle_bound,
        "remaining_count": remaining_count,
        "exited": total_images - remaining_count,
        "highest_known_better": highest_known_better,
        "highest_known_worse": highest_known_worse,
        "est_comparisons_min": est_comparisons_min,
        "est_comparisons_max": est_comparisons_max,
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
