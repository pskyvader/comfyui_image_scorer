"""Read-only serialization of graph objects into comparison-frontend payloads.

All functions accept ``NodeProxy`` objects directly so that, when the phase
selectors later return proxies instead of filename strings, no signature change
is required here. All field reading is isolated in the helpers below.
"""

from __future__ import annotations

from typing import Any, TypedDict

from ....core.configuration.settings import config
from ...graph.node_proxy import NodeProxy
from ...analysis.trueskill import expected_win_probability, Rating
from . import graph_helpers

from ....domain.ports.graph import CrystalGraphPort, GraphStructure


class ScoreBucket(TypedDict):
    """One equal-width histogram bucket."""

    lower: float
    upper: float
    count: int


class Distribution(TypedDict):
    """A measured series plus its histogram, in ascending bucket order."""

    min: float
    max: float
    mean: float
    buckets: list[ScoreBucket]


class RankedExtremes(TypedDict):
    """One row of a top/bottom score table."""

    filename: str
    score: float
    rating_mu: float
    rating_sigma: float
    link_count: int


class GraphStats(TypedDict):
    """Whole-graph ranking measurements shared by every graph-wide view."""

    total_nodes: int
    score: Distribution
    rating_mu: Distribution
    rating_sigma: Distribution
    link_count: Distribution
    link_level: dict[int, int]
    sigma_threshold: float
    sigma_above_threshold: int
    sigma_below_threshold: int
    single_win_count: int
    single_loss_count: int
    ready_count: int
    ranked: int
    unranked: int
    top: list[RankedExtremes]
    bottom: list[RankedExtremes]
    structure: GraphStructure


def _bucket_edges(values: list[float], bucket_count: int) -> list[tuple[float, float]]:
    lower = min(values)
    upper = max(values)
    if upper == lower:
        return [(lower, upper)]
    width = (upper - lower) / bucket_count
    return [(lower + i * width, lower + (i + 1) * width) for i in range(bucket_count)]


def _distribution(values: list[float], bucket_count: int) -> Distribution:
    edges = _bucket_edges(values, bucket_count)
    last = len(edges) - 1
    buckets: list[ScoreBucket] = []
    for index, (lower, upper) in enumerate(edges):
        if index == last:
            count = sum(1 for v in values if lower <= v <= upper)
        else:
            count = sum(1 for v in values if lower <= v < upper)
        buckets.append({"lower": lower, "upper": upper, "count": count})
    return {
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "buckets": buckets,
    }


def _extremes(nodes: list[NodeProxy], limit: int, *, highest_first: bool) -> list[RankedExtremes]:
    ordered = sorted(nodes, key=lambda n: float(n.score), reverse=highest_first)
    return [
        {
            "filename": node.filename,
            "score": round(float(node.score), 4),
            "rating_mu": round(float(node.mu_skill), 4),
            "rating_sigma": round(float(node.sigma_uncertainty), 4),
            "link_count": int(node.link_count),
        }
        for node in ordered[:limit]
    ]



def _describe_one(node: NodeProxy, cg: CrystalGraphPort) -> dict[str, Any]:
    """Build the per-image payload from a NodeProxy.

    Every field is read through the proxy; no database row is touched here.
    """
    component = node.get_component()
    chain = node.get_chain(only_main=True)
    chain_length = chain[0].length if chain else 0
    chain_id = chain[0].id if chain else None
    chain_main_members = (
        cg.get_main_chain_member_count(chain_id)
        if chain_id is not None
        else 0
    )

    seed_target = int(config["ranking"]["seed_target_comparisons"])
    is_seed = node.link_count >= seed_target

    extremes = {"top": 0, "bottom": 0}
    if component is not None:
        extremes = {
            "top": sum(1 for member in component.nodes if member.is_top()),
            "bottom": sum(1 for member in component.nodes if member.is_bottom()),
        }

    return {
        "filename": node.filename,
        "score": round(float(node.score), 4),
        "rating_mu": round(float(node.mu_skill), 4),
        "rating_sigma": round(float(node.sigma_uncertainty), 4),
        "trueskill_score": round(float(node.trueskill_score), 4),
        "link_count": int(node.link_count),
        "wins": len(node.get_links(worse_than=True)),
        "losses": len(node.get_links(better_than=True)),
        "chain_length": chain_length,
        "chain_id": chain_id,
        "chain_main_members": chain_main_members,
        "component_size": component.size if component is not None else 0,
        "component_id": component.id if component is not None else None,
        "is_top": node.is_top(),
        "is_bottom": node.is_bottom(),
        "is_seed": is_seed,
        "_extremes": extremes,
    }


def describe_image(node: NodeProxy, cg: CrystalGraphPort) -> dict[str, Any]:
    """Return all per-image info for a single node, regardless of phase."""
    return _describe_one(node, cg)


def describe_graph(cg: CrystalGraphPort) -> GraphStats:
    """Return whole-graph ranking measurements.

    Promoted out of ``describe_pair`` so the analyze page can serialize the same
    numbers the pair payload carries. There is one owner for the sigma-threshold
    and readiness counts; the pair payload is a projection of this.
    """
    ranking_conf = config["ranking"]
    sigma_threshold = float(ranking_conf["sigma_threshold"])
    bucket_count = int(ranking_conf["analysis_histogram_bucket_count"])
    extremes_count = int(ranking_conf["analysis_top_bottom_display_rows"])

    structure: GraphStructure = cg.get_graph_stats()
    all_nodes = cg.get_all_nodes()
    scores: list[float] = []
    mus: list[float] = []
    sigmas: list[float] = []
    counts: list[float] = []
    level_counts: dict[int, int] = {}
    sigma_above = 0
    single_win_count = 0
    single_loss_count = 0
    ready_count = 0
    for node in all_nodes:
        score = float(node.score)
        mu = float(node.mu_skill)
        sigma = float(node.sigma_uncertainty)
        comparisons = int(node.link_count)
        scores.append(score)
        mus.append(mu)
        sigmas.append(sigma)
        counts.append(comparisons)
        level_counts[comparisons] = level_counts.get(comparisons, 0) + 1
        if sigma >= sigma_threshold:
            sigma_above += 1
        wins = len(node.get_links(worse_than=True))
        losses = len(node.get_links(better_than=True))
        if wins == 1:
            single_win_count += 1
        if losses == 1:
            single_loss_count += 1
        if wins > 1 and losses > 1:
            ready_count += 1

    ranked = sum(1 for c in counts if c > 0)
    total = len(all_nodes)

    if not total:
        empty: Distribution = {"min": 0.0, "max": 0.0, "mean": 0.0, "buckets": []}
        return {
            "total_nodes": 0,
            "score": empty,
            "rating_mu": empty,
            "rating_sigma": empty,
            "link_count": empty,
            "link_level": {},
            "sigma_threshold": sigma_threshold,
            "sigma_above_threshold": 0,
            "sigma_below_threshold": 0,
            "single_win_count": 0,
            "single_loss_count": 0,
            "ready_count": 0,
            "ranked": 0,
            "unranked": 0,
            "top": [],
            "bottom": [],
            "structure": structure,
        }

    return {
        "total_nodes": total,
        "score": _distribution(scores, bucket_count),
        "rating_mu": _distribution(mus, bucket_count),
        "rating_sigma": _distribution(sigmas, bucket_count),
        "link_count": _distribution(counts, bucket_count),
        "link_level": level_counts,
        "sigma_threshold": sigma_threshold,
        "sigma_above_threshold": sigma_above,
        "sigma_below_threshold": total - sigma_above,
        "single_win_count": single_win_count,
        "single_loss_count": single_loss_count,
        "ready_count": ready_count,
        "ranked": ranked,
        "unranked": total - ranked,
        "top": _extremes(all_nodes, extremes_count, highest_first=True),
        "bottom": _extremes(all_nodes, extremes_count, highest_first=False),
        "structure": structure,
    }


def describe_pair(
    node_a: NodeProxy,
    node_b: NodeProxy,
    phase_index: int,
    cg: CrystalGraphPort,
) -> dict[str, Any]:
    """Return phase-specific pair context built from the two nodes and config.

    ``phase_index`` is an int (0=seed, 1=anchor, 2=collapsible,
    3=single_win_loss, 4=chain_middle, 5=refine, 6=chain_merge, 7=fallback). The int->label
    mapping lives on the frontend.
    """
    ranking_conf = config["ranking"]

    left = _describe_one(node_a, cg)
    right = _describe_one(node_b, cg)

    base_level = min(left["link_count"], right["link_count"])

    stats = describe_graph(cg)
    structure = stats["structure"]

    rating_a = Rating(mu_skill=node_a.mu_skill, sigma_uncertainty=node_a.sigma_uncertainty)
    rating_b = Rating(mu_skill=node_b.mu_skill, sigma_uncertainty=node_b.sigma_uncertainty)
    probability_a_beats_b = expected_win_probability(rating_a, rating_b)

    component_a = node_a.get_component()
    component_b = node_b.get_component()
    same_component = (
        component_a is not None
        and component_b is not None
        and component_a.id == component_b.id
    )

    return {
        "phase": phase_index,
        "total_nodes": stats["total_nodes"],
        "total_links": structure["total_links"],
        "total_chains": structure["total_chains"],
        "target_chains": int(ranking_conf["minimum_chains_for_pairing"]),
        "level": stats["link_level"],
        "base_level": base_level,
        "collapsible": graph_helpers.is_collapsable_pair(
            node_a.filename, node_b.filename, cg
        ),
        "same_component": same_component,
        "seed_percentage": int(ranking_conf["seed_percentage"]),
        "seed_target_comparisons": int(ranking_conf["seed_target_comparisons"]),
        "insertion_target_comparisons": int(
            ranking_conf["insertion_target_comparisons"]
        ),
        "reserve_count": int(ranking_conf["reserve_count"]),
        "sigma_threshold": stats["sigma_threshold"],
        "sigma_above_threshold": stats["sigma_above_threshold"],
        "sigma_below_threshold": stats["sigma_below_threshold"],
        "single_win_count": stats["single_win_count"],
        "single_loss_count": stats["single_loss_count"],
        "ready_count": stats["ready_count"],
        "probability_a_beats_b": round(probability_a_beats_b, 4),
    }
