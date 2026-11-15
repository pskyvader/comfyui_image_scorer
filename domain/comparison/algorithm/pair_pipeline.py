"""Pair formation, filtering, and score-gap selection."""

from __future__ import annotations

from tqdm import tqdm

from ....core.configuration.settings import config
from ...graph.node_proxy import NodeProxy
from ....domain.ports.graph import CrystalGraphPort
from .history_collapse import canonicalize_pair

Pair = tuple[NodeProxy, NodeProxy]


def form_candidate_pairs(
    node_a: NodeProxy, compatible_nodes: list[NodeProxy]
) -> list[Pair]:
    """Pair one anchor with every compatible opponent."""
    return [(node_a, node_b) for node_b in compatible_nodes]


def filter_existing_pairs(
    pair_list: list[Pair], existing_pair_set: set[tuple[str, str]]
) -> list[Pair]:
    """Remove pairs already present in comparison history."""
    return [
        pair
        for pair in pair_list
        if canonicalize_pair(pair[0].filename, pair[1].filename)
        not in existing_pair_set
    ]


def filter_cross_chain_pairs(
    pair_list: list[Pair],
    existing_pair_set: set[tuple[str, str]],
    cg: CrystalGraphPort,
) -> list[Pair] | None:
    """Keep new pairs from different main chains that are not already connected."""
    filtered_list: list[Pair] = [
        pair
        for pair in filter_existing_pairs(pair_list, existing_pair_set)
        if not cg.are_in_same_path(pair[0].filename, pair[1].filename)
    ]

    if not filtered_list:
        return None
    return filtered_list


def filter_uncertainty_refine_pairs(
    pair_list: list[Pair],
    pair_set: set[tuple[str, str]],
    cg: CrystalGraphPort,
) -> list[Pair] | None:
    """Remove previously compared and already-connected pairs."""
    filtered_pairs: list[Pair] = []
    pair_count: int = len(pair_list)
    with tqdm(total=pair_count, desc="Creating pair list", delay=3.0) as pbar:
        for pair in pair_list:
            pbar.update(1)
            if canonicalize_pair(pair[0].filename, pair[1].filename) in pair_set:
                continue
            if cg.are_in_same_path(pair[0].filename, pair[1].filename):
                continue
            filtered_pairs.append(pair)
    if not filtered_pairs:
        return None
    return filtered_pairs


def sigma_range_cap(node_a: NodeProxy) -> float:
    """Upper score-gap bound that the anchor's sigma allows for a pair."""
    return node_a.sigma_uncertainty * float(config["ranking"]["sigma_range_multiplier"])


def closest_score_pair(
    pair_list: list[Pair],
    closest: bool,
    sigma_cap: float,
) -> Pair | None:
    """Choose a score-gap pair within the given sigma cap."""
    if not pair_list:
        return None
    pair_list.sort(
        key=lambda pair: (
            abs(pair[0].trueskill_score - pair[1].trueskill_score),
            pair[1].link_count,
        )
    )
    best_pair: Pair = pair_list[0]
    best_difference: float = abs(
        best_pair[0].trueskill_score - best_pair[1].trueskill_score
    )
    if best_difference > sigma_cap:
        return None
    if closest:
        return best_pair

    for pair in pair_list:
        difference: float = abs(pair[0].trueskill_score - pair[1].trueskill_score)
        if difference > sigma_cap:
            break
        if difference > best_difference:
            best_difference = difference
            best_pair = pair
    return best_pair
