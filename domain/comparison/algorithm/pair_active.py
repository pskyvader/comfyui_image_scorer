"""Active pair selection for the TrueSkill-based step01 flow."""

from __future__ import annotations

import math
import random
import time

from ....core.configuration.settings import config
from ....core.observability.logger import get_logger, ModuleLogger
from ...graph.chain_proxy import ChainProxy
from ...graph.node_proxy import NodeProxy
from ....domain.ports.comparison import PairingProcessorPort
from ....domain.ports.graph import CrystalGraphPort

from .pair_candidates import (
    collect_long_chain_opponents,
    collect_small_chain_anchors,
    get_seed_coverage_ready_pool_length,
    get_seed_coverage_under_target_nodes,
    select_anchor_insert_node,
    select_uncertainty_refine_anchor,
)
from .pair_opponents import (
    get_anchor_insert_opponents,
    get_compatible_nodes,
    get_seed_coverage_opponents,
    get_uncertainty_refine_opponents,
)
from .pair_pipeline import (
    Pair,
    closest_score_pair,
    filter_cross_chain_pairs,
    filter_existing_pairs,
    filter_uncertainty_refine_pairs,
    form_candidate_pairs,
    sigma_range_cap,
)

logger: ModuleLogger = get_logger(__name__)


# =============================================================================
# LOGGING AND CACHE HELPERS
# =============================================================================

_MAX_RETRIES = 5


def _key_diff(pair: Pair) -> float:
    return abs(pair[0].trueskill_score - pair[1].trueskill_score)


def _key_link_count(node: NodeProxy) -> int:
    return node.link_count


def _key_position_gap(pair: Pair) -> tuple[int, int]:
    return (
        abs(pair[0].position_score - pair[1].position_score),
        pair[1].link_count,
    )


def _log_selected_pair(result: Pair, _start: float) -> None:
    """Log the standard success message for all phases."""
    logger.debug(
        f"selected pair: {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
        start_timer=_start,
    )


def _mark_recent(pairing_processor: PairingProcessorPort, filename: str) -> None:
    """Append a filename to the recent-images deque under its lock."""
    with pairing_processor.recent_lock:
        if filename not in pairing_processor.recent_images:
            pairing_processor.recent_images.append(filename)


def _log_sigma_miss(pair_list: list[Pair], _start: float) -> None:
    """Log closest pair details when nothing falls inside the sigma range."""
    if not pair_list:
        return
    pair_list.sort(key=_key_diff)
    closest: Pair = pair_list[0]
    logger.debug(
        "no valid pair within the anchor's sigma range."
        f" Closest:{closest[0].trueskill_score - closest[1].trueskill_score:.4f}"
        f" Sigma:{closest[0].sigma_uncertainty:.4f}",
        start_timer=_start,
    )


# =============================================================================
# PAIR SELECTION
# =============================================================================


def select_exact_count_pair(
    candidate_nodes: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
    pairing_processor: PairingProcessorPort,
    *,
    bottom: bool,
    count: int,
    closest: bool,
    retry: int,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Pair an anchor with exactly `count` wins (bottom) or losses (top) inside its pool."""
    _start: float = time.perf_counter()
    pool: list[NodeProxy] = []
    for node in candidate_nodes:
        links: list[NodeProxy] = (
            node.get_links(worse_than=True)
            if bottom
            else node.get_links(better_than=True)
        )
        if len(links) == count:
            pool.append(node)
    if len(pool) < 2:
        logger.debug(
            f"exact-count pool too small ({'bottom' if bottom else 'top'}, count {count}): {len(pool)}",
            start_timer=_start,
        )
        return None

    pool_size: int = len(pool)
    anchor_index: int = random.randrange(pool_size)
    node_a: NodeProxy = pool.pop(anchor_index)
    pair_list: list[Pair] = form_candidate_pairs(node_a, pool)
    pair_list = filter_existing_pairs(pair_list, existing_pair_set)
    if not pair_list:
        logger.debug("no new pair inside the exact-count pool", start_timer=_start)
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        result: tuple[NodeProxy, NodeProxy] | None = select_exact_count_pair(
            candidate_nodes,
            existing_pair_set,
            pairing_processor,
            bottom=bottom,
            count=count,
            closest=closest,
            retry=retry + 1,
        )
        return result

    pair_list.sort(key=_key_position_gap)
    result = pair_list[0] if pair_list else None

    # sigma_cap: float = sigma_range_cap(node_a)
    # result = closest_score_pair(pair_list, closest, sigma_cap)

    if result is None:
        _mark_recent(pairing_processor, node_a.filename)
        if retry <= _MAX_RETRIES:
            result = select_exact_count_pair(
                candidate_nodes,
                existing_pair_set,
                pairing_processor,
                bottom=bottom,
                count=count,
                closest=closest,
                retry=retry + 1,
            )
            return result
        _log_sigma_miss(pair_list, _start)
        return closest_score_pair(pair_list, closest, math.inf)
    return result


def _middle_matching_count(node: NodeProxy) -> int:
    """Distance to leaving the middle pool on whichever side is closest."""
    return max(node.known_better_count, node.known_worse_count)


def _middle_anchor_key(node: NodeProxy) -> tuple[int, int]:
    """Order candidates by nearest exit, then by the direction of their chain position."""
    prefer_better_side: bool = node.known_better_count >= node.known_worse_count
    position_key: int = (
        node.position_score if prefer_better_side else -node.position_score
    )
    return -_middle_matching_count(node), position_key


def _middle_opponent_key(item: tuple[bool, int, NodeProxy]) -> tuple[int, int]:
    """Order opponents by how close their matching count is to the anchor's."""
    prefer_better_side, anchor_count, opponent = item
    side_count: int = (
        opponent.known_better_count
        if prefer_better_side
        else opponent.known_worse_count
    )
    position_key: int = (
        opponent.position_score if prefer_better_side else -opponent.position_score
    )
    return abs(side_count - anchor_count), position_key


# =============================================================================
# PHASE ORCHESTRATION
# =============================================================================


def phase_seed_coverage(
    candidate_nodes: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
    seed_pool: list[NodeProxy],
    all_images_length: int,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Select a similar untested pair while the seed pool is below its target."""
    _start: float = time.perf_counter()
    ready_seed_pool_length: int | None = get_seed_coverage_ready_pool_length(
        seed_pool, all_images_length
    )
    if ready_seed_pool_length is None:
        logger.info("seed pool target reached", start_timer=_start)
        return None

    under_seed_target: list[NodeProxy] = get_seed_coverage_under_target_nodes(
        candidate_nodes
    )
    node_a: NodeProxy | None = (
        random.choice(under_seed_target) if under_seed_target else None
    )
    if node_a is None:
        logger.debug("no eligible anchor", start_timer=_start)
        return None
    compatible_nodes: list[NodeProxy] | None = get_seed_coverage_opponents(
        under_seed_target, node_a, ready_seed_pool_length, all_images_length
    )
    if compatible_nodes is None:
        logger.debug("no compatible opponents", start_timer=_start)
        return None
    pair_list: list[Pair] = form_candidate_pairs(node_a, compatible_nodes)
    pair_list = filter_existing_pairs(pair_list, existing_pair_set)
    sigma_cap: float = sigma_range_cap(node_a)
    result: Pair | None = closest_score_pair(
        pair_list, closest=False, sigma_cap=sigma_cap
    )
    if result is None:
        logger.debug("no eligible pair", start_timer=_start)
        return None
    _log_selected_pair(result, _start)
    return result


def phase_anchor_insert(
    candidate_images: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
    pairing_processor: PairingProcessorPort,
    retry: int = 0,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Pair a low-comparison candidate with an eligible seed-pool opponent."""
    _start: float = time.perf_counter()
    node_a: NodeProxy | None = select_anchor_insert_node(candidate_images)
    if retry > 0:
        logger.debug(
            f"anchor insert retry {retry}",
            start_timer=_start,
        )
    if node_a is None:
        logger.debug(
            "no eligible anchor, pool too small (0 images at or below the insertion target)",
            start_timer=_start,
        )
        return None

    if retry > _MAX_RETRIES:
        logger.debug(
            f"max retries exceeded ({retry}) for anchor insert, switching to node_a count filter",
            start_timer=_start,
        )
        compatible_nodes: list[NodeProxy] | None = get_anchor_insert_opponents(
            candidate_images, node_a, node_a.link_count
        )
    else:
        seed_target_comparisons: int = int(config["ranking"]["seed_target_comparisons"])
        compatible_nodes = get_anchor_insert_opponents(
            candidate_images, node_a, seed_target_comparisons
        )
    if compatible_nodes is None:
        logger.debug("no compatible opponents", start_timer=_start)
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        result: tuple[NodeProxy, NodeProxy] | None = phase_anchor_insert(
            candidate_images, existing_pair_set, pairing_processor, retry + 1
        )
        return result

    pair_list: list[Pair] = form_candidate_pairs(node_a, compatible_nodes)
    pair_list = filter_existing_pairs(pair_list, existing_pair_set)

    pair_list.sort(key=_key_position_gap)
    result = pair_list[0] if pair_list else None

    # sigma_cap: float = sigma_range_cap(node_a)
    # result = closest_score_pair(pair_list, closest=True, sigma_cap=sigma_cap)

    if result is None:
        _log_sigma_miss(pair_list, _start)
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        result = phase_anchor_insert(
            candidate_images, existing_pair_set, pairing_processor, retry + 1
        )
        return result
    _log_selected_pair(result, _start)
    return result


def phase_exact_count_pair(
    candidate_nodes: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
    pairing_processor: PairingProcessorPort,
    bottom: bool,
    count: int,
    closest: bool,
    retry: int = 0,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Pair two nodes from the pool with exactly `count` wins or losses."""
    _start: float = time.perf_counter()
    result: tuple[NodeProxy, NodeProxy] | None = select_exact_count_pair(
        candidate_nodes,
        existing_pair_set,
        pairing_processor,
        bottom=bottom,
        count=count,
        closest=closest,
        retry=retry,
    )
    if result is None:
        return None
    _log_selected_pair(result, _start)
    return result


def phase_chain_middle(
    candidate_images: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
    cg: CrystalGraphPort,
    pairing_processor: PairingProcessorPort,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Resolve the middle image by voting on a candidate about to be ruled out.

    An image can still be the middle only while neither of its proven counts
    has passed half the images. Those counts only grow, so the pool of possible
    middles only ever shrinks. This phase puts the image closest to leaving the
    pool on the left and offers it only images it has never met. Because that
    anchor sits on an edge, either outcome rules at least one image out for
    good and the countdown cannot go back up.

    Candidates are ordered by how close they are to an exit and by chain
    position. Opponents are filtered before being trimmed to the closest
    counts, and the final pair is the closest skill match in that shortlist.
    """
    _start: float = time.perf_counter()
    total_images: int = cg.get_node_count()
    middle_bound: int = total_images // 2
    pool: list[NodeProxy] = []
    for node in candidate_images:
        if (
            node.known_better_count <= middle_bound
            and node.known_worse_count <= middle_bound
        ):
            pool.append(node)
    if len(pool) <= 1:
        logger.debug(
            f"{len(pool)} middle candidates remain, nothing to compare",
            start_timer=_start,
        )
        return None

    pool.sort(key=_middle_anchor_key)
    anchor: NodeProxy = pool[0]
    prefer_better_side: bool = anchor.known_better_count >= anchor.known_worse_count
    anchor_count: int = _middle_matching_count(anchor)
    opponents: list[NodeProxy] = pool[1:]

    ranked: list[tuple[bool, int, NodeProxy]] = [
        (prefer_better_side, anchor_count, opponent) for opponent in opponents
    ]
    ranked.sort(key=_middle_opponent_key)
    lru_size: int = int(config["ranking"]["lru_size"])
    trimmed: list[NodeProxy] = [item[2] for item in ranked[:lru_size]]

    pair_list: list[Pair] = form_candidate_pairs(anchor, trimmed)
    valid_pairs: list[Pair] | None = filter_cross_chain_pairs(
        pair_list, existing_pair_set, cg
    )
    if valid_pairs is None:
        _mark_recent(pairing_processor, anchor.filename)
        logger.debug("no untested opponent for the middle anchor", start_timer=_start)
        return None

    result: Pair | None = closest_score_pair(
        valid_pairs, closest=True, sigma_cap=math.inf
    )
    if result is None:
        _mark_recent(pairing_processor, anchor.filename)
        logger.debug("no pair inside the middle shortlist", start_timer=_start)
        return None
    _log_selected_pair(result, _start)
    return result


def phase_uncertainty_refine(
    candidate_images: list[NodeProxy],
    seed_pool_set: set[str],
    pair_set: set[tuple[str, str]],
    cg: CrystalGraphPort,
    pairing_processor: PairingProcessorPort,
    retry: int = 0,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Pair a high-uncertainty candidate with an eligible seed-pool node."""
    _start: float = time.perf_counter()
    node_a: NodeProxy | None = select_uncertainty_refine_anchor(
        candidate_images, seed_pool_set
    )
    if node_a is None:
        logger.debug(
            "no eligible anchor",
            start_timer=_start,
        )
        return None

    compatible_nodes: list[NodeProxy] | None = get_uncertainty_refine_opponents(
        candidate_images, node_a, seed_pool_set
    )
    if compatible_nodes is None:
        logger.debug("no seed-pool opponents", start_timer=_start)
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        result: tuple[NodeProxy, NodeProxy] | None = phase_uncertainty_refine(
            candidate_images, seed_pool_set, pair_set, cg, pairing_processor, retry + 1
        )
        return result
    pair_list: list[Pair] = form_candidate_pairs(node_a, compatible_nodes)
    filtered_pairs: list[Pair] | None = filter_uncertainty_refine_pairs(
        pair_list, pair_set, cg
    )
    if filtered_pairs is None:
        logger.debug("no valid pair after filtering", start_timer=_start)
        return None

    sigma_cap: float = sigma_range_cap(node_a)
    result = closest_score_pair(filtered_pairs, closest=True, sigma_cap=sigma_cap)

    if result is None:
        _log_sigma_miss(filtered_pairs, _start)
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        result = phase_uncertainty_refine(
            candidate_images, seed_pool_set, pair_set, cg, pairing_processor, retry + 1
        )
        return result
    _log_selected_pair(result, _start)
    return result


def phase_chain_small(
    candidate_images: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
    cg: CrystalGraphPort,
    pairing_processor: PairingProcessorPort,
    retry: int = 0,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Settle small main chains by pairing their extreme nodes with long-chain nodes.

    Anchors are the top and bottom main nodes of each short chain; opponents
    are the main members of the long chains, so a win or loss against the
    anchor's extreme absorbs the whole small chain into the opponent's.
    """
    _start: float = time.perf_counter()
    chain_length_threshold: int = int(config["ranking"]["chain_length_threshold"])
    small_chains: list[ChainProxy] = []
    long_chains: list[ChainProxy] = []
    for chain in cg.get_all_chains(sort_order="asc"):
        if chain.main_length <= chain_length_threshold:
            small_chains.append(chain)
        else:
            long_chains.append(chain)
    if not small_chains:
        logger.debug(
            f"every chain exceeds {chain_length_threshold} main nodes",
            start_timer=_start,
        )
        return None
    if not long_chains:
        logger.debug(
            f"no chain exceeds {chain_length_threshold} main nodes",
            start_timer=_start,
        )
        return None

    anchors: list[NodeProxy] = collect_small_chain_anchors(
        small_chains, candidate_images
    )
    if not anchors:
        logger.debug("no small-chain anchor candidates", start_timer=_start)
        return None
    anchor_pool_size: int = len(anchors)
    anchor_index: int = random.randrange(anchor_pool_size)
    node_a: NodeProxy = anchors.pop(anchor_index)

    opponents: list[NodeProxy] = collect_long_chain_opponents(
        long_chains, candidate_images
    )
    if not opponents:
        logger.debug("no long-chain opponent candidates", start_timer=_start)
        return None
    pair_list: list[Pair] = form_candidate_pairs(node_a, opponents)
    pair_list_filtered: list[Pair] | None = filter_cross_chain_pairs(
        pair_list, existing_pair_set, cg
    )
    if pair_list_filtered is None:
        logger.debug(
            "no valid pair after filtering",
            start_timer=_start,
        )
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        result: tuple[NodeProxy, NodeProxy] | None = phase_chain_small(
            candidate_images, existing_pair_set, cg, pairing_processor, retry + 1
        )
        return result
    sigma_cap: float = sigma_range_cap(node_a)
    result = closest_score_pair(pair_list_filtered, closest=True, sigma_cap=sigma_cap)

    if result is None:
        _log_sigma_miss(pair_list_filtered, _start)
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        result = phase_chain_small(
            candidate_images, existing_pair_set, cg, pairing_processor, retry + 1
        )
        return result
    _log_selected_pair(result, _start)
    return result


def phase_fallback(
    candidate_images: list[NodeProxy],
    pair_set: set[tuple[str, str]],
) -> tuple[NodeProxy, NodeProxy] | None:
    """Return the first untested pair found by scanning candidates in comparison-count order."""
    _start: float = time.perf_counter()
    ordered: list[NodeProxy] = sorted(candidate_images, key=_key_link_count)
    result: Pair | None = None
    for idx, node_a in enumerate(ordered):
        later_nodes: list[NodeProxy] = ordered[idx + 1 :]
        compatible_nodes: list[NodeProxy] | None = get_compatible_nodes(
            later_nodes, node_a
        )
        if compatible_nodes is None:
            continue
        pair_list: list[Pair] = form_candidate_pairs(node_a, compatible_nodes)
        pair_list = filter_existing_pairs(pair_list, pair_set)
        result = pair_list[0] if pair_list else None
        if result is not None:
            break
    if result is None:
        logger.debug("no pair found", start_timer=_start)
        return None
    _log_selected_pair(result, _start)
    return result
