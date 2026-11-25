"""Phase ordering configuration.

The single source of truth for which phases exist, in which order they run,
and the metadata (labels, colors, descriptions, conditional flags) that
the frontend uses to render them.  Reorder the PHASES list to change the
execution order — the list index IS the phase number.
"""

from __future__ import annotations

import random
import time
from typing import NotRequired, TypedDict, cast

from ....core.observability.logger import get_logger, ModuleLogger
from ....core.configuration.settings import config
from .pair_active import (
    phase_seed_coverage,
    phase_anchor_insert,
    phase_exact_count_pair,
    phase_chain_middle,
    phase_uncertainty_refine,
    phase_chain_small,
    phase_fallback,
)
from .history_collapse import canonicalize_pair
from .graph_helpers import stable_seed_pool
from ....domain.ports.graph import CrystalGraphPort
from ....domain.ports.repository import ImageRow
from ....domain.ports.comparison import PairingProcessorPort
from ...graph.node_proxy import NodeProxy

logger: ModuleLogger = get_logger(__name__)


class PhaseMetadata(TypedDict):
    phase_label: str
    color: str
    description: str
    show_chain_info: bool
    show_mu_sigma: bool
    show_wins_losses: NotRequired[bool]
    bottom: NotRequired[bool]
    count: NotRequired[int]
    closest: NotRequired[bool]
    name: str


class CountPhaseMetadata(TypedDict):
    """Count-family entry; the exact-count flags are required here."""

    phase_label: str
    color: str
    description: str
    show_chain_info: bool
    show_mu_sigma: bool
    show_wins_losses: bool
    bottom: bool
    count: int
    closest: bool
    name: str


# Each entry contains the phase name and metadata consumed by the frontend.
PHASES: tuple[PhaseMetadata | CountPhaseMetadata, ...] = (
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
    {
        "phase_label": "Phase 3 / Only Losers",
        "color": "#facc15",
        "description": "pairs two images that never won a comparison, picking the closest-score pair inside the sigma range",
        "show_chain_info": True,
        "show_mu_sigma": False,
        "show_wins_losses": True,
        "bottom": True,
        "count": 0,
        "closest": True,
        "name": "only_losers",
    },
    {
        "phase_label": "Phase 4 / Only Winners",
        "color": "#4ade80",
        "description": "pairs two images that never lost a comparison, picking the closest-score pair inside the sigma range",
        "show_chain_info": True,
        "show_mu_sigma": False,
        "show_wins_losses": True,
        "bottom": False,
        "count": 0,
        "closest": True,
        "name": "only_winners",
    },
    # {
    #     "phase_label": "Phase 5 / Mostly Losers",
    #     "color": "#22d3ee",
    #     "description": "compares images with exactly one win against their many losses, picking the widest score gap inside the sigma range",
    #     "show_chain_info": False,
    #     "show_mu_sigma": False,
    #     "show_wins_losses": True,
    #     "bottom": True,
    #     "count": 1,
    #     "closest": True,
    #     "name": "mostly_losers",
    # },
    # {
    #     "phase_label": "Phase 6 / Mostly Winners",
    #     "color": "#60a5fa",
    #     "description": "compares images with exactly one loss against their many wins, picking the widest score gap inside the sigma range",
    #     "show_chain_info": False,
    #     "show_mu_sigma": False,
    #     "show_wins_losses": True,
    #     "bottom": False,
    #     "count": 1,
    #     "closest": True,
    #     "name": "mostly_winners",
    # },
    {
        "phase_label": "Phase 7 / Chain Middle",
        "color": "#c084fc",
        "description": "keeps only images that could still be the middle: neither the pile proven better nor the pile proven worse has passed half the set. Each vote uses an image about to be ruled out, so every result eliminates someone for good and the countdown only goes down until one image is left",
        "show_chain_info": True,
        "show_mu_sigma": False,
        "show_wins_losses": True,
        "name": "chain_middle",
    },
    {
        "phase_label": "Phase 8 / Uncertainty Refine",
        "color": "#a78bfa",
        "description": "reduces uncertainty by comparing images above \u03c3 \u2265 {sigma_threshold} against the closest-mu seed images",
        "show_chain_info": False,
        "show_mu_sigma": True,
        "name": "refine",
    },
    {
        "phase_label": "Phase 9 / Chain Small",
        "color": "#818cf8",
        "description": "pairs extreme nodes of small main chains with long-chain members so every chain grows past the length threshold",
        "show_chain_info": True,
        "show_mu_sigma": False,
        "show_wins_losses": True,
        "name": "chain_small",
    },
    {
        "phase_label": "Fallback",
        "color": "#9ca3af",
        "description": "last-resort scan for any unseen pair when all heuristics fail",
        "show_chain_info": False,
        "show_mu_sigma": False,
        "name": "fallback",
    },
)

COUNT_FAMILY_PHASES: tuple[str, ...] = (
    "only_losers",
    "only_winners",
    "mostly_losers",
    "mostly_winners",
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
    pairing_processor: PairingProcessorPort,
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
    existing_pairs_set: set[tuple[str, str]] = cg.get_existing_pairs()
    if len(existing_pairs_set) == 0:
        existing_pairs_set = {
            canonicalize_pair(link.winner, link.loser) for link in cg.get_all_links()
        }
        cg.set_existing_pairs(existing_pairs_set)
    logger.debug(f"existing pairs: {len(existing_pairs_set)}", start_timer=_start)

    seed_pool: list[NodeProxy] = []
    seed_pool_loaded: bool = False
    seed_pool_set: set[str] = set()
    seed_pool_set_loaded: bool = False

    for idx in range(len(PHASES)):
        name: str = get_phase_name(idx)

        if skip_before > idx:
            continue

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
                cg,
            )
        elif name == "anchor":
            result = phase_anchor_insert(
                candidate_nodes, existing_pairs_set, pairing_processor, cg
            )
        elif name in COUNT_FAMILY_PHASES:
            count_entry: CountPhaseMetadata = cast(CountPhaseMetadata, PHASES[idx])
            result = phase_exact_count_pair(
                candidate_nodes,
                existing_pairs_set,
                pairing_processor,
                cg,
                bottom=count_entry["bottom"],
                count=count_entry["count"],
                closest=count_entry["closest"],
            )
        elif name == "chain_middle":
            result = phase_chain_middle(
                candidate_nodes, existing_pairs_set, cg, pairing_processor
            )
        elif name == "refine":
            result = phase_uncertainty_refine(
                candidate_nodes,
                seed_pool_set,
                existing_pairs_set,
                cg,
                pairing_processor,
            )
        elif name == "chain_small":
            result = phase_chain_small(
                candidate_nodes, existing_pairs_set, cg, pairing_processor
            )
        elif name == "fallback":
            result = phase_fallback(candidate_nodes, existing_pairs_set, cg)
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
