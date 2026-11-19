"""Temporary helpers for the one-time cut-stability experiment notebook."""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass

import matplotlib.image as mpimg
import matplotlib.pyplot as plt

from comfyui_image_scorer.core.observability.logger import get_logger
from comfyui_image_scorer.domain.analysis.trueskill import (
    public_score_from_rating,
    replay_ratings,
)
from comfyui_image_scorer.domain.comparison.algorithm.history_collapse import (
    canonicalize_pair,
)
from comfyui_image_scorer.domain.comparison.algorithm.loop_detection import (
    CutEntry,
    CutGraph,
    PassResult,
)
from comfyui_image_scorer.domain.graph.chain_manager import tarjan_scc
from comfyui_image_scorer.domain.graph.link_proxy import LinkProxy
from comfyui_image_scorer.infrastructure.persistence.path_handler import find_image_path

logger = get_logger(__name__)

SEED: int = 45700


@dataclass(frozen=True)
class PairStats:
    canon: tuple[str, str]
    count: int
    run_count: int
    frequency: float
    mean_gap: float
    mean_sigma: float
    scc_ids: tuple[int, ...]
    row_ids: tuple[int, ...]
    min_ts: str


def replay_scores(
    links: list[LinkProxy], seed: int
) -> tuple[dict[str, float], dict[str, float]]:
    random.seed(seed)
    replayed = replay_ratings([link.data for link in links], order="random")
    scores: dict[str, float] = {}
    sigmas: dict[str, float] = {}
    for filename, (rating, _count) in replayed.items():
        scores[filename] = public_score_from_rating(rating)
        sigmas[filename] = rating.sigma_uncertainty
    return scores, sigmas


def aggregate_runs(results: list[PassResult], run_count: int) -> list[PairStats]:
    gathered: defaultdict[tuple[str, str], list[CutEntry]] = defaultdict(list)
    for result in results:
        for entry in result.entries:
            gathered[entry.canon].append(entry)
    stats: list[PairStats] = []
    for canon, group in gathered.items():
        gaps: list[float] = [entry.gap for entry in group]
        sigmas: list[float] = [entry.sigma_pair for entry in group]
        stats.append(
            PairStats(
                canon=canon,
                count=len(group),
                run_count=run_count,
                frequency=len(group) / run_count,
                mean_gap=sum(gaps) / len(gaps),
                mean_sigma=sum(sigmas) / len(sigmas),
                scc_ids=tuple(sorted({entry.scc_id for entry in group})),
                row_ids=tuple(sorted({entry.link.id for entry in group})),
                min_ts=min(entry.link.timestamp for entry in group),
            )
        )
    stats.sort(key=lambda stat: (-stat.frequency, -stat.mean_gap))
    return stats


def consensus_pairs(stats: list[PairStats], threshold: float) -> list[PairStats]:
    kept: list[PairStats] = [stat for stat in stats if stat.frequency >= threshold]
    kept.sort(key=lambda stat: (-stat.frequency, -stat.mean_gap))
    return kept


def verify_acyclic(graph: CutGraph, pairs: list[tuple[str, str]]) -> int:
    pair_set: set[tuple[str, str]] = set(pairs)
    residual: defaultdict[str, list[str]] = defaultdict(list)
    for winner, edges in graph.successors.items():
        residual[winner] = [
            m for m in edges if canonicalize_pair(winner, m) not in pair_set
        ]
    _, members = tarjan_scc(graph.all_filenames, residual)
    return len([m for m in members.values() if len(m) > 1])


def report_stats(stats: list[PairStats], run_count: int) -> None:
    for index, stat in enumerate(stats):
        logger.info(
            "pair %d/%d | cut %d/%d | %s -> %s | mean_gap=%+.3f | mean_sigma=%.3f | scc=%s | ids=%s | ts=%s",
            index + 1,
            len(stats),
            stat.count,
            run_count,
            stat.canon[0],
            stat.canon[1],
            stat.mean_gap,
            stat.mean_sigma,
            list(stat.scc_ids),
            list(stat.row_ids),
            stat.min_ts,
        )


def show_cut_grid(entries: list[CutEntry], show_top: int, tag: str) -> None:
    shown: list[CutEntry] = entries[:show_top] if show_top > 0 else entries
    if not shown:
        logger.warning("Nothing to display")
        return
    fig, axes = plt.subplots(
        len(shown), 2, figsize=(10, 4.8 * len(shown)), squeeze=False
    )
    for row_i, entry in enumerate(shown):
        link = entry.link
        winner_fn: str = link.winner
        loser_fn: str = link.loser
        header: str = (
            f"{tag} | cut {row_i + 1}/{len(entries)}\n"
            f"{winner_fn[:40]} -> {loser_fn[:40]}\n"
            f"gap={entry.gap:+.3f}  sigma={entry.sigma_pair:.3f}  id={link.id}  ts={link.timestamp}\n"
            f"SCC {entry.scc_id} (size {entry.scc_size})  cycle length {entry.cycle_length}"
        )
        for col, filename in enumerate((winner_fn, loser_fn)):
            side_label, side_color = (
                ("WINNER", "tab:green") if col == 0 else ("LOSER", "tab:red")
            )
            ax = axes[row_i][col]
            path = find_image_path(filename)
            if path is None:
                ax.text(
                    0.5,
                    0.5,
                    f"not found:\n{filename}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    wrap=True,
                )
            else:
                ax.imshow(mpimg.imread(path))
            title: str = f"{side_label}\n{filename}"
            if col == 0:
                title = f"{header}\n{title}"
            ax.set_title(title, fontsize=7.5, color=side_color)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_edgecolor(side_color)
                spine.set_linewidth(3)
    fig.tight_layout()
    fig.subplots_adjust(hspace=0.5, wspace=0.06)
    plt.show()


def show_pair_grid(
    graph: CutGraph, pairs: list[PairStats], show_top: int, tag: str
) -> None:
    shown: list[PairStats] = pairs[:show_top]
    if not shown:
        logger.warning("Nothing to display")
        return
    fig, axes = plt.subplots(
        len(shown), 2, figsize=(10, 4.8 * len(shown)), squeeze=False
    )
    for row_i, stat in enumerate(shown):
        link = graph.edge_to_comp.get((stat.canon[0], stat.canon[1])) or (
            graph.edge_to_comp.get((stat.canon[1], stat.canon[0]))
        )
        if link is None:
            continue
        winner_fn: str = link.winner
        loser_fn: str = link.loser
        header: str = (
            f"{tag} | pair {row_i + 1}/{len(pairs)}\n"
            f"{winner_fn[:40]} -> {loser_fn[:40]}\n"
            f"cut in {stat.count}/{stat.run_count} runs  mean_gap={stat.mean_gap:+.3f}  mean_sigma={stat.mean_sigma:.3f}\n"
            f"scc={list(stat.scc_ids)}  ids={list(stat.row_ids)}  ts={stat.min_ts}"
        )
        for col, filename in enumerate((winner_fn, loser_fn)):
            side_label, side_color = (
                ("WINNER", "tab:green") if col == 0 else ("LOSER", "tab:red")
            )
            ax = axes[row_i][col]
            path = find_image_path(filename)
            if path is None:
                ax.text(
                    0.5,
                    0.5,
                    f"not found:\n{filename}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    wrap=True,
                )
            else:
                ax.imshow(mpimg.imread(path))
            title: str = f"{side_label}\n{filename}"
            if col == 0:
                title = f"{header}\n{title}"
            ax.set_title(title, fontsize=7.5, color=side_color)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_edgecolor(side_color)
                spine.set_linewidth(3)
    fig.tight_layout()
    fig.subplots_adjust(hspace=0.5, wspace=0.06)
    plt.show()


def show_frequency_histogram(stats: list[PairStats], run_count: int) -> None:
    frequencies: list[float] = [stat.frequency for stat in stats]
    if not frequencies:
        logger.warning("No cuts recorded across runs")
        return
    figure, axis = plt.subplots(figsize=(9, 4))
    axis.hist(
        frequencies,
        bins=run_count,
        range=(0.0, 1.0),
        color="tab:blue",
        edgecolor="black",
    )
    axis.set_xlabel("fraction of runs in which the pair was cut")
    axis.set_ylabel("pairs (count)")
    axis.set_title(
        f"Cut frequency across {run_count} random replays ({len(stats)} distinct pairs)"
    )
    axis.grid(axis="y", linestyle=":", alpha=0.4)
    figure.tight_layout()
    plt.show()
