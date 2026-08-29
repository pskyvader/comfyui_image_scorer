"""Active pair selection for the TrueSkill-based step01 flow."""

from __future__ import annotations

import time
from typing import Any, Protocol

from ....core.observability.logger import get_logger, ModuleLogger
from ...graph.chain_proxy import ChainProxy

from ...graph.node_proxy import NodeProxy

from ....core.configuration.settings import config

from ..constants import MIN_CHAIN_THRESHOLD

from .graph_helpers import pair_key, stable_seed_pool

logger: ModuleLogger = get_logger(__name__)

NodeTuple = tuple[NodeProxy, bool]


class CrystalGraph(Protocol):
    def get_node(self, node_id: str | None) -> Any: ...
    def get_all_nodes(
        self, only_top: bool = False, only_bottom: bool = False
    ) -> list[Any]: ...
    def get_component(
        self,
        node_id: str | None = None,
        component_id: int | None = None,
        chain_id: int | None = None,
    ) -> Any: ...
    def get_all_chains(
        self, min_length: int = 0, sort_order: str = "desc"
    ) -> list[tuple[Any, list[Any]]]: ...
    def get_graph_stats(self) -> dict[str, Any]: ...
    def are_in_same_path(self, img1: str, img2: str) -> bool: ...
    def get_all_links(self) -> set[tuple[str, str]]: ...
    def get_images_with_only_wins(self) -> list[str]: ...
    def get_images_with_only_losses(self) -> list[str]: ...
    def get_recent_chain_ids(self) -> list[int]: ...
    def set_recent_chain_ids(self, chain_ids: list[int]) -> None: ...

    _chain: Any


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
        i for i in seed_pool if i.comparison_count >= seed_target
    ]
    ready_seed_pool_length: int = len(ready_seed_pool)

    logger.debug(
        f"phase_seed_coverage: all_images={all_images_length}, seed_size={seed_size}, "
        f"seed_pool={len(seed_pool)}, ready={ready_seed_pool_length}, target={seed_target}, ",
        start_timer=_start,
    )

    if ready_seed_pool_length >= seed_size:
        logger.info(
            f"skipping phase 0: seed pool size {ready_seed_pool_length} >= {seed_size} ({seed_percentage}% of {all_images_length})",
            start_timer=_start,
        )
        return None

    logger.info(
        f"phase 0 active: {ready_seed_pool_length}/{seed_size} seeds ready (target={seed_target}), "
        f"under_target={len([n for n in candidate_nodes if n.comparison_count < seed_target])}",
        start_timer=_start,
    )

    under_seed_target: list[NodeProxy] = [
        node for node in candidate_nodes if node.comparison_count < seed_target
    ]
    under_seed_target.sort(key=lambda node: node.comparison_count, reverse=True)

    node_a: NodeProxy = under_seed_target[0]
    return _closest_score_pair(
        [
            (node_a, node_b)
            for node_b in under_seed_target[
                1 : (seed_size - ready_seed_pool_length + 1)
            ]
            if node_b.comparison_count <= node_a.comparison_count + 2
            and pair_key(node_a.filename, node_b.filename) not in existing_pair_set
        ]
    )
    # if result:
    #     logger.debug(
    #         f"phase_seed_coverage: returning pair {result[0].filename}({result[0].comparison_count}) vs {result[1].filename}({result[1].comparison_count})",
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
    cg: CrystalGraph,
) -> tuple[NodeProxy, NodeProxy] | None:
    _start: float = time.perf_counter()
    insertion_target = int(config["ranking"]["insertion_target_comparisons"])
    reserve_count: int = config["ranking"]["reserve_count"]

    candidates: list[NodeProxy] = [
        node
        for node in candidate_images
        if node.filename not in seed_pool_set
        and node.comparison_count < insertion_target
    ]

    if len(candidates) < reserve_count:
        logger.warning(
            f"pool too small ({len(candidates)} < {reserve_count})",
            start_timer=_start,
        )
        return None
    candidates.sort(key=lambda node: (node.comparison_count, node.trueskill_score))
    node_a: NodeProxy = candidates[0]

    pool_nodes: list[NodeProxy] = [
        node for node in candidate_images if node.filename in seed_pool_set
    ]

    # for threshold in range(insertion_target + 1):
    #     pool_nodes = [node for node in candidates if node.comparison_count <= threshold]
    #     if len(pool_nodes) >= max(threshold + 2, reserve_count):
    #         break

    pool_nodes.sort(key=lambda node: node.comparison_count)

    # remaining: list[NodeProxy] = [
    #     node for node in pool_nodes[1:] if node.filename != node_a.filename
    # ]
    # remaining.sort(key=lambda opp: abs(opp.mu_skill - node_a.mu_skill))

    seen_opponents = 0
    # for opponent in pool_nodes:
    #     if pair_key(node_a.filename, opponent.filename) in existing_pair_set:
    #         continue
    #     seen_opponents += 1
    #     if cg.are_in_same_path(node_a.filename, opponent.filename):
    #         continue
    #     return node_a, opponent
    nodes: list[NodeProxy] = [
        node
        for node in pool_nodes
        if pair_key(node_a.filename, node.filename) not in existing_pair_set
        and cg.are_in_same_path(node_a.filename, node.filename)
    ]

    pair_list: list[tuple[NodeProxy, NodeProxy]] = [
        (node_a, nodes[i + 1]) for i in range(len(nodes) - 1)
    ]
    result: tuple[NodeProxy, NodeProxy] | None = _closest_score_pair(pair_list)
    if result:
        return result
    logger.debug(f"no pair found out of {seen_opponents} opponents")
    return None


def _collect_chain_extremes(
    chains: list[ChainProxy],
    candidate_names: set[str],
    check_list: list[str],
    use_bottom: bool,
    cg: CrystalGraph,
) -> list[NodeProxy]:
    """Return up to 10 qualifying chain extremes, least-compared first."""
    nodes: list[NodeProxy] = []
    seen: set[str] = set()
    for chain in chains:
        chain_extreme = chain.last if use_bottom else chain.first
        if not (
            chain_extreme
            and chain_extreme.filename in candidate_names
            and chain_extreme.filename in check_list
            and (chain_extreme.is_bottom() if use_bottom else chain_extreme.is_top())
        ):
            continue
        filename = chain_extreme.filename
        if filename in seen:
            continue
        seen.add(filename)
        node = cg.get_node(filename)
        if node is None:
            continue
        nodes.append(node)
    nodes.sort(key=lambda node: node.comparison_count)
    return nodes[:10]


def _closest_score_pair(
    pair_list: list[tuple[NodeProxy, NodeProxy]],
) -> tuple[NodeProxy, NodeProxy] | None:
    if not pair_list:
        return None
    pair_list.sort(
        key=lambda pair: abs(pair[0].trueskill_score - pair[1].trueskill_score)
    )
    selected: tuple[NodeProxy, NodeProxy] = pair_list[0]
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
    cg: CrystalGraph,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Anchor on the least-compared node and return its most score-similar same-type partner."""
    _start = time.perf_counter()

    # insertion_target = int(config["ranking"]["insertion_target_comparisons"])

    candidate_names = {
        node.filename
        for node in candidate_nodes
        # if node.comparison_count > insertion_target
    }

    chains_list = cg.get_all_chains()
    chains: list[ChainProxy] = [c[0] for c in chains_list]

    check_list = cg.get_images_with_only_losses()
    use_bottom = True
    nodes: list[NodeProxy] = _collect_chain_extremes(
        chains, candidate_names, check_list, use_bottom, cg
    )

    if len(nodes) < 2:
        check_list = cg.get_images_with_only_wins()
        use_bottom = False
        nodes = _collect_chain_extremes(
            chains, candidate_names, check_list, use_bottom, cg
        )

    if len(nodes) < 2:
        logger.info(
            f"no candidates found, len:{len(nodes)}, bottom:{use_bottom}, checklist:{len(check_list)}"
        )
        return None

    node_a: NodeProxy = nodes[0]
    return _closest_score_pair([(node_a, node_b) for node_b in nodes[1:]])


def phase_single_win_loss(
    candidate_nodes: list[NodeProxy],
    _cg: CrystalGraph,
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

        logger.info(f"single_win={single_win}, filtered_only={filtered_only}")

        nodes: list[NodeProxy] = []
        for node in candidate_nodes:
            if node.comparison_count <= insertion_target:
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
            key=lambda node: (node.comparison_count, node.mu_skill)
        )  # , reverse=reverse)
        node_a: NodeProxy = nodes[0]

        if single_win is True:
            minimum_count = node_a.comparison_count

        if filtered_only and node_a.comparison_count >= minimum_count:
            filtered_nodes: list[NodeProxy] = [
                node
                for node in nodes
                if node.comparison_count <= node_a.comparison_count
            ]
            if len(filtered_nodes) < reserve_count:
                # logger.info(
                #     f"skipping single win={single_win}, filtered_only={filtered_only}: only {len(filtered_nodes)} candidates with comparison_count={node_a.comparison_count}"
                # )

                continue
            nodes = filtered_nodes

        pair_list: list[tuple[NodeProxy, NodeProxy]] = [
            (node_a, nodes[i + 1]) for i in range(len(nodes) - 1)
        ]
        result: tuple[NodeProxy, NodeProxy] | None = _closest_score_pair(pair_list)
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
    cg: CrystalGraph,
) -> tuple[NodeProxy, NodeProxy] | None:
    score_threshold = 0.01
    min_comparisons = int(config["ranking"]["insertion_target_comparisons"])

    last_chains_index: list[int] = cg.get_recent_chain_ids()
    if len(last_chains_index) > MIN_CHAIN_THRESHOLD:
        last_chains_index = last_chains_index[MIN_CHAIN_THRESHOLD // 2 :]
        cg.set_recent_chain_ids(last_chains_index)

    _start = time.perf_counter()
    candidate_names = {node.filename for node in candidate_images}

    chains_list: list[tuple[ChainProxy, list[NodeTuple]]] = cg.get_all_chains(
        min_length=1, sort_order="asc"
    )
    chains: list[list[NodeTuple]] = [c[1] for c in chains_list]

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
            n[0]
            for n in chains[i]
            if n[0].filename in candidate_names
            and n[1]
            and n[0].comparison_count > min_comparisons
        ]
        if len(a_nodes) == 0:
            continue
        a_mid: NodeProxy = a_nodes[len(a_nodes) // 2]

        for j in range(len(chains) - 1, i, -1):
            if j in last_chains_index:
                continue
            b_nodes: list[NodeProxy] = [
                n[0] for n in chains[j] if n[0].filename in candidate_names and n[1]
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
            for node_a, node_b in set(pair_list):
                if abs(node_a.score - node_b.score) > score_threshold:
                    continue

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
    pair_set: set[tuple[str, str]],
    cg: CrystalGraph,
) -> tuple[NodeProxy, NodeProxy] | None:
    _start = time.perf_counter()

    min_sigma_threshold = float(config["ranking"]["sigma_threshold"])

    seed_filenames = stable_seed_pool(candidate_images)
    seed_pool: list[NodeProxy] = []
    node_a: NodeProxy | None = None
    insertion_target = int(config["ranking"]["insertion_target_comparisons"])

    candidate_nodes = sorted(
        (node for node in candidate_images if node.comparison_count > insertion_target),
        key=lambda node: -node.sigma_uncertainty,
    )

    for node in candidate_nodes:
        if node.filename in seed_filenames:
            seed_pool.append(node)
        elif node.sigma_uncertainty >= min_sigma_threshold:
            if not node_a:
                node_a = node

    logger.debug(
        f"seed pool: {len(seed_pool)}/{len(candidate_images)}",
        start_timer=_start,
    )

    if not node_a or not seed_pool:
        return None

    best_pair: tuple[NodeProxy, NodeProxy] | None = None
    closest_ranking_mu: float = 100

    pair_list = sorted(
        ((node_a, node_b) for node_b in seed_pool),
        key=lambda pair: abs(pair[0].mu_skill - pair[1].mu_skill),
    )

    for node_a, node_b in pair_list:
        if pair_key(node_a.filename, node_b.filename) in pair_set:
            continue
        if cg.are_in_same_path(node_a.filename, node_b.filename):
            continue
        closest_ranking_mu = abs(node_a.mu_skill - node_b.mu_skill)
        best_pair = (node_a, node_b)
        break

    if best_pair:
        logger.debug(
            f"Uncertainty refine selected pair: {best_pair} (mu difference:{closest_ranking_mu})",
            start_timer=_start,
        )
        return best_pair

    logger.debug("Uncertainty refine no pair found", start_timer=_start)
    return None


def phase_fallback(
    candidate_images: list[NodeProxy],
    pair_set: set[tuple[str, str]],
) -> tuple[NodeProxy, NodeProxy] | None:
    _start = time.perf_counter()
    ordered = sorted(candidate_images, key=lambda node: node.comparison_count)
    for idx, left in enumerate(ordered):
        for right in ordered[idx + 1 :]:
            if pair_key(left.filename, right.filename) in pair_set:
                continue

            return left, right
    logger.debug("fallback: no pair found", start_timer=_start)
    return None
