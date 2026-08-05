"""Active pair selection for the TrueSkill-based step01 flow."""

from __future__ import annotations

import time
from typing import Any, Protocol
from collections.abc import Iterator

from ....core.observability.logger import get_logger, ModuleLogger
from ...graph.chain_proxy import ChainProxy

from ...graph.node_proxy import NodeProxy

from ....core.configuration.settings import config

from ..constants import MIN_CHAIN_THRESHOLD

logger: ModuleLogger = get_logger(__name__)

NodeTuple = tuple[NodeProxy, bool]


class ComparisonRepository(Protocol):
    def get_all_comparisons(
        self, weight: float | None = None
    ) -> list[dict[str, Any]]: ...
    def get_images_with_only_wins(self) -> list[str]: ...
    def get_images_with_only_losses(self) -> list[str]: ...


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

    _chain: Any


def stable_seed_pool(
    images: list[dict[str, Any]],
) -> list[str]:
    seed_percentage = int(config["ranking"]["seed_percentage"])
    seed_size = max(1, len(images) * seed_percentage // 100)
    by_comps = sorted(
        images, key=lambda img: int(img["comparison_count"]), reverse=True
    )
    result = [img["filename"] for img in by_comps[:seed_size]]

    return result


def _pair_key(filename_a: str, filename_b: str) -> tuple[str, str]:
    _start = time.perf_counter()
    result: tuple[str, str] = (
        (filename_a, filename_b)
        if filename_a <= filename_b
        else (filename_b, filename_a)
    )
    return result


def existing_pairs(comparison_repo: ComparisonRepository) -> set[tuple[str, str]]:
    result = {
        _pair_key(comp["filename_a"], comp["filename_b"])
        for comp in comparison_repo.get_all_comparisons(weight=1.0)
    }
    return result


def _score_gap(image_a: dict[str, Any], image_b: dict[str, Any]) -> float:
    _start = time.perf_counter()
    result = abs(float(image_a["score"]) - float(image_b["score"]))

    return result


def _find_unseen_candidates(
    source: dict[str, Any],
    candidates: list[dict[str, Any]],
    pair_set: set[tuple[str, str]],
) -> Iterator[dict[str, Any]]:

    _start = time.perf_counter()
    source_name = source["filename"]
    results = 0
    for candidate in candidates:
        if (
            _pair_key(source_name, candidate["filename"]) not in pair_set
            and candidate["filename"] != source_name
        ):
            results += 1
            yield candidate

    logger.debug(f"find unseen candidates length:{results}", start_timer=_start)


def _are_in_different_paths(filename_a: str, filename_b: str, cg: CrystalGraph) -> bool:
    _start = time.perf_counter()
    result = not cg.are_in_same_path(filename_a, filename_b)
    return result


def _build_low_count_pool(
    candidate_images: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    insertion_target = int(config["ranking"]["insertion_target_comparisons"])
    reserve_count = int(config["ranking"]["reserve_count"])

    for threshold in range(0, insertion_target + 1):
        pool = [
            img for img in candidate_images if int(img["comparison_count"]) <= threshold
        ]
        if len(pool) >= max(threshold + 2, reserve_count):
            return pool
    result = [
        img
        for img in candidate_images
        if int(img["comparison_count"]) <= insertion_target
    ]
    return result


def phase_seed_coverage(
    seed_candidates: list[dict[str, Any]],
    existing_pair_set: set[tuple[str, str]],
    cg: CrystalGraph,
    comparison_repo: ComparisonRepository,
) -> tuple[str, str] | None:
    _start = time.perf_counter()
    seed_target = int(config["ranking"]["seed_target_comparisons"])
    seed_nodes: list[dict[str, Any]] = [
        img for img in seed_candidates if int(img["comparison_count"]) < seed_target
    ]

    under_seed_target = sorted(
        seed_nodes,
        key=lambda img: (
            int(img["comparison_count"]),
            -float(img["rating_sigma"]),
        ),
    )

    for source in under_seed_target:
        if cg.get_node(source["filename"]) is None:
            continue
        logger.debug(f"starting iterator", start_timer=_start)
        opponents: Iterator[dict[str, Any]] = _find_unseen_candidates(
            source, under_seed_target, existing_pair_set
        )

        chosen = None
        i = 0
        for opp in opponents:
            if cg.get_node(opp["filename"]) is None:
                continue
            i += 1
            if chosen is None:
                chosen = opp

            if (
                i > 5
                and _score_gap(source, chosen) < 0.05
                and int(source["comparison_count"]) <= chosen["comparison_count"] + 1
            ):
                logger.debug(f"good candidate found st {i} steps", start_timer=_start)
                break

            if i > 20:
                break

            if int(opp["comparison_count"]) < chosen["comparison_count"]:
                chosen = opp
                continue
            if _score_gap(source, opp) < _score_gap(source, chosen):
                chosen = opp
                continue

        if chosen is None:
            continue
        result = (source["filename"], chosen["filename"])
        logger.debug(f"return result after {i} steps", start_timer=_start)
        return result
    logger.debug(
        f"not pairs found for seed coverage, under_seed_target/ready: {len(under_seed_target)}/{len(seed_candidates)}"
    )
    return None


def phase_anchor_insert(
    candidate_images: list[dict[str, Any]],
    seed_pool: set[str],
    existing_pair_set: set[tuple[str, str]],
    cg: CrystalGraph,
    comparison_repo: ComparisonRepository,
) -> tuple[str, str] | None:
    _start = time.perf_counter()
    pool = _build_low_count_pool(
        [img for img in candidate_images if img["filename"] not in seed_pool]
    )
    reserve_count = config["ranking"]["reserve_count"]
    if len(pool) < reserve_count:
        logger.warning(
            f"phase_anchor_insert: pool too small ({len(pool)} < {reserve_count})",
            start_timer=_start,
        )
        return None

    pool.sort(key=lambda img: (int(img["comparison_count"]), float(img["score"])))
    source = pool[0]
    source_name = source["filename"]
    source_mu_skill = float(source["rating_mu"])

    remaining = [img for img in pool if img["filename"] != source_name]
    remaining.sort(key=lambda opp: (abs(float(opp["rating_mu"]) - source_mu_skill),))
    opponents = _find_unseen_candidates(source, remaining, existing_pair_set)
    seen_opponents = 0
    for opponent in opponents:
        seen_opponents += 1
        opp_name = opponent["filename"]
        if not _are_in_different_paths(source_name, opp_name, cg):
            continue
        result = (source_name, opp_name)
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


def _collapsible_extreme_pair(
    chains: list[ChainProxy],
    candidate_names: set[str],
    comparison_repo: ComparisonRepository,
    cg: CrystalGraph,
) -> tuple[str, str] | None:
    """Anchor on the least-compared node and return its most score-similar same-type partner."""

    check_list = comparison_repo.get_images_with_only_losses()
    use_bottom = True
    nodes: list[NodeProxy] = _collect_chain_extremes(
        chains, candidate_names, check_list, use_bottom, cg
    )

    if len(nodes) < 2:
        check_list = comparison_repo.get_images_with_only_wins()
        use_bottom = False
        nodes: list[NodeProxy] = _collect_chain_extremes(
            chains, candidate_names, check_list, use_bottom, cg
        )

    if len(nodes) < 2:
        logger.info(
            f"no candidates found, len:{len(nodes)}, bottom:{use_bottom}, checklist:{len(check_list)}"
        )
        return None

    node_a: NodeProxy = nodes[0]
    pair_list: list[tuple[NodeProxy, NodeProxy]] = [
        (node_a, node_b) for node_b in nodes[1:]
    ]
    pair_list.sort(
        key=lambda pair: abs(pair[0].score - pair[1].score),
    )

    node_a, node_b = pair_list[0]
    return (node_a.filename, node_b.filename)


def phase_collapsible_pairs(
    candidate_images: list[dict[str, Any]],
    pair_set: set[tuple[str, str]],
    cg: CrystalGraph,
    comparison_repo: ComparisonRepository,
) -> tuple[str, str] | None:
    _start = time.perf_counter()

    insertion_target = int(config["ranking"]["insertion_target_comparisons"])

    candidate_nodes = [cg.get_node(img["filename"]) for img in candidate_images]

    candidate_names = {
        node.filename
        for node in candidate_nodes
        if node is not None and node.comparison_count > insertion_target
    }

    chains_list = cg.get_all_chains()
    chains: list[ChainProxy] = [c[0] for c in chains_list]

    result = _collapsible_extreme_pair(chains, candidate_names, comparison_repo, cg)
    if result:
        logger.debug(f"collapsible pair: {result}", start_timer=_start)

    return result


_last_chains_index: list[int] = []


def phase_chain_merge(
    candidate_images: list[dict[str, Any]],
    cg: CrystalGraph,
    comparison_repo: ComparisonRepository,
) -> tuple[str, str] | None:
    global _last_chains_index
    score_threshold = 0.01
    min_comparisons = int(config["ranking"]["insertion_target_comparisons"])

    if len(_last_chains_index) > MIN_CHAIN_THRESHOLD:
        _last_chains_index = _last_chains_index[MIN_CHAIN_THRESHOLD // 2 :]

    _start = time.perf_counter()
    candidate_names = {img["filename"] for img in candidate_images}

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
            if i == j:
                continue
            b_nodes: list[NodeProxy] = [
                n[0] for n in chains[j] if n[0].filename in candidate_names and n[1]
            ]

            if len(b_nodes) == 0:
                continue

            b_mid: NodeProxy = b_nodes[len(b_nodes) // 2]
            pair_list: list[tuple[NodeProxy, NodeProxy]] = []
            pair_list.insert(0, (a_mid, b_mid))
            pair_list.extend(list(zip(a_nodes, b_nodes)))
            pair_list.extend(
                [
                    (node_a, node_b)
                    for node_a in a_nodes
                    for node_b in b_nodes
                    if node_a.filename != node_b.filename
                ]
            )
            for node_a, node_b in set(pair_list):
                a_name = node_a.filename
                b_name = node_b.filename
                if abs(node_a.score - node_b.score) > score_threshold:
                    continue

                if cg.are_in_same_path(a_name, b_name):
                    continue

                result = (a_name, b_name)
                _last_chains_index.append(i)
                _last_chains_index.append(j)
                logger.debug(f"I={i},j={j}", start_timer=_start)
                logger.debug(
                    f"chain i={len(a_nodes)}({len(chains[i])}),chain j={len(b_nodes)}({len(chains[j])})",
                    start_timer=_start,
                )

                return result
    logger.warning(
        f"skipping phase 4: no valid pair found in shorter {MIN_CHAIN_THRESHOLD*10} chains",
        start_timer=_start,
    )

    return None


def phase_uncertainty_refine(
    candidate_images: list[dict[str, Any]],
    pair_set: set[tuple[str, str]],
    cg: CrystalGraph,
    comparison_repo: ComparisonRepository,
) -> tuple[str, str] | None:
    _start = time.perf_counter()

    min_sigma_threshold = float(config["ranking"]["sigma_threshold"])

    seed_filenames: set[str] = set(stable_seed_pool(candidate_images))
    seed_pool: list[NodeProxy] = []
    candidate_nodes: list[NodeProxy] = []
    ready_nodes: list[NodeProxy] = []
    node_a: NodeProxy | None = None
    insertion_target = int(config["ranking"]["insertion_target_comparisons"])

    for img in candidate_images:
        node: NodeProxy | None = cg.get_node(img["filename"])
        if not node:
            continue
        if node.comparison_count <= insertion_target:
            continue

        candidate_nodes.append(node)

    candidate_nodes = sorted(
        candidate_nodes,
        key=lambda node: (-float(node.sigma_uncertainty)),
    )

    for node in candidate_nodes:
        if node.filename in seed_filenames:
            seed_pool.append(node)
        elif float(node.sigma_uncertainty) >= min_sigma_threshold:
            if not node_a:
                node_a = node
        else:
            ready_nodes.append(node)

    logger.debug(
        f"seed pool: {len(seed_pool)}/{len(candidate_images)}",
        start_timer=_start,
    )

    if not node_a or not seed_pool:
        return None

    best_pair: tuple[NodeProxy, NodeProxy] | None = None
    closest_ranking_mu: float = 100

    pair_list: list[tuple[NodeProxy, NodeProxy]] = [
        (node_a, node_b) for node_b in seed_pool
    ]
    pair_list = sorted(
        pair_list,
        key=lambda pair: abs(pair[0].mu_skill - pair[1].mu_skill),
    )

    for node_a, node_b in pair_list:
        if _pair_key(node_a.filename, node_b.filename) in pair_set:
            continue
        if cg.are_in_same_path(node_a.filename, node_b.filename):
            continue
        closest_ranking_mu = abs(node_a.mu_skill - node_b.mu_skill)
        best_pair = (node_a, node_b)
        break

    if best_pair:
        result: tuple[str, str] = (
            best_pair[0].filename,
            best_pair[1].filename,
        )
        logger.debug(
            f"Uncertainty refine selected pair: {result} (mu difference:{closest_ranking_mu})",
            start_timer=_start,
        )

        return result

    logger.debug(
        f"Uncertainty refine no pair found",
        start_timer=_start,
    )
    return None


def phase_fallback(
    candidate_images: list[dict[str, Any]],
    pair_set: set[tuple[str, str]],
    cg: CrystalGraph,
    comparison_repo: ComparisonRepository,
) -> tuple[str, str] | None:
    _start = time.perf_counter()
    ordered = sorted(
        candidate_images,
        key=lambda img: (int(img["comparison_count"]),),
    )
    for idx, left in enumerate(ordered):
        for right in ordered[idx + 1 :]:
            if _pair_key(left["filename"], right["filename"]) in pair_set:
                continue

            result = (left["filename"], right["filename"])

            return result
    return None
