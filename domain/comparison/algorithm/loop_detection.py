"""Cycle-cutting machinery for the comparison graph.

Computes, per cyclic SCC, which comparisons to remove so no directed cycle
remains: walk one cycle at a time and cut its most suspect edge under a
configurable rule, restricted to positive-gap edges (loser scored above
winner).
"""

from __future__ import annotations

import random
import time
from collections import defaultdict
from dataclasses import dataclass
from math import sqrt
from typing import Literal

from comfyui_image_scorer.core.observability.logger import get_logger
from comfyui_image_scorer.domain.analysis.trueskill import (
    Rating,
    public_score_from_rating,
    trueskill_score_from_rating,
)
from comfyui_image_scorer.domain.comparison.algorithm.history_collapse import (
    canonicalize_pair,
    safe_parse_timestamp,
)
from comfyui_image_scorer.domain.graph.chain_manager import ChainManager, tarjan_scc
from comfyui_image_scorer.domain.graph.link_proxy import LinkProxy
from comfyui_image_scorer.domain.graph.node_proxy import NodeProxy

logger = get_logger(__name__)

CutRule = Literal["gap_ts", "ts_gap", "gap_random", "sigma", "random"]
ScoreForm = Literal["trueskill", "public", "position"]


@dataclass(frozen=True)
class CutEntry:
    canon: tuple[str, str]
    link: LinkProxy
    gap: float
    sigma_pair: float
    scc_id: int
    scc_size: int
    cycle_length: int


@dataclass(frozen=True)
class SccStat:
    scc_id: int
    size: int
    cuts: int
    clean: bool
    lower_bound: int | None


@dataclass(frozen=True)
class PassResult:
    entries: list[CutEntry]
    complete: bool
    residual_cyclic: int
    scc_stats: list[SccStat]
    pruned_count: int
    pruned_canons: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CutGraph:
    all_filenames: set[str]
    edge_to_comp: dict[tuple[str, str], LinkProxy]
    successors: defaultdict[str, list[str]]
    cyclic_sccs: list[tuple[int, list[str]]]
    cyclic_members: set[str]


def proxy_scores(
    nodes: list[NodeProxy], form: ScoreForm
) -> tuple[dict[str, float], dict[str, float]]:
    scores: dict[str, float] = {}
    sigmas: dict[str, float] = {}
    for node in nodes:
        rating: Rating = Rating(
            mu_skill=node.mu_skill, sigma_uncertainty=node.sigma_uncertainty
        )
        sigmas[node.filename] = rating.sigma_uncertainty
        if form == "trueskill":
            scores[node.filename] = trueskill_score_from_rating(rating)
        elif form == "public":
            scores[node.filename] = public_score_from_rating(rating)
        else:
            scores[node.filename] = float(node.position_score)
    return scores, sigmas


def build_cut_graph(chain_manager: ChainManager, links: list[LinkProxy]) -> CutGraph:
    edge_to_comp: dict[tuple[str, str], LinkProxy] = {}
    for link in links:
        key: tuple[str, str] = (link.winner, link.loser)
        if key not in edge_to_comp or link.id > edge_to_comp[key].id:
            edge_to_comp[key] = link
    successors: defaultdict[str, list[str]] = defaultdict(list)
    for winner, loser in chain_manager.get_all_edges():
        successors[winner].append(loser)
    _, scc_members = tarjan_scc(chain_manager.get_all_filenames(), successors)
    cyclic: dict[int, list[str]] = {
        scc_id: members for scc_id, members in scc_members.items() if len(members) > 1
    }
    ordered: list[tuple[int, list[str]]] = sorted(
        cyclic.items(), key=lambda item: len(item[1]), reverse=True
    )
    return CutGraph(
        all_filenames=chain_manager.get_all_filenames(),
        edge_to_comp=edge_to_comp,
        successors=successors,
        cyclic_sccs=ordered,
        cyclic_members={m for _, members in ordered for m in members},
    )


def _timestamp_value(link: LinkProxy) -> float:
    return safe_parse_timestamp(link.timestamp or "")[1].timestamp()


def _rule_key(
    rule: CutRule,
    link: LinkProxy,
    gap: float,
    sigma_pair: float,
    rng: random.Random,
) -> tuple[float, ...]:
    if rule == "gap_ts":
        return (-gap, _timestamp_value(link))
    if rule == "ts_gap":
        return (_timestamp_value(link), -gap)
    if rule == "gap_random":
        return (-gap, rng.random())
    if rule == "sigma":
        return (-sigma_pair, -gap)
    return (rng.random(),)


def _find_cycle(nodes: list[str], succ: dict[str, list[str]]) -> list[str]:
    """Return one directed cycle from a node set known to contain one."""
    node_set: set[str] = set(nodes)
    indeg: dict[str, int] = {n: 0 for n in nodes}
    for n in nodes:
        for m in succ.get(n, []):
            if m in node_set:
                indeg[m] += 1
    peel: list[str] = [n for n in nodes if indeg[n] == 0]
    remaining: set[str] = set(nodes)
    while peel:
        v = peel.pop()
        remaining.discard(v)
        for m in succ.get(v, []):
            if m in remaining:
                indeg[m] -= 1
                if indeg[m] == 0:
                    peel.append(m)
    v = min(remaining)
    seen: set[str] = set()
    path: list[str] = []
    while v not in seen:
        seen.add(v)
        path.append(v)
        v = min(m for m in succ.get(v, []) if m in remaining)
    return path[path.index(v) :]


def _disjoint_cycle_lower_bound(nodes: set[str], succ: dict[str, list[str]]) -> int:
    remaining: dict[str, list[str]] = {n: list(edges) for n, edges in succ.items()}
    count: int = 0
    while True:
        _, members = tarjan_scc(nodes, defaultdict(list, remaining))
        cyclic: list[list[str]] = [m for m in members.values() if len(m) > 1]
        if not cyclic:
            break
        cycle: list[str] = _find_cycle(max(cyclic, key=len), remaining)
        for i in range(len(cycle)):
            winner: str = cycle[i]
            loser: str = cycle[(i + 1) % len(cycle)]
            remaining[winner] = [m for m in remaining.get(winner, []) if m != loser]
        count += 1
    return count


def _prune_redundant(
    graph: CutGraph,
    cut_pairs: set[tuple[str, str]],
    ordered_canons: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    sub_succ: dict[str, list[str]] = {
        node: [m for m in graph.successors.get(node, []) if m in graph.cyclic_members]
        for node in graph.cyclic_members
    }
    pruned: list[tuple[str, str]] = []
    for canon in ordered_canons:
        if canon not in cut_pairs:
            continue
        test_pairs: set[tuple[str, str]] = cut_pairs - {canon}
        test_succ: defaultdict[str, list[str]] = defaultdict(list)
        for winner, edges in sub_succ.items():
            test_succ[winner] = [
                m for m in edges if canonicalize_pair(winner, m) not in test_pairs
            ]
        _, members = tarjan_scc(set(graph.cyclic_members), test_succ)
        if not any(len(m) > 1 for m in members.values()):
            cut_pairs.discard(canon)
            pruned.append(canon)
    return pruned


def run_cut_pass(
    graph: CutGraph,
    scores: dict[str, float],
    sigmas: dict[str, float],
    rule: CutRule,
    prune: bool,
    lower_bound: bool,
    seed: int,
) -> PassResult:
    rng: random.Random = random.Random(seed)
    cut_pairs: set[tuple[str, str]] = set()
    entries: list[CutEntry] = []
    scc_stats: list[SccStat] = []
    for scc_id, members in graph.cyclic_sccs:
        member_set: set[str] = set(members)
        original_succ: dict[str, list[str]] = {
            n: [m for m in graph.successors.get(n, []) if m in member_set]
            for n in members
        }
        local_succ: dict[str, list[str]] = {
            n: list(edges) for n, edges in original_succ.items()
        }
        scc_clean: bool = True
        scc_cuts: int = 0
        while True:
            _, sub_members = tarjan_scc(member_set, defaultdict(list, local_succ))
            cyclic_sub: list[list[str]] = [
                m for m in sub_members.values() if len(m) > 1
            ]
            if not cyclic_sub:
                break
            cycle: list[str] = _find_cycle(max(cyclic_sub, key=len), local_succ)
            cycle_len: int = len(cycle)
            candidates: list[tuple[LinkProxy, float, float]] = []
            for i in range(cycle_len):
                cycle_winner: str = cycle[i]
                cycle_loser: str = cycle[(i + 1) % cycle_len]
                if canonicalize_pair(cycle_winner, cycle_loser) in cut_pairs:
                    continue
                link: LinkProxy | None = graph.edge_to_comp.get(
                    (cycle_winner, cycle_loser)
                )
                if link is None:
                    continue
                gap: float = scores[link.loser] - scores[link.winner]
                if gap <= 0:
                    continue
                sigma_pair: float = sqrt(
                    sigmas[link.winner] ** 2 + sigmas[link.loser] ** 2
                )
                candidates.append((link, gap, sigma_pair))
            if not candidates:
                logger.error(
                    "SCC %d: cycle %s has no positive-gap edge; leaving it uncut",
                    scc_id,
                    cycle,
                )
                scc_clean = False
                break
            best_link, best_gap, best_sigma = min(
                candidates,
                key=lambda candidate: _rule_key(
                    rule, candidate[0], candidate[1], candidate[2], rng
                ),
            )
            canon: tuple[str, str] = canonicalize_pair(
                best_link.winner, best_link.loser
            )
            cut_pairs.add(canon)
            entries.append(
                CutEntry(
                    canon=canon,
                    link=best_link,
                    gap=best_gap,
                    sigma_pair=best_sigma,
                    scc_id=scc_id,
                    scc_size=len(members),
                    cycle_length=cycle_len,
                )
            )
            local_succ[best_link.winner] = [
                m for m in local_succ.get(best_link.winner, []) if m != best_link.loser
            ]
            local_succ[best_link.loser] = [
                m for m in local_succ.get(best_link.loser, []) if m != best_link.winner
            ]
            scc_cuts += 1
        lower: int | None = (
            _disjoint_cycle_lower_bound(member_set, original_succ)
            if lower_bound
            else None
        )
        scc_stats.append(
            SccStat(
                scc_id=scc_id,
                size=len(members),
                cuts=scc_cuts,
                clean=scc_clean,
                lower_bound=lower,
            )
        )
    pruned_canons: list[tuple[str, str]] = []
    if prune:
        pruned_canons = _prune_redundant(
            graph, cut_pairs, [entry.canon for entry in entries]
        )
    residual_succ: defaultdict[str, list[str]] = defaultdict(list)
    for winner, edges in graph.successors.items():
        residual_succ[winner] = [
            m for m in edges if canonicalize_pair(winner, m) not in cut_pairs
        ]
    _, residual_members = tarjan_scc(graph.all_filenames, residual_succ)
    residual_cyclic: int = len([m for m in residual_members.values() if len(m) > 1])
    return PassResult(
        entries=entries,
        complete=residual_cyclic == 0,
        residual_cyclic=residual_cyclic,
        scc_stats=scc_stats,
        pruned_count=len(pruned_canons),
        pruned_canons=tuple(pruned_canons),
    )


def run_cut_phase(
    cut_graph: CutGraph, nodes: list[NodeProxy], score_form: ScoreForm, rule: CutRule
) -> PassResult:
    t0: float = time.perf_counter()
    scores, sigmas = proxy_scores(nodes, score_form)
    result: PassResult = run_cut_pass(
        cut_graph, scores, sigmas, rule, prune=False, lower_bound=False, seed=0
    )
    for stat in result.scc_stats:
        logger.info(
            "SCC %d (n=%d): %d cut(s), %s",
            stat.scc_id,
            stat.size,
            stat.cuts,
            "clean" if stat.clean else "left uncut",
        )
    logger.info(
        "Cut list: %d pairs, complete=%s, remaining cyclic SCCs=%d",
        len(result.entries),
        result.complete,
        result.residual_cyclic,
        start_timer=t0,
    )
    if not result.complete:
        logger.error("Cut set incomplete - some cycles have no positive-gap edge")
    return result


def cycles_after_removal(
    chain_manager: ChainManager, removed_pairs: set[tuple[str, str]]
) -> list[list[str]]:
    successors: defaultdict[str, list[str]] = defaultdict(list)
    for winner, loser in chain_manager.get_all_edges():
        if canonicalize_pair(winner, loser) not in removed_pairs:
            successors[winner].append(loser)
    _, members = tarjan_scc(chain_manager.get_all_filenames(), successors)
    return [m for m in members.values() if len(m) > 1]
