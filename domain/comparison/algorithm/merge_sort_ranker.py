"""Public orchestration layer for step01 pair selection and comparison recording."""

from __future__ import annotations

import time

from ....core.observability.logger import get_logger, ModuleLogger
from .graph_helpers import filter_excluded_images
from .phase_order import select_pair

from ....domain.ports.graph import CrystalGraphPort
from ....domain.ports.comparison import PairingProcessorPort

logger: ModuleLogger = get_logger(__name__)


def select_pair_for_comparison(
    exclude_set: set[str] | None,
    crystal_graph: CrystalGraphPort,
    pairing_processor: PairingProcessorPort,
) -> tuple[tuple[str, str] | None, int | None]:
    """Select the next pair of images to compare.

    Returns ``(pair, phase_index)`` where ``pair`` is ``(filename_a,
    filename_b)`` or ``None`` and ``phase_index`` is a PHASES list index
    (owned by phase_order, whose name lookup is the stable phase identity)
    or ``None``.
    """
    _start = time.perf_counter()
    cached = crystal_graph.get_images_snapshot()
    if cached is None:
        cached = [node.data for node in crystal_graph.get_all_nodes()]
        crystal_graph.set_images_snapshot(cached)
    if len(cached) < 2:
        logger.warning(
            f"select_pair_for_comparison: <2 images ({time.perf_counter() - _start:.4f}s)"
        )
        return None, None

    cg: CrystalGraphPort = crystal_graph
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

    pair, phase_index = select_pair(cached, candidate_images, cg, pairing_processor)

    if not pair:
        logger.warning(f"no pair", start_timer=_start)
        return None, None

    return pair, phase_index
