"""Phase ordering configuration.

The single source of truth for which phases exist, in which order they run,
and the metadata (labels, colors, descriptions, conditional flags) that
the frontend uses to render them.  Reorder the PHASES list to change the
execution order — the list index IS the phase number.
"""

from __future__ import annotations

import random
from typing import Any
import time


from ....core.observability.logger import get_logger, ModuleLogger
from ....core.configuration.settings import config
from .pair_active import (
    phase_seed_coverage,
    phase_anchor_insert,
    phase_collapsible_pairs,
    phase_single_win_loss,
    phase_chain_merge,
    phase_uncertainty_refine,
    phase_fallback,
)
from .graph_helpers import pair_key, stable_seed_pool
from ...graph.node_proxy import NodeProxy

logger: ModuleLogger = get_logger(__name__)


# Each entry is a dict whose first key is the phase name (mapping to its
# function).  Remaining keys are metadata consumed by the frontend.
PHASES: tuple[dict[str, Any], ...] = (
    {
        "seed": phase_seed_coverage,
        "phase_label": "Phase 1 / Bootstrap Seed",
        "color": "#f87171",
        "description": "ensures seed images (top {seed_size} by comparisons) reach {seed_target} comparisons each, preferring cross-path opponents with similar scores",
        "show_chain_info": False,
        "show_mu_sigma": False,
    },
    {
        "anchor": phase_anchor_insert,
        "phase_label": "Phase 2 / Anchor Insert",
        "color": "#facc15",
        "description": "integrates new images with \u2264{insertion_target} comparisons by pairing them with the closest mu (skill) from a different crystal path, preferring different components",
        "show_chain_info": False,
        "show_mu_sigma": False,
    },
    {
        "collapsible": phase_collapsible_pairs,
        "phase_label": "Phase 3 / Collapsible",
        "color": "#4ade80",
        "description": "finds two tops or two bottoms in the same component not yet transitively connected; one click resolves ranking for entire branches",
        "show_chain_info": True,
        "show_mu_sigma": False,
    },
    {
        "single_win_loss": phase_single_win_loss,
        "phase_label": "Phase 4 / Single Win-Loss",
        "color": "#22d3ee",
        "description": "compares images with exactly one win (highest score first) or exactly one loss (lowest score first), picking the closest-score adjacent pair until one image remains in each group",
        "show_chain_info": False,
        "show_mu_sigma": False,
        "show_wins_losses": True,
    },
    {
        "refine": phase_uncertainty_refine,
        "phase_label": "Phase 5 / Uncertainty Refine",
        "color": "#60a5fa",
        "description": "reduces uncertainty by comparing images above \u03c3 \u2265 {sigma_threshold} against the closest-mu seed images",
        "show_chain_info": False,
        "show_mu_sigma": True,
    },
    {
        "chain_merge": phase_chain_merge,
        "phase_label": "Phase 6 / Chain Merge",
        "color": "#a78bfa",
        "description": "merges the longest chains by comparing internal mid-chain nodes, reducing the total number of chains",
        "show_chain_info": True,
        "show_mu_sigma": True,
    },
    {
        "fallback": phase_fallback,
        "phase_label": "Fallback",
        "color": "#9ca3af",
        "description": "last-resort scan for any unseen pair when all heuristics fail",
        "show_chain_info": False,
        "show_mu_sigma": False,
    },
)


_skip_before: int = 0
_existing_pairs: set[tuple[str, str]] = set()


def reset_skip() -> None:
    global _skip_before, _existing_pairs
    _skip_before = 0
    _existing_pairs = set()


def get_phases() -> list[dict[str, Any]]:
    """Return a JSON-serializable version of PHASES (callables stripped).

    Each output dict includes the ``name`` key (derived from the callable
    key in the source entry) for the frontend to identify the phase.
    """
    result: list[dict[str, Any]] = []
    for entry in PHASES:
        cleaned: dict[str, Any] = {}
        name: str | None = None
        for k, v in entry.items():
            if callable(v):
                name = k
            else:
                cleaned[k] = v
        cleaned["name"] = name
        result.append(cleaned)
    return result


def select_pair(
    all_images: list[dict[str, Any]],
    candidate_images: list[dict[str, Any]],
    cg: Any,
    comparison_repo: Any,
) -> tuple[tuple[str, str] | None, int | None]:
    global _skip_before, _existing_pairs
    _start = time.perf_counter()

    if len(candidate_images) < 2:
        logger.warning(
            "select_pair: only %d candidates, need >=2", len(candidate_images)
        )
        return None, None

    if len(_existing_pairs) == 0:
        _existing_pairs = {
            pair_key(winner, loser) for winner, loser in cg.get_all_links()
        }
    existing_pairs_set: set[tuple[str, str]] = _existing_pairs
    logger.debug(f"existing pairs: {len(existing_pairs_set)}", start_timer=_start)

    random.shuffle(candidate_images)

    candidate_nodes = [
        node
        for img in candidate_images
        if (node := cg.get_node(img["filename"])) is not None
    ]
    if len(candidate_nodes) < 2:
        logger.warning(
            "select_pair: only %d candidates with graph nodes, need >=2",
            len(candidate_nodes),
        )
        return None, None

    seed_pool: list[NodeProxy] = stable_seed_pool(
        [
            node
            for img in all_images
            if (node := cg.get_node(img["filename"])) is not None
        ]
    )
    seed_pool_set: set[str] = {node.filename for node in seed_pool}

    reserve_count = int(config["ranking"]["reserve_count"])
    total_comps: int = comparison_repo.get_total_comparisons()

    if total_comps % reserve_count == 0:
        reset_skip()

    for idx, phase in enumerate(PHASES):
        name = next(k for k, v in phase.items() if callable(v))
        fn = phase[name]

        if _skip_before > idx:
            continue

        if name == "seed":
            result = fn(
                candidate_nodes,
                existing_pairs_set,
                seed_pool,
                len(all_images),
            )
        elif name == "anchor":
            result = fn(candidate_nodes, seed_pool_set, existing_pairs_set, cg)
        elif name == "collapsible":
            result = fn(candidate_nodes, cg, comparison_repo)
        elif name == "single_win_loss":
            result = fn(candidate_nodes, cg)
        elif name == "refine":
            result = fn(candidate_nodes, existing_pairs_set, cg)
        elif name == "chain_merge":
            result = fn(candidate_nodes, cg)
        elif name == "fallback":
            result = fn(candidate_nodes, existing_pairs_set)
        else:
            result = None

        if result:
            _skip_before = idx
            return (result[0].filename, result[1].filename), idx

    logger.warning("No pair found after all phases")
    return None, None
