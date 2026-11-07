"""Phase ordering configuration.

The single source of truth for which phases exist, in which order they run,
and the metadata (labels, colors, descriptions, conditional flags) that
the frontend uses to render them.  Reorder the PHASES list to change the
execution order — the list index IS the phase number.
"""

from __future__ import annotations

import random
import time
from typing import NotRequired, TypedDict

from ....core.observability.logger import get_logger, ModuleLogger
from ....core.configuration.settings import config
from .pair_active import (
    phase_seed_coverage,
    phase_anchor_insert,
    phase_branch_probe,
    phase_collapsible_pairs,
    phase_chain_middle,
    phase_single_win_loss,
    phase_chain_merge,
    phase_uncertainty_refine,
    phase_fallback,
)
from ....domain.ports.graph import CrystalGraphPort
from ....domain.ports.repository import ImageRow

from ...comparison.algorithm.history_collapse import canonicalize_pair

from .graph_helpers import stable_seed_pool
from ...graph.node_proxy import NodeProxy

logger: ModuleLogger = get_logger(__name__)


class PhaseMetadata(TypedDict):
    phase_label: str
    color: str
    description: str
    show_chain_info: bool
    show_mu_sigma: bool
    show_wins_losses: NotRequired[bool]
    name: str


# Each entry contains the phase name and metadata consumed by the frontend.
PHASES: tuple[PhaseMetadata, ...] = (
    {
        "phase_label": "Phase 1 / Bootstrap Seed",
        "color": "#f87171",
        "description": "ensures seed images (top {seed_size} by comparisons) reach {seed_target} comparisons each, preferring cross-path opponents with similar scores",
        "show_chain_info": False,
        "show_mu_sigma": False,
        "name": "seed",
    },
    {
        "phase_label": "Phase 2 / Anchor Insert",
        "color": "#fb923c",
        "description": "integrates new images with \u2264{insertion_target} comparisons by pairing them with the closest mu (skill) from a different crystal path, preferring different components",
        "show_chain_info": False,
        "show_mu_sigma": False,
        "name": "anchor",
    },
    # {
    #     "phase_label": "Phase 3 / Branch Probe (Test)",
    #     "color": "#facc15",
    #     "description": "test branch-compatible opponent selection from a random anchor, using the closest score pair within the sigma range",
    #     "show_chain_info": True,
    #     "show_mu_sigma": False,
    #     "name": "branch_probe",
    # },
    {
        "phase_label": "Phase 4 / Collapsible",
        "color": "#4ade80",
        "description": "finds two tops or two bottoms in the same component not yet transitively connected; one click resolves ranking for entire branches",
        "show_chain_info": True,
        "show_mu_sigma": False,
        "name": "collapsible",
    },
    {
        "phase_label": "Phase 5 / Single Win-Loss",
        "color": "#22d3ee",
        "description": "compares images with exactly one win (highest score first) or exactly one loss (lowest score first), picking the closest-score adjacent pair until one image remains in each group",
        "show_chain_info": False,
        "show_mu_sigma": False,
        "show_wins_losses": True,
        "name": "single_win_loss",
    },
    {
        "phase_label": "Phase 6 / Chain Middle",
        "color": "#60a5fa",
        "description": "compares mid-chain nodes to resolve the global middle ordering",
        "show_chain_info": True,
        "show_mu_sigma": False,
        "show_wins_losses": True,
        "name": "chain_middle",
    },
    {
        "phase_label": "Phase 7 / Uncertainty Refine",
        "color": "#818cf8",
        "description": "reduces uncertainty by comparing images above \u03c3 \u2265 {sigma_threshold} against the closest-mu seed images",
        "show_chain_info": False,
        "show_mu_sigma": True,
        "name": "refine",
    },
    # {
    #     "phase_label": "Phase 8 / Chain Merge",
    #     "color": "#a78bfa",
    #     "description": "merges the longest chains by comparing internal mid-chain nodes, reducing the total number of chains",
    #     "show_chain_info": True,
    #     "show_mu_sigma": True,
    #     "name": "chain_merge",
    # },
    {
        "phase_label": "Fallback",
        "color": "#9ca3af",
        "description": "last-resort scan for any unseen pair when all heuristics fail",
        "show_chain_info": False,
        "show_mu_sigma": False,
        "name": "fallback",
    },
)


def get_phase_name(phase_index: int) -> str:
    """Return the phase name at a list index."""
    return PHASES[phase_index]["name"]


def get_phases() -> list[dict[str, object]]:
    """Return frontend phase metadata."""
    phases: list[dict[str, object]] = [dict(entry) for entry in PHASES]
    return phases


def select_pair(
    all_images: list[ImageRow],
    candidate_images: list[ImageRow],
    cg: CrystalGraphPort,
) -> tuple[tuple[str, str] | None, int | None]:
    _start: float = time.perf_counter()

    if len(candidate_images) < 2:
        logger.warning(
            "select_pair: only %d candidates, need >=2", len(candidate_images)
        )
        return None, None

    random.shuffle(candidate_images)

    candidate_nodes: list[NodeProxy] = [
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

    reserve_count: int = int(config["ranking"]["reserve_count"])
    total_comps: int = cg.get_link_count()

    if total_comps % reserve_count == 0:
        cg.reset_selection_state()

    skip_before: int = cg.get_skip_before()
    existing_pairs_set: set[tuple[str, str]] = set()
    existing_pairs_loaded: bool = False
    seed_pool: list[NodeProxy] = []
    seed_pool_loaded: bool = False
    seed_pool_set: set[str] = set()
    seed_pool_set_loaded: bool = False

    for idx in range(len(PHASES)):
        name: str = get_phase_name(idx)

        if skip_before > idx:
            continue

        if (
            name
            in (
                "seed",
                "anchor",
                "branch_probe",
                "single_win_loss",
                "chain_middle",
                "refine",
                "fallback",
            )
            and not existing_pairs_loaded
        ):
            existing_pairs_set = cg.get_existing_pairs()
            if len(existing_pairs_set) == 0:
                existing_pairs_set = {
                    canonicalize_pair(link.winner, link.loser)
                    for link in cg.get_all_links()
                }
                cg.set_existing_pairs(existing_pairs_set)
            logger.debug(
                f"existing pairs: {len(existing_pairs_set)}", start_timer=_start
            )
            existing_pairs_loaded = True

        if name in ("seed", "anchor", "refine") and not seed_pool_loaded:
            seed_pool = stable_seed_pool(
                [
                    node
                    for img in all_images
                    if (node := cg.get_node(img["filename"])) is not None
                ]
            )
            seed_pool_loaded = True

        if name in ("anchor", "refine") and not seed_pool_set_loaded:
            seed_pool_set = {node.filename for node in seed_pool}
            seed_pool_set_loaded = True

        if name == "seed":
            result: tuple[NodeProxy, NodeProxy] | None = phase_seed_coverage(
                candidate_nodes,
                existing_pairs_set,
                seed_pool,
                len(all_images),
            )
        elif name == "anchor":
            result = phase_anchor_insert(candidate_nodes, existing_pairs_set)
        elif name == "branch_probe":
            result = phase_branch_probe(candidate_nodes, existing_pairs_set)
        elif name == "collapsible":
            result = phase_collapsible_pairs(candidate_nodes, cg)
        elif name == "single_win_loss":
            result = phase_single_win_loss(candidate_nodes, existing_pairs_set)
        elif name == "chain_middle":
            result = phase_chain_middle(candidate_nodes, existing_pairs_set, cg)
        elif name == "refine":
            result = phase_uncertainty_refine(
                candidate_nodes, seed_pool_set, existing_pairs_set, cg
            )
        elif name == "chain_merge":
            result = phase_chain_merge(candidate_nodes, cg)
        elif name == "fallback":
            result = phase_fallback(candidate_nodes, existing_pairs_set)
        else:
            result = None

        if result:
            cg.set_skip_before(idx)
            selected_pair: tuple[str, str] = (
                result[0].filename,
                result[1].filename,
            )
            return selected_pair, idx

    logger.warning("No pair found after all phases")
    return None, None
