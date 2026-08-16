"""Reusable graph-query helpers for the ranking algorithm.

Each helper takes the graph as a parameter and avoids duplicating the same
node-grouping / filtering patterns that appear across multiple pair-selection
strategies.
"""

from typing import Any, Protocol
import time

from ....core.configuration.settings import config
from ...graph.node_proxy import NodeProxy


class CrystalGraph(Protocol):
    def get_node(self, node_id: str | None = None) -> Any: ...
    def get_component(self, node_id: str | None = None, component_id: int | None = None, chain_id: int | None = None) -> Any: ...
    def are_in_same_path(self, img1: str, img2: str) -> bool: ...


def pair_key(filename_a: str, filename_b: str) -> tuple[str, str]:
    return (
        (filename_a, filename_b)
        if filename_a <= filename_b
        else (filename_b, filename_a)
    )


def stable_seed_pool(images: list[NodeProxy]) -> set[str]:
    seed_percentage = int(config["ranking"]["seed_percentage"])
    seed_size = max(1, len(images) * seed_percentage // 100)
    by_comps = sorted(images, key=lambda node: node.comparison_count, reverse=True)
    return {node.filename for node in by_comps[:seed_size]}


# ---------------------------------------------------------------------------
# Grouping helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Public-API helpers (exposed via merge_sort_ranker re-exports)
# ---------------------------------------------------------------------------


def is_collapsable_pair(filename_a: str, filename_b: str, cg: CrystalGraph) -> bool:
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
    images: list[dict[str, Any]],
    exclude_set: set[str],
) -> list[dict[str, Any]]:
    """Remove images whose filename is in exclude_set."""
    _start = time.perf_counter()
    if not exclude_set:
        return images

    result: list[dict[str, Any]] = []
    for img in images:
        filename = img["filename"]
        if filename not in exclude_set:
            result.append(img)

    return result
