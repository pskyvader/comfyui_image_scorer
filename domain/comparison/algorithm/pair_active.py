"""Active pair selection for the TrueSkill-based step01 flow."""

from __future__ import annotations

from collections.abc import Iterator

import random
import time
from tqdm import tqdm

from ....core.observability.logger import get_logger, ModuleLogger
from ...graph.chain_proxy import ChainProxy
from ...graph.node_proxy import NodeProxy
from ....core.configuration.settings import config

from ...comparison.algorithm.history_collapse import canonicalize_pair

from ....domain.ports.graph import CrystalGraphPort

logger: ModuleLogger = get_logger(__name__)

Pair = tuple[NodeProxy, NodeProxy]
_SINGLE_WIN_LOSS_INITIAL_COUNT = 999


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
    ready_seed_pool_length: int | None = _get_seed_coverage_ready_pool_length(
        seed_pool, all_images_length
    )
    if ready_seed_pool_length is None:
        logger.info("seed pool target reached", start_timer=_start)
        return None

    under_seed_target: list[NodeProxy] = _get_seed_coverage_under_target_nodes(
        candidate_nodes
    )
    node_a: NodeProxy | None = _select_seed_coverage_anchor(under_seed_target)
    if node_a is None:
        logger.debug("no eligible anchor", start_timer=_start)
        return None
    compatible_nodes: list[NodeProxy] | None = _get_seed_coverage_opponents(
        under_seed_target, node_a, ready_seed_pool_length, all_images_length
    )
    if compatible_nodes is None:
        logger.debug("no compatible opponents", start_timer=_start)
        return None
    pair_list: list[Pair] = _form_candidate_pairs(node_a, compatible_nodes)
    pair_list = _filter_existing_pairs(pair_list, existing_pair_set)
    closest_pair: Pair | None = _closest_score_pair(pair_list, closest=False)
    result: Pair | None = closest_pair
    if result is None:
        logger.debug("no eligible pair", start_timer=_start)
        return None
    logger.debug(
        f"selected pair: {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
        start_timer=_start,
    )
    return result


def phase_anchor_insert(
    candidate_images: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
) -> tuple[NodeProxy, NodeProxy] | None:
    """Pair a low-comparison candidate with an eligible seed-pool opponent."""
    _start: float = time.perf_counter()
    node_a: NodeProxy | None = _select_anchor_insert_node(
        candidate_images, "position_score"
    )
    if node_a is None:
        logger.debug(
            "no eligible anchor, pool too small (0 images at or below the insertion target)",
            start_timer=_start,
        )
        return None

    compatible_nodes: list[NodeProxy] | None = _get_anchor_insert_opponents(
        candidate_images, node_a
    )
    if compatible_nodes is None:
        logger.debug("no compatible opponents", start_timer=_start)
        return None
    pair_list: list[Pair] = _form_candidate_pairs(node_a, compatible_nodes)
    pair_list = _filter_existing_pairs(pair_list, existing_pair_set)
    result: Pair | None = _closest_score_pair(
        pair_list, closest=True, prefer_least_compared_opponent=False
    )
    if result is None:
        pair_list.sort(
            key=lambda pair: abs(pair[0].trueskill_score - pair[1].trueskill_score),
        )
        logger.debug(
            "no valid pair within the anchor's sigma range."
            f"\n Closest (unfiltered by count):{pair_list[0][0].trueskill_score-pair_list[0][1].trueskill_score:.4f}"
            f"\n Sigma:{pair_list[0][0].sigma_uncertainty:.4f} ( with multiplier: {pair_list[0][0].sigma_uncertainty*config["ranking"]["sigma_range_multiplier"]:.4f})"
            f"\n Count:{pair_list[0][0].link_count} vs {pair_list[0][1].link_count}",
            start_timer=_start,
        )
        return None
    logger.debug(
        f"selected pair: {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
        start_timer=_start,
    )
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
    compatible_nodes: list[NodeProxy] | None = _get_branch_chain_compatible_nodes(
        candidate_nodes, node_a
    )
    if compatible_nodes is None:
        logger.debug("no compatible branch opponents", start_timer=_start)
        return None
    pair_list: list[Pair] = _form_candidate_pairs(node_a, compatible_nodes)
    pair_list = _filter_existing_pairs(pair_list, existing_pair_set)
    result: Pair | None = _closest_score_pair(pair_list, closest=True)

    if result is None:
        logger.debug("no valid branch-compatible pair", start_timer=_start)
        return None
    logger.debug(
        f"selected pair: {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
        start_timer=_start,
    )
    return result


def phase_collapsible_pairs(
    candidate_nodes: list[NodeProxy],
    cg: CrystalGraphPort,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Anchor on the least-compared node and return its most score-similar same-type partner."""
    _start: float = time.perf_counter()

    nodes, use_bottom, check_list = _get_collapsible_candidates(candidate_nodes, cg)

    if len(nodes) < 2:
        logger.info(
            f"no candidates found, len:{len(nodes)}, bottom:{use_bottom}, checklist:{len(check_list)}",
            start_timer=_start,
        )
        return None

    node_a: NodeProxy | None = _find_candidate_node(candidate_nodes, nodes[0].filename)
    if node_a is None:
        logger.debug("selected anchor is not a candidate", start_timer=_start)
        return None
    compatible_nodes: list[NodeProxy] | None = _get_ordered_compatible_nodes(
        candidate_nodes, node_a, nodes, skip_first=True
    )
    if compatible_nodes is None:
        logger.debug("no compatible opponents", start_timer=_start)
        return None
    pair_list: list[Pair] = _form_candidate_pairs(node_a, compatible_nodes)
    closest_pair: Pair | None = _closest_score_pair(pair_list, closest=False)
    result: Pair | None = closest_pair
    if result is None:
        logger.info(
            f"no pair found, len:{len(nodes)}, bottom:{use_bottom}, checklist:{len(check_list)}",
            start_timer=_start,
        )
        return None
    logger.debug(
        f"selected pair: {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
        start_timer=_start,
    )
    return result


def phase_single_win_loss(
    candidate_nodes: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
) -> tuple[NodeProxy, NodeProxy] | None:
    """Select an untested pair from candidates with exactly one win or loss."""
    _start: float = time.perf_counter()
    minimum_count: int = _SINGLE_WIN_LOSS_INITIAL_COUNT
    result: Pair | None = None
    for single_win, filtered_only, nodes in _get_single_win_loss_candidate_lanes(
        candidate_nodes
    ):
        node_a, partner_nodes, minimum_count = _prepare_single_win_loss_lane(
            candidate_nodes,
            nodes,
            single_win,
            filtered_only,
            minimum_count,
        )
        if node_a is None:
            logger.debug(
                f"lane {"single win" if single_win else "single loss"} has no eligible anchor",
                start_timer=_start,
            )
            continue

        compatible_nodes: list[NodeProxy] | None = _get_compatible_nodes(
            partner_nodes, node_a
        )
        if compatible_nodes is None:
            continue
        pair_list: list[Pair] = _form_candidate_pairs(node_a, compatible_nodes)
        pair_list = _filter_existing_pairs(pair_list, existing_pair_set)
        # closest_pair: Pair | None = _closest_score_pair(
        #     pair_list, closest=True, prefer_least_compared_opponent=True
        # )
        pair_list.sort(
            key=lambda pair: (
                pair[1].link_count,
                abs(pair[0].trueskill_score - pair[1].trueskill_score),
            )
        )
        # result = closest_pair
        result = pair_list[0] if pair_list else None
        if result is not None:
            break
    if result is None:
        logger.debug("no pair found", start_timer=_start)
        return None
    logger.debug(
        f"selected pair: {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
        start_timer=_start,
    )
    return result


def phase_chain_middle(
    candidate_images: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
    cg: CrystalGraphPort,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Compare mid-chain nodes to resolve the global middle ordering."""
    _start: float = time.perf_counter()
    qualifying_chains, min_chain_length = _get_chain_candidates(cg)

    if not qualifying_chains:
        logger.debug(
            f"every chain reached {min_chain_length} nodes",
            start_timer=_start,
        )
        return None
    # logger.debug(f"chains {qualifying_chain_count} ", start_timer=_start)

    nodes: list[NodeProxy] = _collect_chain_midpoints(
        qualifying_chains, candidate_images, cg
    )
    if not nodes:
        logger.debug(
            f"no midpoint candidates (limit {min_chain_length})",
            start_timer=_start,
        )
        return None
    # logger.debug(f"nodes:{len(nodes)}", start_timer=_start)
    selected_node = random.choice(nodes)

    node_a: NodeProxy | None = _find_candidate_node(
        candidate_images, selected_node.filename
    )
    if node_a is None:
        logger.debug("selected anchor is not a candidate", start_timer=_start)
        return None

    compatible_nodes: list[NodeProxy] | None = _get_branch_chain_compatible_nodes(
        candidate_images, node_a
    )
    if compatible_nodes is None:
        logger.debug("no compatible branch opponents", start_timer=_start)
        return None
    pair_list: list[Pair] = _form_candidate_pairs(node_a, compatible_nodes)
    pair_list_filtered: list[Pair] | None = _filter_chain_middle_pairs(
        pair_list, node_a, existing_pair_set, cg
    )
    if pair_list_filtered is None:
        logger.debug(
            "no valid pair after filtering",
            start_timer=_start,
        )
        return None
    result: Pair | None = _closest_score_pair(pair_list_filtered)

    if result is None:
        pair_list_filtered.sort(
            key=lambda pair: abs(pair[0].trueskill_score - pair[1].trueskill_score)
        )
        logger.debug(
            "no valid pair within the anchor's sigma range."
            f" Closest:{pair_list_filtered[0][0].trueskill_score-pair_list_filtered[0][1].trueskill_score:.4f}"
            f" Sigma:{pair_list_filtered[0][0].sigma_uncertainty:.4f}",
            start_timer=_start,
        )
        return None
    logger.debug(
        f"selected pair: {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
        start_timer=_start,
    )
    return result


def phase_uncertainty_refine(
    candidate_images: list[NodeProxy],
    seed_pool_set: set[str],
    pair_set: set[tuple[str, str]],
    cg: CrystalGraphPort,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Pair a high-uncertainty candidate with an eligible seed-pool node."""
    _start: float = time.perf_counter()
    node_a: NodeProxy | None = _select_uncertainty_refine_anchor(
        candidate_images, seed_pool_set
    )
    if node_a is None:
        logger.debug(
            "no eligible anchor",
            start_timer=_start,
        )
        return None

    compatible_nodes: list[NodeProxy] | None = _get_uncertainty_refine_opponents(
        candidate_images, node_a, seed_pool_set
    )
    if compatible_nodes is None:
        logger.debug("no seed-pool opponents", start_timer=_start)
        return None
    pair_list: list[Pair] = _form_candidate_pairs(node_a, compatible_nodes)
    filtered_pairs: list[Pair] | None = _filter_uncertainty_refine_pairs(
        pair_list, pair_set, cg
    )
    if filtered_pairs is None:
        logger.debug("no valid pair after filtering", start_timer=_start)
        return None
    # first_pair: Pair | None = _first_pair(filtered_pairs)

    result: Pair | None = _closest_score_pair(filtered_pairs, closest=True)

    if result is None:
        filtered_pairs.sort(
            key=lambda pair: abs(pair[0].trueskill_score - pair[1].trueskill_score)
        )
        logger.debug(
            "no valid pair within the anchor's sigma range."
            f" Closest:{filtered_pairs[0][0].trueskill_score-filtered_pairs[0][1].trueskill_score:.4f}"
            f" Sigma:{filtered_pairs[0][0].sigma_uncertainty:.4f}",
            start_timer=_start,
        )
        return None
    logger.debug(
        f"selected pair: {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
        f" Closest:{result[0].trueskill_score-result[1].trueskill_score:.4f}"
        f" Sigma:{result[0].sigma_uncertainty:.4f}",
        start_timer=_start,
    )
    return result


def phase_chain_merge(
    candidate_images: list[NodeProxy],
    cg: CrystalGraphPort,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Select an unconnected pair from two eligible chains to merge their ranking paths."""
    _start: float = time.perf_counter()
    chains, recent_chain_ids, min_chains, min_comparisons = _get_chain_merge_state(cg)
    if len(chains) < min_chains:
        logger.info(f"fewer than {min_chains} chains", start_timer=_start)
        return None
    # logger.debug(f"shortest chain: {len(chains[0])}, longest: {len(chains[-1])}")

    candidate_by_filename: dict[str, NodeProxy] = {
        node.filename: node for node in candidate_images
    }
    result: Pair | None = None
    chosen_chain_indices: tuple[int, int] | None = None
    chosen_chain_sizes: tuple[int, int, int, int] | None = None
    for i, j in _iter_chain_merge_chain_pairs(chains, recent_chain_ids, min_chains):
        a_nodes: list[NodeProxy] = _get_chain_merge_anchor_nodes(
            chains[i], candidate_by_filename, min_comparisons
        )
        if not a_nodes:
            continue
        a_mid: NodeProxy | None = _select_chain_merge_midpoint(
            candidate_images, a_nodes
        )
        if a_mid is None:
            logger.debug("no anchor midpoint", start_timer=_start)
            continue

        b_nodes: list[NodeProxy] = _get_chain_merge_opponent_nodes(
            chains[j], candidate_by_filename
        )
        if not b_nodes:
            continue
        b_mid: NodeProxy | None = _select_chain_merge_midpoint(
            candidate_images, b_nodes
        )
        if b_mid is None:
            logger.debug("no opponent midpoint", start_timer=_start)
            continue

        pair_list: list[Pair] = _get_chain_merge_pair_candidates(
            candidate_images, a_nodes, b_nodes, a_mid, b_mid
        )
        pair_list = _filter_chain_merge_pairs(pair_list, cg)
        first_pair: Pair | None = _first_pair(pair_list)
        result = first_pair
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
            f"no valid pair found in shorter {min_chains*10} chains",
            start_timer=_start,
        )
        return None

    recent_chain_ids.extend(chosen_chain_indices)
    cg.set_recent_chain_ids(recent_chain_ids)
    # logger.debug(f"I={chosen_chain_indices[0]},j={chosen_chain_indices[1]}", start_timer=_start)
    logger.debug(
        f"chain i={chosen_chain_sizes[0]}({chosen_chain_sizes[2]}),chain j={chosen_chain_sizes[1]}({chosen_chain_sizes[3]})",
        start_timer=_start,
    )
    logger.debug(
        f"selected pair: {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
        start_timer=_start,
    )
    return result


def phase_fallback(
    candidate_images: list[NodeProxy],
    pair_set: set[tuple[str, str]],
) -> tuple[NodeProxy, NodeProxy] | None:
    """Return the first untested pair found by scanning candidates in comparison-count order."""
    _start: float = time.perf_counter()
    ordered: list[NodeProxy] = _get_fallback_anchor_candidates(candidate_images)
    result: Pair | None = None
    candidate_count: int = len(ordered)
    for idx in range(candidate_count):
        node_a: NodeProxy | None = _find_candidate_node(
            candidate_images, ordered[idx].filename
        )
        if node_a is None:
            logger.debug("anchor is not a candidate", start_timer=_start)
            continue
        later_nodes: list[NodeProxy] = ordered[idx + 1 :]
        compatible_nodes: list[NodeProxy] | None = _get_compatible_nodes(
            later_nodes, node_a
        )
        if compatible_nodes is None:
            continue
        pair_list: list[Pair] = _form_candidate_pairs(node_a, compatible_nodes)
        pair_list = _filter_existing_pairs(pair_list, pair_set)
        first_pair: Pair | None = _first_pair(pair_list)
        result = first_pair
        if result is not None:
            break
    if result is None:
        logger.debug("no pair found", start_timer=_start)
        return None
    logger.debug(
        f"selected pair: {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
        start_timer=_start,
    )
    return result


# =============================================================================
# CANDIDATE AND ANCHOR SELECTION
# =============================================================================


def _find_candidate_node(
    candidate_nodes: list[NodeProxy], filename: str
) -> NodeProxy | None:
    """Find a candidate proxy by filename."""
    node: NodeProxy | None = next(
        (node for node in candidate_nodes if node.filename == filename), None
    )
    return node


def _get_seed_coverage_ready_pool_length(
    seed_pool: list[NodeProxy], all_images_length: int
) -> int | None:
    """Count ready seed nodes or return None when the seed target is complete."""
    seed_percentage: int = int(config["ranking"]["seed_percentage"])
    seed_size: int = all_images_length * seed_percentage // 100
    seed_target: int = int(config["ranking"]["seed_target_comparisons"])
    ready_seed_pool_length: int = sum(
        node.link_count >= seed_target for node in seed_pool
    )
    if ready_seed_pool_length >= seed_size:
        return None
    return ready_seed_pool_length


def _get_seed_coverage_under_target_nodes(
    candidate_nodes: list[NodeProxy],
) -> list[NodeProxy]:
    """Return candidates below the seed comparison target, most-compared first."""
    seed_target: int = int(config["ranking"]["seed_target_comparisons"])
    under_seed_target: list[NodeProxy] = [
        node for node in candidate_nodes if node.link_count < seed_target
    ]
    under_seed_target.sort(key=lambda node: node.link_count, reverse=True)
    return under_seed_target


def _select_seed_coverage_anchor(
    under_seed_target: list[NodeProxy],
) -> NodeProxy | None:
    """Select the most-compared candidate that remains below the seed target."""
    return under_seed_target[0] if under_seed_target else None


def _select_anchor_insert_node(
    candidate_nodes: list[NodeProxy],
    score_type: str,
) -> NodeProxy | None:
    """Select the lowest-comparison candidate at or below the insertion target."""
    insertion_target: int = int(config["ranking"]["insertion_target_comparisons"])
    node_a: NodeProxy | None = min(
        (node for node in candidate_nodes if node.link_count <= insertion_target),
        key=lambda node: (node.link_count, node.__getattribute__(score_type)),
        default=None,
    )
    if node_a is None:
        return None
    anchor_node: NodeProxy | None = _find_candidate_node(
        candidate_nodes, node_a.filename
    )
    return anchor_node


def _collect_chain_extremes(
    chains: list[ChainProxy],
    candidate_names: set[str],
    check_list: list[str],
    use_bottom: bool,
    cg: CrystalGraphPort,
) -> list[NodeProxy]:
    """Return up to 10 qualifying chain extremes, least-compared first."""
    nodes: list[NodeProxy] = []
    seen: set[str] = set()
    errors: dict[str, int] = {
        "none": 0,
        "none_2": 0,
        "candidate_missing": 0,
        "checklist_missing": 0,
        "not_real_extreme": 0,
        "seen": 0,
    }
    for chain in chains:
        chain_extreme: NodeProxy | None = chain.last if use_bottom else chain.first
        if not chain_extreme:
            errors["none"] += 1
            continue
        filename: str = chain_extreme.filename
        if filename in seen:
            errors["seen"] += 1
            continue
        seen.add(filename)
        if not chain_extreme.is_bottom() if use_bottom else not chain_extreme.is_top():
            errors["not_real_extreme"] += 1
            continue
        if chain_extreme.filename not in candidate_names:
            errors["candidate_missing"] += 1
            continue
        if chain_extreme.filename not in check_list:
            errors["checklist_missing"] += 1
            # logger.debug(
            #     f"skipping {filename} because not in check_list, use_bottom={use_bottom}, check_list={len(check_list)}"
            # )
            continue

        node: NodeProxy | None = cg.get_node(filename)
        if node is None:
            errors["none_2"] += 1
            continue
        nodes.append(node)
    # logger.info(
    #     f"collected {len(nodes)} chain extremes, bottom={use_bottom}, check_list={len(check_list)}, errors={errors}",
    # )
    # logger.debug(f"check list: {check_list[:5]}... (len={len(check_list)})")
    nodes.sort(key=lambda node: node.link_count)
    lru_size = int(config["ranking"]["lru_size"])
    return nodes[:lru_size]


def _get_collapsible_candidates(
    candidate_nodes: list[NodeProxy], cg: CrystalGraphPort
) -> tuple[list[NodeProxy], bool, list[str]]:
    """Find eligible chain extremes, switching sides when too few bottoms qualify."""
    candidate_names: set[str] = {node.filename for node in candidate_nodes}
    chains: list[ChainProxy] = cg.get_all_chains()
    check_list: list[str] = [node.filename for node in cg.get_loser_only_nodes()]
    use_bottom: bool = True
    nodes: list[NodeProxy] = _collect_chain_extremes(
        chains, candidate_names, check_list, use_bottom, cg
    )
    if len(nodes) < 2:
        check_list = [node.filename for node in cg.get_winner_only_nodes()]
        use_bottom = False
        nodes = _collect_chain_extremes(
            chains, candidate_names, check_list, use_bottom, cg
        )
    return nodes, use_bottom, check_list


def _get_single_win_loss_candidate_lanes(
    candidate_nodes: list[NodeProxy],
) -> Iterator[tuple[bool, bool, list[NodeProxy]]]:
    """Yield candidate lanes for single-win and single-loss nodes."""
    insertion_target: int = int(config["ranking"]["insertion_target_comparisons"])
    for single_win, filtered_only in (
        (True, True),
        (False, True),
        (True, False),
        (False, False),
    ):
        nodes: list[NodeProxy] = []
        for node in candidate_nodes:
            if node.link_count <= insertion_target:
                continue
            links: list[NodeProxy] = (
                node.get_links(worse_than=True)
                if single_win
                else node.get_links(better_than=True)
            )
            if len(links) == 1:
                nodes.append(node)
        if len(nodes) >= 2:
            nodes.sort(key=lambda node: (node.link_count, node.mu_skill))
            yield single_win, filtered_only, nodes


def _prepare_single_win_loss_lane(
    candidate_nodes: list[NodeProxy],
    nodes: list[NodeProxy],
    single_win: bool,
    filtered_only: bool,
    minimum_count: int,
) -> tuple[NodeProxy | None, list[NodeProxy], int]:
    """Choose a lane anchor and apply its comparison-count eligibility rule."""
    node_a: NodeProxy | None = _find_candidate_node(candidate_nodes, nodes[0].filename)
    if node_a is None:
        return None, [], minimum_count

    if single_win:
        minimum_count = node_a.link_count
    partner_nodes: list[NodeProxy] = nodes[1:]
    if filtered_only and node_a.link_count >= minimum_count:
        filtered_nodes: list[NodeProxy] = [
            node for node in nodes if node.link_count <= node_a.link_count
        ]
        reserve_count: int = config["ranking"]["reserve_count"]
        if len(filtered_nodes) < reserve_count:
            return None, [], minimum_count
        partner_nodes = [
            node for node in filtered_nodes if node.filename != node_a.filename
        ]
    return node_a, partner_nodes, minimum_count


def _get_chain_merge_state(
    cg: CrystalGraphPort,
) -> tuple[list[list[NodeProxy]], list[int], int, int]:
    """Load merge chains and the current chain-pair selection settings."""
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
    return chains, recent_chain_ids, min_chains, min_comparisons


def _iter_chain_merge_chain_pairs(
    chains: list[list[NodeProxy]], recent_chain_ids: list[int], min_chains: int
) -> Iterator[tuple[int, int]]:
    """Yield eligible chain-index pairs, skipping recently selected chains."""
    chain_count: int = len(chains)
    top_n: int = min(min_chains * 10, chain_count)
    for i in range(top_n - 1):
        if i in recent_chain_ids:
            continue
        for j in range(len(chains) - 1, i, -1):
            if j not in recent_chain_ids:
                yield i, j


def _get_chain_merge_anchor_nodes(
    chain_nodes: list[NodeProxy],
    candidate_by_filename: dict[str, NodeProxy],
    min_comparisons: int,
) -> list[NodeProxy]:
    """Return candidate nodes on a chain that exceed the comparison minimum."""
    return [
        candidate_by_filename[node.filename]
        for node in chain_nodes
        if node.filename in candidate_by_filename
        and candidate_by_filename[node.filename].link_count > min_comparisons
    ]


def _get_chain_merge_opponent_nodes(
    chain_nodes: list[NodeProxy], candidate_by_filename: dict[str, NodeProxy]
) -> list[NodeProxy]:
    """Return candidate nodes belonging to the opponent chain."""
    return [
        candidate_by_filename[node.filename]
        for node in chain_nodes
        if node.filename in candidate_by_filename
    ]


def _select_chain_merge_midpoint(
    candidate_nodes: list[NodeProxy], chain_nodes: list[NodeProxy]
) -> NodeProxy | None:
    """Select the candidate at the middle position of a chain-node list."""
    if not chain_nodes:
        return None
    midpoint_name: str = chain_nodes[len(chain_nodes) // 2].filename
    node: NodeProxy | None = _find_candidate_node(candidate_nodes, midpoint_name)
    return node


def _select_uncertainty_refine_anchor(
    candidate_nodes: list[NodeProxy], seed_pool_set: set[str]
) -> NodeProxy | None:
    """Select the most uncertain eligible candidate outside the seed pool."""
    min_sigma_threshold: float = float(config["ranking"]["sigma_threshold"])
    insertion_target: int = int(config["ranking"]["insertion_target_comparisons"])
    target_nodes: list[NodeProxy] = [
        node
        for node in candidate_nodes
        if node.link_count > insertion_target
        and node.sigma_uncertainty >= min_sigma_threshold
    ]
    target_nodes.sort(key=lambda node: node.sigma_uncertainty, reverse=True)
    target_a: NodeProxy | None = next(
        (node for node in target_nodes if node.filename not in seed_pool_set), None
    )
    if target_a is None:
        return None
    node_a: NodeProxy | None = _find_candidate_node(candidate_nodes, target_a.filename)
    return node_a


def _get_chain_candidates(cg: CrystalGraphPort) -> tuple[list[ChainProxy], int]:
    """Collect chains below the configured length."""
    min_chain_length: int = int(config["ranking"]["chain_middle_min_chain_length"])
    chains: list[ChainProxy] = cg.get_all_chains(sort_order="asc")
    qualifying_chains: list[ChainProxy] = [
        chain for chain in chains if chain.main_length < min_chain_length
    ]
    if not qualifying_chains:
        return [], min_chain_length
    return qualifying_chains, min_chain_length


def _collect_chain_midpoints(
    chains: list[ChainProxy],
    candidate_nodes: list[NodeProxy],
    cg: CrystalGraphPort,
) -> list[NodeProxy]:
    """Return up to 'lru_size' distinct candidate proxies at the chain midpoints."""
    nodes: list[NodeProxy] = []
    seen: set[str] = set()
    candidates_by_name: dict[str, NodeProxy] = {
        node.filename: node for node in candidate_nodes
    }
    candidate_names: set[str] = set(candidates_by_name)

    for raw_chain in chains:
        midpoint: NodeProxy | None = raw_chain.main_node_at(raw_chain.main_length // 2)
        if midpoint is None:
            continue

        filename: str = midpoint.filename
        if filename in seen:
            continue
        if candidate_names and filename not in candidate_names:
            continue

        node: NodeProxy | None = (
            candidates_by_name.get(filename)
            if candidate_names
            else cg.get_node(filename)
        )
        if node is None:
            continue

        seen.add(filename)
        nodes.append(node)

    nodes.sort(key=lambda node: node.link_count)
    lru_size = int(config["ranking"]["lru_size"])
    return nodes[:lru_size]


def _get_fallback_anchor_candidates(
    candidate_nodes: list[NodeProxy],
) -> list[NodeProxy]:
    """Order fallback anchors from fewest comparisons to most."""
    ordered: list[NodeProxy] = sorted(candidate_nodes, key=lambda node: node.link_count)
    return ordered


# =============================================================================
# COMPATIBLE-NODE SELECTION
# =============================================================================


def _get_compatible_nodes(
    candidate_nodes: list[NodeProxy],
    node_a: NodeProxy,
) -> list[NodeProxy] | None:
    """Return compatible opponents, or None when the list is empty."""
    compatible_nodes: list[NodeProxy] = [
        node_b for node_b in candidate_nodes if node_b.filename != node_a.filename
    ]
    return compatible_nodes or None


def _get_seed_coverage_opponents(
    under_seed_target: list[NodeProxy],
    node_a: NodeProxy,
    ready_seed_pool_length: int,
    all_images_length: int,
) -> list[NodeProxy] | None:
    """Select under-target opponents within the seed-pool range and count limit."""
    seed_percentage: int = int(config["ranking"]["seed_percentage"])
    seed_size: int = all_images_length * seed_percentage // 100
    opponent_candidates: list[NodeProxy] = under_seed_target[
        1 : (seed_size - ready_seed_pool_length + 1)
    ]
    eligible_opponents: list[NodeProxy] = [
        node for node in opponent_candidates if node.link_count <= node_a.link_count + 2
    ]
    compatible_nodes: list[NodeProxy] | None = _get_compatible_nodes(
        eligible_opponents, node_a
    )
    return compatible_nodes


def _get_anchor_insert_opponents(
    candidate_nodes: list[NodeProxy],
    node_a: NodeProxy,
) -> list[NodeProxy] | None:
    """Select the most-compared <=seed_target_comparisons candidates other than the anchor. limited byt lru_size"""

    seed_target_comparisons: int = int(config["ranking"]["seed_target_comparisons"])
    seed_candidates: list[NodeProxy] = [
        node for node in candidate_nodes if node.link_count <= seed_target_comparisons
    ]
    seed_candidates.sort(key=lambda node: node.link_count, reverse=True)
    seed_candidates = seed_candidates[: int(config["ranking"]["lru_size"])]
    compatible_nodes: list[NodeProxy] | None = _get_compatible_nodes(
        seed_candidates, node_a
    )
    return compatible_nodes


def _get_ordered_compatible_nodes(
    candidate_nodes: list[NodeProxy],
    node_a: NodeProxy,
    nodes: list[NodeProxy],
    skip_first: bool,
) -> list[NodeProxy] | None:
    """Return candidate proxies from an ordered node list, excluding the anchor."""
    candidate_by_filename: dict[str, NodeProxy] = {
        node.filename: node for node in candidate_nodes
    }
    ordered_nodes: list[NodeProxy] = nodes[1:] if skip_first else nodes
    ordered_compatible_nodes: list[NodeProxy] = [
        candidate_by_filename[node.filename]
        for node in ordered_nodes
        if node.filename in candidate_by_filename
    ]
    compatible_nodes: list[NodeProxy] | None = _get_compatible_nodes(
        ordered_compatible_nodes, node_a
    )
    return compatible_nodes


def _get_branch_chain_compatible_nodes(
    candidate_nodes: list[NodeProxy], node_a: NodeProxy
) -> list[NodeProxy] | None:
    """Return candidate nodes below the anchor's immediate upper node on its other main chain."""

    candidate_by_filename: dict[str, NodeProxy] = {
        node.filename: node for node in candidate_nodes
    }
    anchor_chains: list[ChainProxy] = node_a.get_chain()
    if not anchor_chains:
        logger.debug(f"no main chain for anchor {node_a.filename}")
        return None

    anchor_chain: ChainProxy = anchor_chains[0]
    anchor_chain_nodes: list[NodeProxy] = anchor_chain.nodes
    anchor_position: int | None = next(
        (
            index
            for index, node in enumerate(anchor_chain_nodes)
            if node.filename == node_a.filename
        ),
        None,
    )
    if anchor_position is None:
        logger.debug(
            f"anchor {node_a.filename} is missing from main chain {anchor_chain.id}"
        )
        return None
    if anchor_position == 0:
        logger.debug(
            f"anchor {node_a.filename} has no immediate upper node in main chain {anchor_chain.id}"
        )
        return None

    upper_index: int = anchor_position - 1
    branch_chain: ChainProxy = anchor_chain
    upper_node: NodeProxy = anchor_chain_nodes[upper_index]

    for i in range(3):
        if upper_index - i <= 0:
            logger.debug(
                f"anchor {node_a.filename} has no immediate valid upper node in main chain {anchor_chain.id}"
            )
            return None
        upper_node = anchor_chain_nodes[upper_index - i]
        upper_chains: list[ChainProxy] = upper_node.get_chain()
        if not upper_chains:
            logger.debug(
                f"immediate upper node {upper_node.filename} has no main chain"
            )
            return None

        branch_chain = upper_chains[0]
        if branch_chain.id != anchor_chain.id:
            break
        if i >= 2:
            logger.debug(
                f"immediate upper node {upper_node.filename} belongs to anchor chain {anchor_chain.id}"
            )
            return None

    branch_nodes: list[NodeProxy] = branch_chain.nodes
    upper_position: int | None = next(
        (
            index
            for index, node in enumerate(branch_nodes)
            if node.filename == upper_node.filename
        ),
        None,
    )
    if upper_position is None:
        logger.debug(
            f"immediate upper node {upper_node.filename} is missing from branch chain {branch_chain.id}"
        )
        return None

    compatible_nodes: list[NodeProxy] = [
        candidate_by_filename[node.filename]
        for node in branch_nodes[upper_position + 1 :]
        if node.filename in candidate_by_filename and node.filename != node_a.filename
    ]
    if not compatible_nodes:
        logger.debug(
            f"no candidate nodes below {upper_node.filename} in branch chain {branch_chain.id}"
        )
        return None
    return compatible_nodes


def _get_uncertainty_refine_opponents(
    candidate_nodes: list[NodeProxy],
    node_a: NodeProxy,
    seed_pool_set: set[str],
) -> list[NodeProxy] | None:
    """Select the closest-rated seed-pool candidates within the LRU limit."""
    seed_pool: list[NodeProxy] = [
        node for node in candidate_nodes if node.filename in seed_pool_set
    ]
    seed_pool.sort(
        key=lambda node: (
            abs(node_a.trueskill_score - node.trueskill_score),
            node.link_count,
        )
    )
    seed_pool = seed_pool[: int(config["ranking"]["lru_size"])]
    compatible_nodes: list[NodeProxy] | None = _get_compatible_nodes(seed_pool, node_a)
    return compatible_nodes


# =============================================================================
# PAIR FORMATION
# =============================================================================


def _form_candidate_pairs(
    node_a: NodeProxy, compatible_nodes: list[NodeProxy]
) -> list[Pair]:
    """Pair one anchor with every compatible opponent."""
    return [(node_a, node_b) for node_b in compatible_nodes]


def _get_chain_merge_pair_candidates(
    candidate_nodes: list[NodeProxy],
    a_nodes: list[NodeProxy],
    b_nodes: list[NodeProxy],
    a_mid: NodeProxy,
    b_mid: NodeProxy,
) -> list[Pair]:
    """Build midpoint, aligned, and cross-product pairs for two chains."""
    pair_list: list[Pair] = _form_candidate_pairs(a_mid, [b_mid])
    chain_pairs: zip[tuple[NodeProxy, NodeProxy]] = zip(a_nodes, b_nodes)
    pair_list.extend(chain_pairs)
    for node_a in a_nodes:
        anchor_node: NodeProxy | None = _find_candidate_node(
            candidate_nodes, node_a.filename
        )
        if anchor_node is None:
            continue
        compatible_nodes: list[NodeProxy] | None = _get_compatible_nodes(
            b_nodes, anchor_node
        )
        if compatible_nodes is None:
            continue
        anchor_pairs: list[Pair] = _form_candidate_pairs(anchor_node, compatible_nodes)
        pair_list.extend(anchor_pairs)
    return pair_list


# =============================================================================
# PAIR FILTERING
# =============================================================================


def _filter_existing_pairs(
    pair_list: list[Pair], existing_pair_set: set[tuple[str, str]]
) -> list[Pair]:
    """Remove pairs already present in comparison history."""
    return [
        pair
        for pair in pair_list
        if canonicalize_pair(pair[0].filename, pair[1].filename)
        not in existing_pair_set
    ]


def _filter_chain_merge_pairs(
    pair_list: list[Pair], cg: CrystalGraphPort
) -> list[Pair]:
    """Order unique pairs by public-score gap and exclude pairs already in one path."""
    unique_pairs: dict[Pair, None] = dict.fromkeys(pair_list)
    ordered_pairs: list[Pair] = list(unique_pairs)
    ordered_pairs.sort(key=lambda pair: abs(pair[0].score - pair[1].score))
    return [
        pair
        for pair in ordered_pairs
        if not cg.are_in_same_path(pair[0].filename, pair[1].filename)
    ]


def _filter_uncertainty_refine_pairs(
    pair_list: list[Pair],
    pair_set: set[tuple[str, str]],
    cg: CrystalGraphPort,
) -> list[Pair] | None:
    """Remove previously compared and already-connected pairs."""
    filtered_pairs: list[Pair] = []
    pair_count: int = len(pair_list)
    with tqdm(total=pair_count, desc="Creating pair list", delay=3.0) as pbar:
        for pair in pair_list:
            if canonicalize_pair(pair[0].filename, pair[1].filename) in pair_set:
                continue
            if cg.are_in_same_path(pair[0].filename, pair[1].filename):
                continue
            filtered_pairs.append(pair)
            pbar.update(1)
    if not filtered_pairs:
        return None
    return filtered_pairs


def _filter_chain_middle_pairs(
    pair_list: list[Pair],
    node_a: NodeProxy,
    existing_pair_set: set[tuple[str, str]],
    cg: CrystalGraphPort,
) -> list[Pair] | None:
    """Keep new pairs from different main chains that are not already connected."""
    anchor_chain_id: int = node_a.get_chain()[0].id
    filtered_list: list[Pair] = [
        pair
        for pair in pair_list
        if canonicalize_pair(pair[0].filename, pair[1].filename)
        not in existing_pair_set
        and anchor_chain_id != pair[1].get_chain()[0].id
        and not cg.are_in_same_path(pair[0].filename, pair[1].filename)
    ]

    if not filtered_list:
        return None
    return filtered_list


# =============================================================================
# PAIR SELECTION
# =============================================================================


def _first_pair(pair_list: list[Pair]) -> Pair | None:
    """Return the first pair, or None when the list is empty."""
    return pair_list[0] if pair_list else None


def _closest_score_pair(
    pair_list: list[Pair],
    closest: bool = False,
    prefer_least_compared_opponent: bool = False,
) -> Pair | None:
    """Choose a score-gap pair within the anchor's sigma range."""

    if not pair_list:
        return None
    if prefer_least_compared_opponent:
        pair_list.sort(
            key=lambda pair: (
                pair[1].link_count,
                abs(pair[0].trueskill_score - pair[1].trueskill_score),
            )
        )
    else:
        pair_list.sort(
            key=lambda pair: abs(pair[0].trueskill_score - pair[1].trueskill_score)
        )
    best_pair: Pair = pair_list[0]
    best_difference: float = abs(
        best_pair[0].trueskill_score - best_pair[1].trueskill_score
    )
    sigma_range_multiplier: float = config["ranking"]["sigma_range_multiplier"]
    if best_difference > best_pair[0].sigma_uncertainty * sigma_range_multiplier:
        return None
    if closest:
        return best_pair

    for pair in pair_list:
        difference: float = abs(pair[0].trueskill_score - pair[1].trueskill_score)
        if difference > best_pair[0].sigma_uncertainty * sigma_range_multiplier:
            break
        if difference > best_difference:
            best_difference = difference
            best_pair = pair
    return best_pair
