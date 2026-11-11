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


def get_chain_merge_pair_candidates(
    a_nodes: list[NodeProxy],
    b_nodes: list[NodeProxy],
    a_mid: NodeProxy,
    b_mid: NodeProxy,
) -> list[Pair]:
    """Build midpoint, aligned, and cross-product pairs for two chains."""
    pair_list: list[Pair] = form_candidate_pairs(a_mid, [b_mid])
    chain_pairs: zip[tuple[NodeProxy, NodeProxy]] = zip(a_nodes, b_nodes)
    pair_list.extend(chain_pairs)
    for node_a in a_nodes:
        compatible_nodes: list[NodeProxy] = [
            node_b for node_b in b_nodes if node_b.filename != node_a.filename
        ]
        if compatible_nodes:
            pair_list.extend(form_candidate_pairs(node_a, compatible_nodes))
    return pair_list


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


def filter_chain_merge_pairs(
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


def filter_chain_middle_pairs(
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


def closest_score_pair(
    pair_list: list[Pair],
    closest: bool = False,
) -> Pair | None:
    """Choose a score-gap pair within the anchor's sigma range."""
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
