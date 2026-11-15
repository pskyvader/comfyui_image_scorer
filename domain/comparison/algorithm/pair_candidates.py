"""Candidate and anchor selection for pairing phases."""

from __future__ import annotations

import random

from ....core.configuration.settings import config
from ...graph.chain_proxy import ChainProxy
from ...graph.node_proxy import NodeProxy


def seed_pool_size(all_images_length: int) -> int:
    """Seed-pool size target derived from the image count."""
    seed_percentage: int = int(config["ranking"]["seed_percentage"])
    return all_images_length * seed_percentage // 100


def get_seed_coverage_ready_pool_length(
    seed_pool: list[NodeProxy], all_images_length: int
) -> int | None:
    """Count ready seed nodes or return None when the seed target is complete."""
    seed_size: int = seed_pool_size(all_images_length)
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


def collect_small_chain_anchors(
    chains: list[ChainProxy],
    candidate_nodes: list[NodeProxy],
) -> list[NodeProxy]:
    """Return each chain's extreme main nodes as candidate proxies, least-compared first.

    Anchors are the top and bottom of each chain (a single node for chains of
    length one); comparing an extreme is what lets a later win or loss absorb
    the whole chain into the opponent's.
    """
    nodes: list[NodeProxy] = []
    seen: set[str] = set()
    candidates_by_name: dict[str, NodeProxy] = {
        node.filename: node for node in candidate_nodes
    }

    for raw_chain in chains:
        for position in (0, raw_chain.main_length - 1):
            main_node: NodeProxy | None = raw_chain.main_node_at(position)
            if main_node is None:
                continue
            filename: str = main_node.filename
            if filename in seen:
                continue
            candidate: NodeProxy | None = candidates_by_name.get(filename)
            if candidate is None:
                continue
            seen.add(filename)
            nodes.append(candidate)

    nodes.sort(key=lambda node: node.link_count)
    lru_size: int = int(config["ranking"]["lru_size"])
    return nodes[:lru_size]


def collect_long_chain_opponents(
    chains: list[ChainProxy],
    candidate_nodes: list[NodeProxy],
) -> list[NodeProxy]:
    """Return every main-chain member of the given chains as candidates, least-compared first."""
    nodes: list[NodeProxy] = []
    seen: set[str] = set()
    candidates_by_name: dict[str, NodeProxy] = {
        node.filename: node for node in candidate_nodes
    }

    for raw_chain in chains:
        for position in range(raw_chain.main_length):
            main_node: NodeProxy | None = raw_chain.main_node_at(position)
            if main_node is None:
                continue
            filename: str = main_node.filename
            if filename in seen:
                continue
            candidate: NodeProxy | None = candidates_by_name.get(filename)
            if candidate is None:
                continue
            seen.add(filename)
            nodes.append(candidate)

    nodes.sort(key=lambda node: node.link_count)
    lru_size: int = int(config["ranking"]["lru_size"])
    return nodes[:lru_size]
