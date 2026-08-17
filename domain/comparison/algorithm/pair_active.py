"""Active pair selection for the TrueSkill-based step01 flow."""

from __future__ import annotations

import time
from typing import Any, Protocol

from ....core.observability.logger import get_logger, ModuleLogger
from ...graph.chain_proxy import ChainProxy

from ...graph.node_proxy import NodeProxy

from ....core.configuration.settings import config

from ...database.ports import ComparisonRepository

from ..constants import MIN_CHAIN_THRESHOLD

from .graph_helpers import pair_key, stable_seed_pool

logger: ModuleLogger = get_logger(__name__)

NodeTuple = tuple[NodeProxy, bool]


class CrystalGraph(Protocol):
    def get_node(self, node_id: str | None = None) -> Any: ...
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

    _chain: Any


def phase_seed_coverage(
    seed_candidates: list[NodeProxy],
    existing_pair_set: set[tuple[str, str]],
) -> tuple[NodeProxy, NodeProxy] | None:
    _start = time.perf_counter()
    seed_target = int(config["ranking"]["seed_target_comparisons"])
    under_seed_target = sorted(
        (node for node in seed_candidates if node.comparison_count < seed_target),
        key=lambda node: (node.comparison_count, -node.sigma_uncertainty),
    )

    for source in under_seed_target:
        unseen = sorted(
            (
                opp
                for opp in under_seed_target
                if opp.filename != source.filename
                and pair_key(source.filename, opp.filename) not in existing_pair_set
            ),
            key=lambda opp: (opp.comparison_count, abs(opp.score - source.score)),
        )
        if unseen:
            return source, unseen[0]
    logger.debug(
        f"not pairs found for seed coverage, under_seed_target/ready: {len(under_seed_target)}/{len(seed_candidates)}"
    )
    return None


def phase_anchor_insert(
    candidate_images: list[NodeProxy],
    seed_pool: set[str],
    existing_pair_set: set[tuple[str, str]],
    cg: CrystalGraph,
) -> tuple[NodeProxy, NodeProxy] | None:
    _start: float = time.perf_counter()
    insertion_target = int(config["ranking"]["insertion_target_comparisons"])
    reserve_count: int = config["ranking"]["reserve_count"]

    candidates = [node for node in candidate_images if node.filename not in seed_pool]
    pool_nodes: list[NodeProxy] = []
    for threshold in range(insertion_target + 1):
        pool_nodes = [node for node in candidates if node.comparison_count <= threshold]
        if len(pool_nodes) >= max(threshold + 2, reserve_count):
            break

    if len(pool_nodes) < reserve_count:
        logger.warning(
            f"pool too small ({len(pool_nodes)} < {reserve_count})",
            start_timer=_start,
        )
        return None
    pool_nodes.sort(key=lambda node: (node.comparison_count, node.score))
    source_node: NodeProxy = pool_nodes[0]

    remaining: list[NodeProxy] = [
        node for node in pool_nodes[1:] if node.filename != source_node.filename
    ]
    remaining.sort(key=lambda opp: abs(opp.mu_skill - source_node.mu_skill))

    seen_opponents = 0
    for opponent in remaining:
        if pair_key(source_node.filename, opponent.filename) in existing_pair_set:
            continue
        seen_opponents += 1
        if cg.are_in_same_path(source_node.filename, opponent.filename):
            continue
        return source_node, opponent
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
    pair_list.sort(key=lambda pair: abs(pair[0].mu_skill - pair[1].mu_skill))
    return pair_list[0]


def phase_collapsible_pairs(
    candidate_images: list[NodeProxy],
    cg: CrystalGraph,
    comparison_repo: ComparisonRepository,
) -> tuple[NodeProxy, NodeProxy] | None:
    """Anchor on the least-compared node and return its most score-similar same-type partner."""
    _start = time.perf_counter()

    insertion_target = int(config["ranking"]["insertion_target_comparisons"])

    candidate_names = {
        node.filename
        for node in candidate_images
        if node.comparison_count > insertion_target
    }

    chains_list = cg.get_all_chains()
    chains: list[ChainProxy] = [c[0] for c in chains_list]

    check_list = comparison_repo.get_images_with_only_losses()
    use_bottom = True
    nodes: list[NodeProxy] = _collect_chain_extremes(
        chains, candidate_names, check_list, use_bottom, cg
    )

    if len(nodes) < 2:
        check_list = comparison_repo.get_images_with_only_wins()
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
    cg: CrystalGraph,
) -> tuple[NodeProxy, NodeProxy] | None:
    _start: float = time.perf_counter()
    insertion_target = int(config["ranking"]["insertion_target_comparisons"])

    for single_win, reverse in ((True, True), (False, False)):

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

            if len(nodes) > 10:
                break

        if len(nodes) < 2:
            continue

        nodes.sort(key=lambda node: node.comparison_count)  # , reverse=reverse)
        pair_list: list[tuple[NodeProxy, NodeProxy]] = [
            (nodes[i], nodes[i + 1]) for i in range(len(nodes) - 1)
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


_last_chains_index: list[int] = []


def phase_chain_merge(
    candidate_images: list[NodeProxy],
    cg: CrystalGraph,
) -> tuple[NodeProxy, NodeProxy] | None:
    global _last_chains_index
    score_threshold = 0.01
    min_comparisons = int(config["ranking"]["insertion_target_comparisons"])

    if len(_last_chains_index) > MIN_CHAIN_THRESHOLD:
        _last_chains_index = _last_chains_index[MIN_CHAIN_THRESHOLD // 2 :]

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
        if i in _last_chains_index:
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
            if j in _last_chains_index:
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

                _last_chains_index.append(i)
                _last_chains_index.append(j)
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
