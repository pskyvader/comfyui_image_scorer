"""Compatible-node and opponent selection for pairing phases."""

from __future__ import annotations

from ....core.configuration.settings import config
from ....core.observability.logger import get_logger, ModuleLogger
from ...graph.node_proxy import NodeProxy
from .pair_candidates import seed_pool_size

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
    opponent_candidates: list[NodeProxy] = under_seed_target[
        1 : (seed_pool_size(all_images_length) - ready_seed_pool_length + 1)
    ]
    eligible_opponents: list[NodeProxy] = [
        node for node in opponent_candidates if node.link_count <= node_a.link_count + 2
    ]
    return get_compatible_nodes(eligible_opponents, node_a)


def get_anchor_insert_opponents(
    candidate_nodes: list[NodeProxy],
    node_a: NodeProxy,
    seed_target_comparisons: int,
) -> list[NodeProxy] | None:
    """Select the most-compared <=seed_target_comparisons candidates other than the anchor."""
    seed_candidates: list[NodeProxy] = [
        node for node in candidate_nodes if node.link_count <= seed_target_comparisons
    ]
    seed_candidates.sort(key=lambda node: node.link_count, reverse=True)
    seed_candidates = seed_candidates[: int(config["ranking"]["lru_size"])]
    return get_compatible_nodes(seed_candidates, node_a)


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
