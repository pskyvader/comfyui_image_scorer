"""Active pair selection for the TrueSkill-based step01 flow."""

from __future__ import annotations

import random
import time
from typing import Iterator

from ....core.configuration.settings import config
from ....core.observability.logger import get_logger, ModuleLogger
from ...graph.chain_proxy import ChainProxy
from ...graph.node_proxy import NodeProxy
from ....domain.ports.comparison import PairingProcessorPort
from ....domain.ports.graph import CrystalGraphPort

from .pair_candidates import (
    collect_chain_midpoints,
    get_collapsible_candidates,
    get_seed_coverage_ready_pool_length,
    get_seed_coverage_under_target_nodes,
    get_single_win_loss_candidate_lanes,
    iter_chain_merge_chain_pairs,
    prepare_single_win_loss_lane,
    select_anchor_insert_node,
    select_uncertainty_refine_anchor,
)
from .pair_opponents import (
    get_anchor_insert_opponents,
    get_branch_chain_compatible_nodes,
    get_compatible_nodes,
    get_seed_coverage_opponents,
    get_uncertainty_refine_opponents,
)
from .pair_pipeline import (
    Pair,
    closest_score_pair,
    filter_chain_merge_pairs,
    filter_chain_middle_pairs,
    filter_existing_pairs,
    filter_uncertainty_refine_pairs,
    form_candidate_pairs,
    get_chain_merge_pair_candidates,
)

logger: ModuleLogger = get_logger(__name__)


# =============================================================================
# LOGGING AND CACHE HELPERS
# =============================================================================

_MAX_RETRIES = 5


def _key_diff(pair: Pair) -> float:
    return abs(pair[0].trueskill_score - pair[1].trueskill_score)


def _key_link_and_diff(pair: Pair) -> tuple[int, float]:
    return (pair[1].link_count, abs(pair[0].trueskill_score - pair[1].trueskill_score))


def _key_link_count(node: NodeProxy) -> int:
    return node.link_count


def _log_selected_pair(
    result: Pair, _start: float, phase: str = "", retries: int = 0
) -> None:
    """Log the standard success message for all phases."""
    logger.debug(
        f"{phase}: selected pair (Retries:{retries}): {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
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
    result: Pair | None = closest_score_pair(pair_list, closest=False)
    if result is None:
        logger.debug("no eligible pair", start_timer=_start)
        return None
    _log_selected_pair(result, _start, "seed coverage")
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
    if node_a is None:
        logger.debug(
            "no eligible anchor, pool too small (0 images at or below the insertion target)",
            start_timer=_start,
        )
        return None

    compatible_nodes: list[NodeProxy] | None = get_anchor_insert_opponents(
        candidate_images, node_a
    )
    if compatible_nodes is None:
        logger.debug("no compatible opponents", start_timer=_start)
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        return phase_anchor_insert(
            candidate_images, existing_pair_set, pairing_processor, retry + 1
        )

    pair_list: list[Pair] = form_candidate_pairs(node_a, compatible_nodes)
    pair_list = filter_existing_pairs(pair_list, existing_pair_set)
    result: Pair | None = closest_score_pair(pair_list, closest=True)
    if result is None:
        pair_list.sort(key=_key_diff)
        sigma_range_multiplier: float = float(
            config["ranking"]["sigma_range_multiplier"]
        )
        logger.debug(
            "no valid pair within the anchor's sigma range."
            f"\n Closest (unfiltered by count):{pair_list[0][0].trueskill_score - pair_list[0][1].trueskill_score:.4f}"
            f"\n Sigma:{pair_list[0][0].sigma_uncertainty:.4f} ( with multiplier: {pair_list[0][0].sigma_uncertainty * sigma_range_multiplier:.4f})"
            f"\n Count:{pair_list[0][0].link_count} vs {pair_list[0][1].link_count}",
            start_timer=_start,
        )
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        return phase_anchor_insert(
            candidate_images, existing_pair_set, pairing_processor, retry + 1
        )
    _log_selected_pair(result, _start, "anchor insert", retry)
    return result


def phase_branch_probe(
    candidate_nodes: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
) -> tuple[NodeProxy, NodeProxy] | None:
    """Test branch-compatible opponents from a randomly selected anchor."""
    _start: float = time.perf_counter()
    if not candidate_nodes:
        logger.debug("no candidates", start_timer=_start)
        return None

    node_a: NodeProxy = random.choice(candidate_nodes)
    compatible_nodes: list[NodeProxy] | None = get_branch_chain_compatible_nodes(
        candidate_nodes, node_a
    )
    if compatible_nodes is None:
        logger.debug("no compatible branch opponents", start_timer=_start)
        return None
    pair_list: list[Pair] = form_candidate_pairs(node_a, compatible_nodes)
    pair_list = filter_existing_pairs(pair_list, existing_pair_set)
    result: Pair | None = closest_score_pair(pair_list, closest=True)

    if result is None:
        logger.debug("no valid branch-compatible pair", start_timer=_start)
        return None
    _log_selected_pair(result, _start, "branch probe")
    return result


def phase_collapsible_pairs(
    candidate_nodes: list[NodeProxy],
    cg: CrystalGraphPort,
    pairing_processor: PairingProcessorPort,
    retry: int = 0,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Anchor on the least-compared node and return its most score-similar same-type partner."""
    _start: float = time.perf_counter()

    nodes, use_bottom, check_list = get_collapsible_candidates(candidate_nodes, cg)

    if len(nodes) < 2:
        logger.info(
            f"no candidates found, len:{len(nodes)}, bottom:{use_bottom}, checklist:{len(check_list)}",
            start_timer=_start,
        )
        return None

    node_a: NodeProxy = random.choice(nodes)
    compatible_nodes: list[NodeProxy] = [
        node for node in nodes if node.filename != node_a.filename
    ]
    if not compatible_nodes:
        logger.debug("no compatible opponents", start_timer=_start)
        _mark_recent(pairing_processor, node_a.filename)
        return None
    pair_list: list[Pair] = form_candidate_pairs(node_a, compatible_nodes)
    result: Pair | None = closest_score_pair(pair_list, closest=False)
    if result is None:
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            pair_list.sort(key=_key_link_and_diff)
            result = pair_list[0] if pair_list else None
    if result is None:
        logger.info(
            f"no pair found for {node_a.filename}, len:{len(nodes)}, bottom:{use_bottom}, checklist:{len(check_list)}",
            start_timer=_start,
        )
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        return phase_collapsible_pairs(
            candidate_nodes, cg, pairing_processor, retry + 1
        )
    _log_selected_pair(result, _start, "collapsible pairs", retry)
    return result


def phase_single_win_loss(
    candidate_nodes: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
    pairing_processor: PairingProcessorPort,
    retry: int = 0,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Select an untested pair from candidates with exactly one win or loss."""
    _start: float = time.perf_counter()
    minimum_count: float = float("inf")
    compatible_nodes: list[NodeProxy]
    result: Pair | None = None
    lanes: Iterator[tuple[bool, bool, list[NodeProxy]]] = (
        get_single_win_loss_candidate_lanes(candidate_nodes)
    )
    errors: int = 0

    for single_win, filtered_only, nodes in lanes:
        if not nodes:
            logger.debug(
                f"lane {'single win' if single_win else 'single loss'} has no eligible anchor",
                start_timer=_start,
            )
            continue

        node_a: NodeProxy = random.choice(nodes)
        compatible_nodes, minimum_count = prepare_single_win_loss_lane(
            node_a,
            nodes,
            single_win,
            filtered_only,
            minimum_count,
        )

        # compatible_nodes: list[NodeProxy] | None = get_compatible_nodes(
        #     partner_nodes, node_a
        # )
        if not compatible_nodes:
            _mark_recent(pairing_processor, node_a.filename)
            errors += 1
            continue
        pair_list: list[Pair] = form_candidate_pairs(node_a, compatible_nodes)
        pair_list = filter_existing_pairs(pair_list, existing_pair_set)

        result: Pair | None = closest_score_pair(pair_list, closest=True)
        if result is None:
            _mark_recent(pairing_processor, node_a.filename)
            errors += 1
            if retry > _MAX_RETRIES:
                pair_list.sort(key=_key_link_and_diff)
                result = pair_list[0] if pair_list else None

        if result is not None:
            break
    if result is None:
        if errors > 0:
            if retry > _MAX_RETRIES:
                return None
            return phase_single_win_loss(
                candidate_nodes, existing_pair_set, pairing_processor, retry + 1
            )
        logger.debug("no pair found", start_timer=_start)
        return None
    _log_selected_pair(result, _start, "single win/loss", retry)
    return result


def phase_chain_middle(
    candidate_images: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
    cg: CrystalGraphPort,
    pairing_processor: PairingProcessorPort,
    retry: int = 0,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Compare mid-chain nodes to resolve the global middle ordering."""
    _start: float = time.perf_counter()
    min_chain_length: int = int(config["ranking"]["chain_middle_min_chain_length"])
    qualifying_chains: list[ChainProxy] = [
        chain
        for chain in cg.get_all_chains(sort_order="asc")
        if chain.main_length < min_chain_length
    ]

    if not qualifying_chains:
        logger.debug(
            f"every chain reached {min_chain_length} nodes",
            start_timer=_start,
        )
        return None

    nodes: list[NodeProxy] = collect_chain_midpoints(
        qualifying_chains, candidate_images, cg
    )
    if not nodes:
        logger.debug(
            f"no midpoint candidates (limit {min_chain_length})",
            start_timer=_start,
        )
        return None

    node_a: NodeProxy = random.choice(nodes)

    compatible_nodes: list[NodeProxy] | None = get_branch_chain_compatible_nodes(
        candidate_images, node_a
    )
    if compatible_nodes is None:
        logger.debug("no compatible branch opponents", start_timer=_start)
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        return phase_chain_middle(
            candidate_images, existing_pair_set, cg, pairing_processor, retry + 1
        )
    pair_list: list[Pair] = form_candidate_pairs(node_a, compatible_nodes)
    pair_list_filtered: list[Pair] | None = filter_chain_middle_pairs(
        pair_list, node_a, existing_pair_set, cg
    )
    if pair_list_filtered is None:
        logger.debug(
            "no valid pair after filtering",
            start_timer=_start,
        )
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        return phase_chain_middle(
            candidate_images, existing_pair_set, cg, pairing_processor, retry + 1
        )
    result: Pair | None = closest_score_pair(pair_list_filtered, closest=False)

    if result is None:
        _log_sigma_miss(pair_list_filtered, _start)
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        return phase_chain_middle(
            candidate_images, existing_pair_set, cg, pairing_processor, retry + 1
        )
    _log_selected_pair(result, _start, "chain middle", retry)
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
        return phase_uncertainty_refine(
            candidate_images, seed_pool_set, pair_set, cg, pairing_processor, retry + 1
        )
    pair_list: list[Pair] = form_candidate_pairs(node_a, compatible_nodes)
    filtered_pairs: list[Pair] | None = filter_uncertainty_refine_pairs(
        pair_list, pair_set, cg
    )
    if filtered_pairs is None:
        logger.debug("no valid pair after filtering", start_timer=_start)
        return None

    result: Pair | None = closest_score_pair(filtered_pairs, closest=True)

    if result is None:
        _log_sigma_miss(filtered_pairs, _start)
        _mark_recent(pairing_processor, node_a.filename)
        if retry > _MAX_RETRIES:
            return None
        return phase_uncertainty_refine(
            candidate_images, seed_pool_set, pair_set, cg, pairing_processor, retry + 1
        )
    _log_selected_pair(result, _start, "uncertainty refine", retry)
    return result


def phase_chain_merge(
    candidate_images: list[NodeProxy],
    cg: CrystalGraphPort,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Select an unconnected pair from two eligible chains to merge their ranking paths."""
    _start: float = time.perf_counter()
    min_chains: int = int(config["ranking"]["minimum_chains_for_pairing"])
    min_comparisons: int = int(config["ranking"]["insertion_target_comparisons"])
    recent_chain_ids: list[int] = cg.get_recent_chain_ids()
    if len(recent_chain_ids) > min_chains:
        recent_chain_ids = recent_chain_ids[min_chains // 2 :]
        cg.set_recent_chain_ids(recent_chain_ids)
    chains: list[list[NodeProxy]] = [
        list(chain_proxy.nodes)
        for chain_proxy in cg.get_all_chains(min_length=1, sort_order="asc")
    ]
    if len(chains) < min_chains:
        logger.info(f"fewer than {min_chains} chains", start_timer=_start)
        return None

    candidate_by_filename: dict[str, NodeProxy] = {
        node.filename: node for node in candidate_images
    }
    result: Pair | None = None
    chosen_chain_indices: tuple[int, int] | None = None
    chosen_chain_sizes: tuple[int, int, int, int] | None = None
    for i, j in iter_chain_merge_chain_pairs(chains, recent_chain_ids, min_chains):
        a_nodes: list[NodeProxy] = [
            candidate_by_filename[node.filename]
            for node in chains[i]
            if node.filename in candidate_by_filename
            and candidate_by_filename[node.filename].link_count > min_comparisons
        ]
        if not a_nodes:
            continue
        a_mid: NodeProxy = a_nodes[len(a_nodes) // 2]

        b_nodes: list[NodeProxy] = [
            candidate_by_filename[node.filename]
            for node in chains[j]
            if node.filename in candidate_by_filename
        ]
        if not b_nodes:
            continue
        b_mid: NodeProxy = b_nodes[len(b_nodes) // 2]

        pair_list: list[Pair] = get_chain_merge_pair_candidates(
            a_nodes, b_nodes, a_mid, b_mid
        )
        pair_list = filter_chain_merge_pairs(pair_list, cg)
        result = pair_list[0] if pair_list else None
        if result is None:
            continue
        chosen_chain_indices = (i, j)
        chosen_chain_sizes = (
            len(a_nodes),
            len(b_nodes),
            len(chains[i]),
            len(chains[j]),
        )
        break

    if result is None or chosen_chain_indices is None or chosen_chain_sizes is None:
        logger.debug(
            f"no valid pair found in shorter {min_chains * 10} chains",
            start_timer=_start,
        )
        return None

    recent_chain_ids.extend(chosen_chain_indices)
    cg.set_recent_chain_ids(recent_chain_ids)
    logger.debug(
        f"chain i={chosen_chain_sizes[0]}({chosen_chain_sizes[2]}),chain j={chosen_chain_sizes[1]}({chosen_chain_sizes[3]})",
        start_timer=_start,
    )
    _log_selected_pair(result, _start, "chain merge")
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
    _log_selected_pair(result, _start, "fallback")
    return result
