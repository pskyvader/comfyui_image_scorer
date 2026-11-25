"""Pair formation, filtering, and score-gap selection."""

from __future__ import annotations

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
    pair_list: list[Pair],
    existing_pair_set: set[tuple[str, str]],
    cg: CrystalGraphPort,
    check_same_path: bool = True,
) -> list[Pair]:
    """Drop compared or connected pairs, then cap the survivors at lru_size."""
    filtered: list[Pair] = [
        pair
        for pair in pair_list
        if canonicalize_pair(pair[0].filename, pair[1].filename)
        not in existing_pair_set
        and (
            not check_same_path
            or not cg.are_in_same_path(pair[0].filename, pair[1].filename)
        )
    ]
    return filtered[: int(config["ranking"]["lru_size"])]


def _key_cascade_score(item: tuple[int, Pair]) -> int:
    return -item[0]


def shortlist_by_cascade(pair_list: list[Pair], cg: CrystalGraphPort) -> list[Pair]:
    """Keep the highest-cascade pairs from an already lru-sized list."""
    scored: list[tuple[int, Pair]] = [
        (cg.get_cascade_score(pair[0].filename, pair[1].filename), pair)
        for pair in pair_list
    ]
    scored.sort(key=_key_cascade_score)
    lru_size: int = int(config["ranking"]["lru_size"])
    return [pair for _, pair in scored[: lru_size // 4]]


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
