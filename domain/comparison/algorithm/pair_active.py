"""Active pair selection for the TrueSkill-based step01 flow."""

from __future__ import annotations

import time
from tqdm import tqdm

from ....core.observability.logger import get_logger, ModuleLogger
from ...graph.chain_proxy import ChainProxy
from ...graph.node_proxy import NodeProxy

from ....core.configuration.settings import config

from ..constants import MIN_CHAIN_THRESHOLD

from ...comparison.algorithm.history_collapse import canonicalize_pair

from ....domain.ports.graph import CrystalGraphPort

logger: ModuleLogger = get_logger(__name__)

NodeTuple = tuple[NodeProxy, bool]


def phase_seed_coverage(
    candidate_nodes: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
    seed_pool: list[NodeProxy],
    all_images_length: int,
) -> tuple[NodeProxy, NodeProxy] | None:
    _start: float = time.perf_counter()
    seed_percentage = int(config["ranking"]["seed_percentage"])
    seed_target = int(config["ranking"]["seed_target_comparisons"])

    seed_size: int = all_images_length * seed_percentage // 100
    ready_seed_pool: list[NodeProxy] = [
        i for i in seed_pool if i.link_count >= seed_target
    ]
    ready_seed_pool_length: int = len(ready_seed_pool)

    # logger.debug(
    #     f"phase_seed_coverage: all_images={all_images_length}, seed_size={seed_size}, "
    #     f"seed_pool={len(seed_pool)}, ready={ready_seed_pool_length}, target={seed_target}, ",
    #     start_timer=_start,
    # )

    if ready_seed_pool_length >= seed_size:
        logger.info(
            f"skipping phase 0: seed pool size {ready_seed_pool_length} >= {seed_size} with >={seed_target} comparisons ({seed_percentage}% of {all_images_length})",
            start_timer=_start,
        )
        return None

    # logger.debug(
    #     f"phase 0 active: {ready_seed_pool_length}/{seed_size} seeds ready (target={seed_target}), "
    #     f"under_target={len([n for n in candidate_nodes if n.link_count < seed_target])}",
    #     start_timer=_start,
    # )

    under_seed_target: list[NodeProxy] = [
        node for node in candidate_nodes if node.link_count < seed_target
    ]
    under_seed_target.sort(key=lambda node: node.link_count, reverse=True)

    node_a: NodeProxy = under_seed_target[0]
    pair_list: list[tuple[NodeProxy, NodeProxy]] = [
        (node_a, node_b)
        for node_b in under_seed_target[1 : (seed_size - ready_seed_pool_length + 1)]
        if node_b.link_count <= node_a.link_count + 2
        and canonicalize_pair(node_a.filename, node_b.filename) not in existing_pair_set
    ]

    return _closest_score_pair(
        pair_list,
        closest=False,
    )
    # if result:
    #     logger.debug(
    #         f"phase_seed_coverage: returning pair {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
    #         start_timer=_start,
    #     )
    # else:
    #     logger.debug(
    #         f"phase_seed_coverage: no pair found, under_seed_target={len(under_seed_target)}, candidate_nodes={len(candidate_nodes)}",
    #         start_timer=_start,
    #     )
    # return result


def phase_anchor_insert(
    candidate_images: list[NodeProxy],
    seed_pool_set: set[str],
    existing_pair_set: set[tuple[str, str]],
) -> tuple[NodeProxy, NodeProxy] | None:
    _start: float = time.perf_counter()
    insertion_target = int(config["ranking"]["insertion_target_comparisons"])

    candidates: list[NodeProxy] = [
        node
        for node in candidate_images
        if node.link_count <= insertion_target
    ]

    # A single new image is a valid node_a: opponents come from the seed pool,
    # not from the other candidates, so only an empty lane means "no work".
    if not candidates:
        logger.warning(
            "pool too small (0 images at or below the insertion target)",
            start_timer=_start,
        )
        return None
    candidates.sort(key=lambda node: (node.link_count, node.score))
    node_a: NodeProxy = candidates[0]

    # Opponents are drawn from the seed pool so a newcomer is tested against
    # the reference set instead of against other newcomers. Sorting by lowest
    # link_count first spreads comparisons evenly across the pool; score
    # distance only breaks ties, so it cannot concentrate traffic.
    pool_nodes: list[NodeProxy] = [
        node
        for node in candidate_images
        if node.filename in seed_pool_set and node.filename != node_a.filename
    ]
    lru_size: int = config["ranking"]["lru_size"]

    pool_nodes.sort(key=lambda node: (node.link_count, abs(node_a.score - node.score)))
    pool_nodes = pool_nodes[:lru_size]
    # logger.debug(
    #     f"first pool node score: {pool_nodes[0].score} (difference: {abs(pool_nodes[0].score - node_a.score)}, link count: {pool_nodes[0].link_count}), "
    #     f"\nlast node: {pool_nodes[-1].score} (difference: {abs(pool_nodes[-1].score - node_a.score)}, link count: {pool_nodes[-1].link_count})"
    #     f"\n(node a score:{node_a.score})"
    #     f"\n(pool size: {len(pool_nodes)})"
    # )

    # remaining: list[NodeProxy] = [
    #     node for node in pool_nodes[1:] if node.filename != node_a.filename
    # ]
    # remaining.sort(key=lambda opp: abs(opp.mu_skill - node_a.mu_skill))

    # seen_opponents = 0
    # for opponent in pool_nodes:
    #     if canonicalize_pair(node_a.filename, opponent.filename) in existing_pair_set:
    #         continue
    #     seen_opponents += 1
    #     if cg.are_in_same_path(node_a.filename, opponent.filename):
    #         continue
    #     return node_a, opponent
    nodes: list[NodeProxy] = [
        node
        for node in pool_nodes
        if canonicalize_pair(node_a.filename, node.filename) not in existing_pair_set
        # and not cg.are_in_same_path(node_a.filename, node.filename)
    ]
    # One surviving opponent is enough: the pair is (node_a, opponent). Requiring
    # two discarded a valid comparison whenever the pool was small or most of
    # its members had already been played.
    if not nodes:
        logger.debug("no pair found, every pool opponent was already compared")
        return None
    # nodes = nodes[:100]

    pair_list: list[tuple[NodeProxy, NodeProxy]] = [
        (node_a, nodes[i]) for i in range(len(nodes))
    ]
    # result = _closest_score_pair(pair_list, closest=True)
    pair_list.sort(
        key=lambda pair: (pair[1].link_count, abs(pair[0].score - pair[1].score))
    )
    result: tuple[NodeProxy, NodeProxy] = pair_list[0]

    # result: tuple[NodeProxy, NodeProxy] | None = _closest_score_pair(
    #     pair_list, closest=True
    # )
    if result:
        logger.debug(
            f"returning pair {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
            start_timer=_start,
        )
        return result
    logger.debug(f"no pair found out of {len(pair_list)} opponents")
    return None


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
    errors = {
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
            logger.debug(
                f"skipping {filename} because not in check_list, use_bottom={use_bottom}, check_list={len(check_list)}"
            )
            continue

        node: NodeProxy | None = cg.get_node(filename)
        if node is None:
            errors["none_2"] += 1
            continue
        nodes.append(node)
    logger.info(
        f"collected {len(nodes)} chain extremes, bottom={use_bottom}, check_list={len(check_list)}, errors={errors}",
    )
    logger.debug(f"check list: {check_list[:5]}... (len={len(check_list)})")
    nodes.sort(key=lambda node: node.link_count)
    return nodes[:100]


def _closest_score_pair(
    pair_list: list[tuple[NodeProxy, NodeProxy]], closest: bool = False
) -> tuple[NodeProxy, NodeProxy] | None:
    if not pair_list:
        return None
    pair_list.sort(
        key=lambda pair: abs(pair[0].trueskill_score - pair[1].trueskill_score)
    )
    selected: tuple[NodeProxy, NodeProxy] = pair_list[0]
    if closest:
        return selected

    best_difference: float = abs(
        selected[0].trueskill_score - selected[1].trueskill_score
    )
    for pair in pair_list:
        difference: float = abs(pair[0].trueskill_score - pair[1].trueskill_score)

        if difference > selected[0].sigma_uncertainty:
            break
        if difference > best_difference:
            best_difference = difference
            selected = pair

    return selected


def phase_collapsible_pairs(
    candidate_nodes: list[NodeProxy],
    cg: CrystalGraphPort,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Anchor on the least-compared node and return its most score-similar same-type partner."""
    _start = time.perf_counter()

    # insertion_target = int(config["ranking"]["insertion_target_comparisons"])

    candidate_names: set[str] = {
        node.filename
        for node in candidate_nodes
        # if node.link_count > insertion_target
    }

    chains: list[ChainProxy] = list(cg.get_all_chains())

    check_list: list[str] = [node.filename for node in cg.get_loser_only_nodes()]
    use_bottom = True
    nodes: list[NodeProxy] = _collect_chain_extremes(
        chains, candidate_names, check_list, use_bottom, cg
    )

    if len(nodes) < 2:
        check_list = [node.filename for node in cg.get_winner_only_nodes()]
        use_bottom = False
        nodes = _collect_chain_extremes(
            chains, candidate_names, check_list, use_bottom, cg
        )

    if len(nodes) < 2:
        logger.info(
            f"no candidates found, len:{len(nodes)}, bottom:{use_bottom}, checklist:{len(check_list)}",
            start_timer=_start,
        )
        return None

    node_a: NodeProxy = nodes[0]
    pair_list: list[tuple[NodeProxy, NodeProxy]] = [
        (node_a, node_b) for node_b in nodes[1:]
    ]
    result: tuple[NodeProxy, NodeProxy] | None = _closest_score_pair(
        pair_list, closest=False
    )
    if not result:
        logger.info(
            f"no pair found, len:{len(nodes)}, bottom:{use_bottom}, checklist:{len(check_list)}",
            start_timer=_start,
        )
        return None
    logger.debug(
        f"collapsible pair: {result[0].filename}({result[0].link_count}) vs {result[1].filename}({result[1].link_count})",
        start_timer=_start,
    )
    return result


def phase_single_win_loss(
    candidate_nodes: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
) -> tuple[NodeProxy, NodeProxy] | None:
    _start: float = time.perf_counter()
    insertion_target = int(config["ranking"]["insertion_target_comparisons"])
    reserve_count: int = config["ranking"]["reserve_count"]
    minimum_count = 999
    for single_win, filtered_only in (
        (True, True),
        (False, True),
        (True, False),
        (False, False),
    ):

        # logger.info(f"single_win={single_win}, filtered_only={filtered_only}")

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

            # if len(nodes) > 100:
            #     break

        if len(nodes) < 2:
            # logger.info(
            #     f"skipping single win={single_win}, filtered_only={filtered_only}: only {len(nodes)} candidates"
            # )
            continue

        nodes.sort(
            key=lambda node: (node.link_count, node.mu_skill)
        )  # , reverse=reverse)
        node_a: NodeProxy = nodes[0]

        if single_win is True:
            minimum_count = node_a.link_count

        if filtered_only and node_a.link_count >= minimum_count:
            filtered_nodes: list[NodeProxy] = [
                node for node in nodes if node.link_count <= node_a.link_count
            ]
            if len(filtered_nodes) < reserve_count:
                # logger.info(
                #     f"skipping single win={single_win}, filtered_only={filtered_only}: only {len(filtered_nodes)} candidates with comparison_count={node_a.link_count}"
                # )

                continue
            nodes = filtered_nodes

        pair_list: list[tuple[NodeProxy, NodeProxy]] = [
            (node_a, nodes[i + 1])
            for i in range(len(nodes) - 1)
            if canonicalize_pair(node_a.filename, nodes[i + 1].filename)
            not in existing_pair_set
        ]
        result: tuple[NodeProxy, NodeProxy] | None = _closest_score_pair(
            pair_list, closest=False
        )
        if result:
            # logger.debug(
            #     f"single win/loss pair: {result}, single_win: {single_win}",
            #     start_timer=_start,
            # )
            return result
    logger.debug("no pair found", start_timer=_start)
    return None


def phase_chain_merge(
    candidate_images: list[NodeProxy],
    cg: CrystalGraphPort,
) -> tuple[NodeProxy, NodeProxy] | None:
    min_comparisons = int(config["ranking"]["insertion_target_comparisons"])

    last_chains_index: list[int] = cg.get_recent_chain_ids()
    if len(last_chains_index) > MIN_CHAIN_THRESHOLD:
        last_chains_index = last_chains_index[MIN_CHAIN_THRESHOLD // 2 :]
        cg.set_recent_chain_ids(last_chains_index)

    _start = time.perf_counter()
    candidate_names = {node.filename for node in candidate_images}

    chains: list[list[NodeProxy]] = [
        list(chain_proxy.nodes)
        for chain_proxy in cg.get_all_chains(min_length=1, sort_order="asc")
    ]

    if len(chains) < MIN_CHAIN_THRESHOLD:
        logger.info(
            f"skipping phase 4: <{MIN_CHAIN_THRESHOLD} chains", start_timer=_start
        )
        return None

    logger.debug(f"shortest chain: {len(chains[0])}, longest: {len(chains[-1])}")
    top_n: int = min(MIN_CHAIN_THRESHOLD * 10, len(chains))

    for i in range(top_n - 1):
        if i in last_chains_index:
            continue
        a_nodes: list[NodeProxy] = [
            n
            for n in chains[i]
            if n.filename in candidate_names and n.link_count > min_comparisons
        ]
        if len(a_nodes) == 0:
            continue
        a_mid: NodeProxy = a_nodes[len(a_nodes) // 2]

        for j in range(len(chains) - 1, i, -1):
            if j in last_chains_index:
                continue
            b_nodes: list[NodeProxy] = [
                n for n in chains[j] if n.filename in candidate_names
            ]

            if len(b_nodes) == 0:
                continue

            b_mid: NodeProxy = b_nodes[len(b_nodes) // 2]
            pair_list: list[tuple[NodeProxy, NodeProxy]] = [
                (a_mid, b_mid),
                *zip(a_nodes, b_nodes),
                *(
                    (node_a, node_b)
                    for node_a in a_nodes
                    for node_b in b_nodes
                    if node_a.filename != node_b.filename
                ),
            ]

            # Sorted so the closest-scoring pairs are offered first. The dedupe
            # has to preserve that order: a set() built here discards it, because
            # iteration order of a set is hash order rather than insertion order.
            # dict.fromkeys removes the duplicate pairs and keeps the ranking.
            deduped_pairs = list(dict.fromkeys(pair_list))
            deduped_pairs.sort(key=lambda pair: abs(pair[0].score - pair[1].score))

            for node_a, node_b in deduped_pairs:
                # if abs(node_a.score - node_b.score) > score_threshold:
                #     continue

                if cg.are_in_same_path(node_a.filename, node_b.filename):
                    continue

                last_chains_index.append(i)
                last_chains_index.append(j)
                cg.set_recent_chain_ids(last_chains_index)
                logger.debug(f"I={i},j={j}", start_timer=_start)
                logger.debug(
                    f"chain i={len(a_nodes)}({len(chains[i])}),chain j={len(b_nodes)}({len(chains[j])})",
                    start_timer=_start,
                )

                return node_a, node_b
    logger.warning(
        f"skipping phase 4: no valid pair found in shorter {MIN_CHAIN_THRESHOLD*10} chains",
        start_timer=_start,
    )

    return None


def phase_uncertainty_refine(
    candidate_images: list[NodeProxy],
    seed_pool_set: set[str],
    pair_set: set[tuple[str, str]],
    cg: CrystalGraphPort,
) -> tuple[NodeProxy, NodeProxy] | None:
    _start: float = time.perf_counter()

    min_sigma_threshold = float(config["ranking"]["sigma_threshold"])
    lru_size: int = config["ranking"]["lru_size"]
    insertion_target = int(config["ranking"]["insertion_target_comparisons"])

    # Who needs refining: past the insertion target, still above the sigma
    # threshold, and not already part of the reference pool.
    candidate_nodes: list[NodeProxy] = [
        node
        for node in candidate_images
        if node.link_count > insertion_target
        and node.sigma_uncertainty >= min_sigma_threshold
    ]
    candidate_nodes.sort(key=lambda node: node.sigma_uncertainty, reverse=True)

    node_a: NodeProxy | None = next(
        (node for node in candidate_nodes if node.filename not in seed_pool_set),
        None,
    )

    # Opponents come from every seed pool member. Applying the sigma threshold
    # to them as well left only 3% of the pool usable and piled all refinement
    # traffic onto those few images.
    seed_pool: list[NodeProxy] = []
    if node_a is not None:
        seed_pool = [
            node
            for node in candidate_images
            if node.filename in seed_pool_set
        ]
        # Least-compared first spreads traffic over the whole pool, with the
        # score gap only breaking ties. Trimming afterwards keeps the per
        # selection graph work bounded.
        seed_pool.sort(
            key=lambda node: (
                node.link_count,
                abs(node_a.trueskill_score - node.trueskill_score),
            )
        )
        seed_pool = seed_pool[:lru_size]

    if not node_a or not seed_pool:
        logger.debug(
            f"uncertainty refine: no node_a or seed_pool, node_a={node_a}, seed_pool={len(seed_pool)}",
            start_timer=_start,
        )
        return None

    pair_list: list[tuple[NodeProxy, NodeProxy]] = []
    with tqdm(total=len(seed_pool), desc="Creating pair list", delay=3.0) as pbar:
        for node_b in seed_pool:
            canonical_pair: tuple[str, str] = canonicalize_pair(
                node_a.filename, node_b.filename
            )
            if canonical_pair in pair_set:
                continue

            if cg.are_in_same_path(node_a.filename, node_b.filename):
                continue
            pair_list.append((node_a, node_b))
            pbar.update(1)

    # seed_pool is already least-compared-first, so the head of the list is the
    # right opponent. Re-sorting by score gap here would concentrate traffic on
    # whichever pool members happen to sit far from node_a.
    result: tuple[NodeProxy, NodeProxy] | None = pair_list[0] if pair_list else None

    if result:
        logger.debug(
            f"Uncertainty refine selected pair:"
            f" (mu difference:{abs(result[0].mu_skill - result[1].mu_skill)},"
            f" sigma:{result[0].sigma_uncertainty},{result[1].sigma_uncertainty})",
            start_timer=_start,
        )
        return result

    logger.debug("Uncertainty refine no pair found", start_timer=_start)
    return None


def phase_fallback(
    candidate_images: list[NodeProxy],
    pair_set: set[tuple[str, str]],
) -> tuple[NodeProxy, NodeProxy] | None:
    _start: float = time.perf_counter()
    ordered: list[NodeProxy] = sorted(
        candidate_images, key=lambda node: node.link_count
    )
    for idx, left in enumerate(ordered):
        for right in ordered[idx + 1 :]:
            if canonicalize_pair(left.filename, right.filename) in pair_set:
                continue

            return left, right
    logger.debug("fallback: no pair found", start_timer=_start)
    return None
