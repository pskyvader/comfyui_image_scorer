"""Public orchestration layer for step01 pair selection and comparison recording."""

from __future__ import annotations

from typing import Any, Protocol
import time

from ....core.observability.logger import get_logger, ModuleLogger
from ..state import get_cached_all_images
from .graph_helpers import (
    filter_excluded_images,
)
from .phase_order import select_pair

logger: ModuleLogger = get_logger(__name__)


class CrystalGraph(Protocol):
    def is_cache_stale(self) -> bool: ...
    def rebuild_from_database(
        self,
        images: list[dict[str, Any]] | None = None,
        comparisons: list[dict[str, Any]] | None = None,
    ) -> None: ...
    def get_node(self, node_id: str | None = None) -> Any: ...
    def get_all_chains(
        self, min_length: int = 0, sort_order: str = "desc"
    ) -> list[tuple[Any, list[Any]]]: ...
    def get_all_nodes(
        self, only_top: bool = False, only_bottom: bool = False
    ) -> list[Any]: ...
    def get_graph_stats(self) -> dict[str, Any]: ...
    def are_in_same_path(self, img1: str, img2: str) -> bool: ...
    def get_main_chain_member_count(self, chain_id: int) -> int: ...


def select_pair_for_comparison(
    exclude_set: set[str] | None,
    crystal_graph: CrystalGraph,
    comparison_repo: Any,
) -> tuple[tuple[str, str] | None, int | None]:
    """Select the next pair of images to compare.

    Returns ``(pair, phase_index)`` where ``pair`` is ``(filename_a,
    filename_b)`` or ``None`` and ``phase_index`` is an int (0=seed,
    1=anchor, 2=collapsible, 3=single_win_loss, 4=refine, 5=chain_merge,
    6=fallback) or ``None``.
    """
    _start = time.perf_counter()
    cached = get_cached_all_images()
    if len(cached) < 2:
        logger.warning(
            f"select_pair_for_comparison: <2 images ({time.perf_counter() - _start:.4f}s)"
        )
        return None, None

    cg: CrystalGraph = crystal_graph
    # if cg.is_cache_stale():
    #     logger.debug("stale from select pair")
    #     cg.rebuild_from_database()

    combined_exclude: set[str] = set()
    if exclude_set:
        combined_exclude.update(exclude_set)
    candidate_images = filter_excluded_images(cached, combined_exclude)

    if len(candidate_images) < 2:
        logger.warning(
            "only %d images after exclusion, cannot form pair",
            len(candidate_images),
            start_timer=_start,
        )
        return None, None

    pair, phase_index = select_pair(cached, candidate_images, cg, comparison_repo)

    if not pair:
        logger.warning(f"no pair", start_timer=_start)
        return None, None

    return pair, phase_index
