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

    pair_list.sort(
        key=lambda pair: (
            abs(pair[0].position_score - pair[1].position_score),
            pair[1].link_count,
        )
    )
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


_CandidateEntry = tuple[NodeProxy, int, int]
_CandidatePair = tuple[_CandidateEntry, _CandidateEntry]


def _key_cand_better(c: _CandidateEntry) -> int:
    return c[1]


def _key_cand_worse(c: _CandidateEntry) -> int:
    return c[2]


def _key_cand_interval(c: _CandidateEntry) -> int:
    return -(c[1] + c[2])


def _elim_counts(
    entry_a: _CandidateEntry,
    entry_b: _CandidateEntry,
    target_rank: int,
    worse_rank_limit: int,
) -> tuple[int, int]:
    """Return (elim_if_a_wins, elim_if_b_wins) using reachability bounds."""
    _, better_a, worse_a = entry_a
    _, better_b, worse_b = entry_b
    elim_aw: int = int(better_a + 1 > target_rank) + int(worse_b + 1 > worse_rank_limit)
    elim_bw: int = int(better_b + 1 > target_rank) + int(worse_a + 1 > worse_rank_limit)
    return elim_aw, elim_bw


def _narrow_counts(
    entry_a: _CandidateEntry,
    entry_b: _CandidateEntry,
) -> tuple[int, int]:
    """Return (narrow_if_a_wins, narrow_if_b_wins) using interval bounds."""
    _, better_a, worse_a = entry_a
    _, better_b, worse_b = entry_b
    narrow_aw: int = max(0, better_a + 1 - better_b) + max(0, worse_b + 1 - worse_a)
    narrow_bw: int = max(0, better_b + 1 - better_a) + max(0, worse_a + 1 - worse_b)
    return narrow_aw, narrow_bw


def _filter_guaranteed_eliminations(
    pairs: list[_CandidatePair],
    target_rank: int,
    worse_rank_limit: int,
) -> list[_CandidatePair]:
    """Keep pairs with the highest worst-case candidate eliminations."""
    if len(pairs) <= 1:
        return pairs
    scored: list[tuple[int, _CandidatePair]] = [
        (min(_elim_counts(p[0], p[1], target_rank, worse_rank_limit)), p)
        for p in pairs
    ]
    max_score: int = max(s for s, _ in scored)
    return [p for s, p in scored if s == max_score]


def _filter_total_eliminations(
    pairs: list[_CandidatePair],
    target_rank: int,
    worse_rank_limit: int,
) -> list[_CandidatePair]:
    """Keep pairs with the highest total expected eliminations."""
    if len(pairs) <= 1:
        return pairs
    scored: list[tuple[int, _CandidatePair]] = [
        (sum(_elim_counts(p[0], p[1], target_rank, worse_rank_limit)), p)
        for p in pairs
    ]
    max_score: int = max(s for s, _ in scored)
    return [p for s, p in scored if s == max_score]


def _filter_guaranteed_narrowing(
    pairs: list[_CandidatePair],
) -> list[_CandidatePair]:
    """Keep pairs with the highest worst-case interval narrowing."""
    if len(pairs) <= 1:
        return pairs
    scored: list[tuple[int, _CandidatePair]] = [
        (min(_narrow_counts(p[0], p[1])), p) for p in pairs
    ]
    max_score: int = max(s for s, _ in scored)
    return [p for s, p in scored if s == max_score]


def _filter_total_narrowing(
    pairs: list[_CandidatePair],
) -> list[_CandidatePair]:
    """Keep pairs with the highest total interval narrowing."""
    if len(pairs) <= 1:
        return pairs
    scored: list[tuple[int, _CandidatePair]] = [
        (sum(_narrow_counts(p[0], p[1])), p) for p in pairs
    ]
    max_score: int = max(s for s, _ in scored)
    return [p for s, p in scored if s == max_score]


def _prune_middle_candidates(
    candidates: list[_CandidateEntry],
    target_rank: int,
    worse_rank_limit: int,
) -> list[_CandidateEntry]:
    """Select the most informative boundary nodes and flankers for large candidate pools."""
    boundary: list[_CandidateEntry] = [
        c for c in candidates if c[1] == target_rank or c[2] == worse_rank_limit
    ]
    by_better: list[_CandidateEntry] = sorted(
        candidates, key=_key_cand_better, reverse=True
    )[:25]
    by_worse: list[_CandidateEntry] = sorted(
        candidates, key=_key_cand_worse, reverse=True
    )[:25]
    by_narrow: list[_CandidateEntry] = sorted(
        candidates, key=_key_cand_interval, reverse=True
    )[:25]
    seen: set[str] = set()
    pruned: list[_CandidateEntry] = []
    for c in boundary + by_better + by_worse + by_narrow:
        fn: str = c[0].filename
        if fn not in seen:
            seen.add(fn)
            pruned.append(c)
    return pruned


def select_median_flanker_pair(
    middle_candidates: list[tuple[NodeProxy, int, int]],
    target_rank: int,
    total_images: int,
    blocked_pairs: set[tuple[str, str]],
) -> Pair | None:
    """Pick the candidate pair whose comparison eliminates the most candidates.

    Filters unblocked candidate pairs through sequential stages:
    1. Guaranteed (worst-case) candidate eliminations.
    2. Total expected eliminations.
    3. Guaranteed (worst-case) rank interval narrowing.
    4. Total rank interval narrowing.

    Each stage only executes if multiple candidate pairs remain tied.
    """
    if len(middle_candidates) <= 1:
        return None

    worse_rank_limit: int = total_images - 1 - target_rank
    candidates: list[_CandidateEntry] = middle_candidates
    if len(candidates) > 100:
        candidates = _prune_middle_candidates(
            candidates, target_rank, worse_rank_limit
        )

    pairs: list[_CandidatePair] = []
    for i in range(len(candidates)):
        entry_a = candidates[i]
        fn_a: str = entry_a[0].filename
        for j in range(i + 1, len(candidates)):
            entry_b = candidates[j]
            fn_b: str = entry_b[0].filename
            if (fn_a, fn_b) in blocked_pairs or (fn_b, fn_a) in blocked_pairs:
                continue
            pairs.append((entry_a, entry_b))

    if not pairs:
        return None

    pairs = _filter_guaranteed_eliminations(pairs, target_rank, worse_rank_limit)
    if len(pairs) > 1:
        pairs = _filter_total_eliminations(pairs, target_rank, worse_rank_limit)
    if len(pairs) > 1:
        pairs = _filter_guaranteed_narrowing(pairs)
    if len(pairs) > 1:
        pairs = _filter_total_narrowing(pairs)

    best: _CandidatePair = pairs[0]
    return best[0][0], best[1][0]


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

    pair_list.sort(
        key=lambda pair: (
            abs(pair[0].position_score - pair[1].position_score),
            pair[1].link_count,
        )
    )
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
) -> tuple[NodeProxy, NodeProxy] | None:
    """Narrow the exact middle image by comparing its two closest remaining candidates.

    The middle image is the one whose provable rank interval is the only one
    containing the target rank ``(image_count - 1) // 2``. Every remaining
    candidate keeps its interval; each comparison picks the two candidates
    estimated closest to that rank from opposite sides.
    """
    _start: float = time.perf_counter()
    total_images: int = cg.get_node_count()
    target_rank: int = (total_images - 1) // 2
    worse_rank_limit: int = total_images - 1 - target_rank
    middle_candidates: list[tuple[NodeProxy, int, int]] = []
    for node in candidate_images:
        known_better: int = node.known_better_count
        known_worse: int = node.known_worse_count
        if known_better > target_rank or known_worse > worse_rank_limit:
            continue
        middle_candidates.append((node, known_better, known_worse))
    if len(middle_candidates) <= 1:
        logger.debug(
            f"{len(middle_candidates)} middle candidates remain, nothing to compare",
            start_timer=_start,
        )
        return None

    result: Pair | None = None
    blocked_pairs: set[tuple[str, str]] = set()
    attempts: int = 0
    while result is None and attempts <= _MAX_RETRIES:
        pair: Pair | None = select_median_flanker_pair(
            middle_candidates, target_rank, total_images, blocked_pairs
        )
        if pair is None:
            break
        node_a: NodeProxy = pair[0]
        node_b: NodeProxy = pair[1]
        pair_list: list[Pair] = form_candidate_pairs(node_a, [node_b])
        pair_list_filtered: list[Pair] | None = filter_cross_chain_pairs(
            pair_list, existing_pair_set, cg
        )
        if pair_list_filtered is None:
            blocked_pairs.add((node_a.filename, node_b.filename))
            attempts += 1
            continue
        result = pair_list_filtered[0]
    if result is None:
        logger.debug("no unblocked flanker pair available", start_timer=_start)
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
