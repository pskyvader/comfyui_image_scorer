"""Compatible-node and opponent selection for pairing phases."""

from __future__ import annotations

from ....core.configuration.settings import config
from ....core.observability.logger import get_logger, ModuleLogger
from ...graph.chain_proxy import ChainProxy
from ...graph.node_proxy import NodeProxy

logger: ModuleLogger = get_logger(__name__)


def get_compatible_nodes(
    candidate_nodes: list[NodeProxy],
    node_a: NodeProxy,
) -> list[NodeProxy] | None:
    """Return compatible opponents, or None when the list is empty."""
    compatible_nodes: list[NodeProxy] = [
        node_b for node_b in candidate_nodes if node_b.filename != node_a.filename
    ]
    return compatible_nodes or None


def get_seed_coverage_opponents(
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
    return get_compatible_nodes(eligible_opponents, node_a)


def get_anchor_insert_opponents(
    candidate_nodes: list[NodeProxy],
    node_a: NodeProxy,
) -> list[NodeProxy] | None:
    """Select the most-compared <=seed_target_comparisons candidates other than the anchor."""
    seed_target_comparisons: int = int(config["ranking"]["seed_target_comparisons"])
    seed_candidates: list[NodeProxy] = [
        node for node in candidate_nodes if node.link_count <= seed_target_comparisons
    ]
    seed_candidates.sort(key=lambda node: node.link_count, reverse=True)
    seed_candidates = seed_candidates[: int(config["ranking"]["lru_size"])]
    return get_compatible_nodes(seed_candidates, node_a)


def get_branch_chain_compatible_nodes(
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
        if upper_index - i < 0:
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


def get_uncertainty_refine_opponents(
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
    return get_compatible_nodes(seed_pool, node_a)
