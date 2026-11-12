"""Candidate and anchor selection for pairing phases."""

from __future__ import annotations

from collections.abc import Iterator
import random

from ....core.configuration.settings import config
from ....core.observability.logger import get_logger, ModuleLogger
from ...graph.chain_proxy import ChainProxy
from ...graph.node_proxy import NodeProxy
from ....domain.ports.graph import CrystalGraphPort

logger: ModuleLogger = get_logger(__name__)


def get_seed_coverage_ready_pool_length(
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


def get_seed_coverage_under_target_nodes(
    candidate_nodes: list[NodeProxy],
) -> list[NodeProxy]:
    """Return candidates below the seed comparison target, most-compared first."""
    seed_target: int = int(config["ranking"]["seed_target_comparisons"])
    lru_size: int = int(config["ranking"]["lru_size"])
    under_seed_target: list[NodeProxy] = [
        node for node in candidate_nodes if node.link_count < seed_target
    ]
    under_seed_target.sort(key=lambda node: node.link_count, reverse=True)
    return under_seed_target[:lru_size]


def select_anchor_insert_node(
    candidate_nodes: list[NodeProxy],
) -> NodeProxy | None:
    """Select the lowest-comparison candidate at or below the insertion target."""
    insertion_target: int = int(config["ranking"]["insertion_target_comparisons"])
    node_list: list[NodeProxy] = [
        node for node in candidate_nodes if node.link_count <= insertion_target
    ]
    if not node_list:
        return None
    node_list.sort(key=lambda node: (node.link_count, node.position_score))
    node_list = node_list[: int(config["ranking"]["lru_size"])]
    return random.choice(node_list)


def _collect_chain_extremes(
    chains: list[ChainProxy],
    candidate_names: set[str],
    check_list: list[str],
    use_bottom: bool,
    cg: CrystalGraphPort,
) -> list[NodeProxy]:
    """Return qualifying chain extremes, least-compared first."""
    nodes: list[NodeProxy] = []
    seen: set[str] = set()
    errors: dict[str, int] = {
        "extreme": 0,
        # "seen": 0,
        "is_top_bottom": 0,
        "not_in_candidates": 0,
        "not_in_checklist": 0,
        "not_in_graph": 0,
    }
    for chain in chains:
        chain_extreme: NodeProxy | None = chain.last if use_bottom else chain.first
        if not chain_extreme:
            errors["extreme"] += 1
            continue
        filename: str = chain_extreme.filename
        if filename in seen:
            # errors["seen"] += 1
            continue
        seen.add(filename)
        if not chain_extreme.is_bottom() if use_bottom else not chain_extreme.is_top():
            errors["is_top_bottom"] += 1
            continue
        if chain_extreme.filename not in candidate_names:
            errors["not_in_candidates"] += 1
            continue
        if chain_extreme.filename not in check_list:
            errors["not_in_checklist"] += 1
            continue

        node: NodeProxy | None = cg.get_node(filename)
        if node is None:
            errors["not_in_graph"] += 1
            continue
        nodes.append(node)

    nodes.sort(key=lambda node: node.link_count)
    lru_size: int = int(config["ranking"]["lru_size"])
    # check if errors have any non-zero values and log them
    for error_type, count in errors.items():
        if count > 0:
            logger.debug(f"Error type '{error_type}' occurred {count} times.")
    return nodes[:lru_size]


def get_collapsible_candidates(
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
    nodes.sort(key=lambda node: node.score)
    lru_size: int = int(config["ranking"]["lru_size"])
    return nodes[:lru_size], use_bottom, check_list


def get_single_win_loss_candidate_lanes(
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
            nodes.sort(key=lambda node: (node.link_count, node.score))
            yield single_win, filtered_only, nodes[: int(config["ranking"]["lru_size"])]


def prepare_single_win_loss_lane(
    node_a: NodeProxy,
    nodes: list[NodeProxy],
    single_win: bool,
    filtered_only: bool,
    minimum_count: float,
) -> tuple[list[NodeProxy], float]:
    """Choose a lane anchor and apply its comparison-count eligibility rule."""

    if single_win:
        minimum_count = float(nodes[0].link_count)
    partner_nodes: list[NodeProxy] = [
        node for node in nodes if node.filename != node_a.filename
    ]
    if filtered_only and node_a.link_count >= minimum_count:
        partner_nodes: list[NodeProxy] = [
            node for node in partner_nodes if node.link_count <= node_a.link_count
        ]
        # reserve_count: int = int(config["ranking"]["reserve_count"])
        # if len(filtered_nodes) < reserve_count:
        #     return [], minimum_count
        # partner_nodes = [
        #     node for node in filtered_nodes if node.filename != node_a.filename
        # ]
    return partner_nodes, minimum_count


def iter_chain_merge_chain_pairs(
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


def select_uncertainty_refine_anchor(
    candidate_nodes: list[NodeProxy], seed_pool_set: set[str]
) -> NodeProxy | None:
    """Select the most uncertain eligible candidate outside the seed pool."""
    min_sigma_threshold: float = float(config["ranking"]["sigma_threshold"])
    insertion_target: int = int(config["ranking"]["insertion_target_comparisons"])
    lru_size: int = int(config["ranking"]["lru_size"])
    target_nodes: list[NodeProxy] = [
        node
        for node in candidate_nodes
        if node.link_count > insertion_target
        and node.sigma_uncertainty >= min_sigma_threshold
        and node.filename not in seed_pool_set
    ]
    target_nodes.sort(key=lambda node: node.sigma_uncertainty, reverse=True)
    target_nodes = target_nodes[:lru_size]
    return random.choice(target_nodes) if target_nodes else None


def collect_chain_midpoints(
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
        if candidate_names and (filename not in candidate_names):
            continue

        node: NodeProxy = candidates_by_name[filename]
        # if node.get_chain()[0].id != raw_chain.id:
        #     raise ValueError(
        #         f"Chain midpoint node {filename} does not belong to the expected chain {raw_chain.id}."
        #     )

        seen.add(filename)
        nodes.append(node)

    nodes.sort(key=lambda node: node.link_count)
    lru_size: int = int(config["ranking"]["lru_size"])
    return nodes[:lru_size]
