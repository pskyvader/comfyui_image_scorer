"""Comparison recording and rating updates."""

from __future__ import annotations

from ...core.observability.logger import get_logger
from datetime import datetime, timezone

from ..analysis.trueskill import (
    public_score_from_rating,
    rating_from_row,
    update_ratings,
)
from ..graph.link_proxy import LinkProxy
from ..graph.node_proxy import NodeProxy

logger: ModuleLogger = get_logger(__name__)


def update_scores_after_comparison(
    winner_data: dict[str, object],
    loser_data: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    winner_rating, loser_rating = update_ratings(
        rating_from_row(winner_data), rating_from_row(loser_data)
    )
    winner_data = dict(winner_data)
    loser_data = dict(loser_data)
    winner_data["rating_mu"] = winner_rating.mu_skill
    winner_data["rating_sigma"] = winner_rating.sigma_uncertainty
    winner_data["score"] = public_score_from_rating(winner_rating)
    winner_data["comparison_count"] = int(winner_data["comparison_count"]) + 1
    loser_data["rating_mu"] = loser_rating.mu_skill
    loser_data["rating_sigma"] = loser_rating.sigma_uncertainty
    loser_data["score"] = public_score_from_rating(loser_rating)
    loser_data["comparison_count"] = int(loser_data["comparison_count"]) + 1
    return winner_data, loser_data


class ComparisonRecorder:
    def __init__(
        self,
        path_syncer: PathResolver,
        graph_service: GraphService,
    ) -> None:
        self._path_syncer = path_syncer
        self._graph = graph_service

    def _persist_image_state(self, filename: str, data: dict[str, object]) -> bool:
        return self._graph.update_image_rating_state(
            filename=filename,
            score=float(data["score"]),
            rating_mu=float(data["rating_mu"]),
            rating_sigma=float(data["rating_sigma"]),
            comparison_count=int(data["comparison_count"]),
            touch_timestamp=True,
        )

    def record_comparison(
        self,
        filename_a: str,
        filename_b: str,
        winner: str,
    ) -> bool:
        """Record one direct comparison and update both image ratings."""
        if self._graph.comparison_exists_for_pair(filename_a, filename_b):
            logger.warning(
                "duplicate pair comparison for %s vs %s. remember to clean up later",
                filename_a,
                filename_b,
            )

        node_a = self._graph.get_node(filename_a)
        node_b = self._graph.get_node(filename_b)
        data_a = node_a.data if node_a is not None else None
        data_b = node_b.data if node_b is not None else None
        if not data_a or not data_b or filename_a == filename_b:
            return False

        if winner == filename_a:
            winner_filename, loser_filename = filename_a, filename_b
            winner_data, loser_data = data_a, data_b
        else:
            winner_filename, loser_filename = filename_b, filename_a
            winner_data, loser_data = data_b, data_a

        winner_data, loser_data = update_scores_after_comparison(
            winner_data, loser_data
        )

        ts = datetime.now(timezone.utc).isoformat()
        comp_id = self._graph.add_link(
            filename_a=filename_a,
            filename_b=filename_b,
            winner=winner,
            timestamp=ts,
        )
        if not comp_id:
            logger.error(
                "Failed to insert comparison into DB: %s vs %s, winner=%s",
                filename_a,
                filename_b,
                winner,
            )
            return False

        if not self._persist_image_state(winner_filename, winner_data):
            return False
        if not self._persist_image_state(loser_filename, loser_data):
            return False

        all_comparisons = [link.data for link in self._graph.get_all_links()]
        saved_winner = self._path_syncer.sync_image_metadata_to_json(
            filename=winner_filename,
            score=float(winner_data["score"]),
            rating_mu=float(winner_data["rating_mu"]),
            rating_sigma=float(winner_data["rating_sigma"]),
            comparison_count=int(winner_data["comparison_count"]),
            all_comparisons=all_comparisons,
        )
        saved_loser = self._path_syncer.sync_image_metadata_to_json(
            filename=loser_filename,
            score=float(loser_data["score"]),
            rating_mu=float(loser_data["rating_mu"]),
            rating_sigma=float(loser_data["rating_sigma"]),
            comparison_count=int(loser_data["comparison_count"]),
            all_comparisons=all_comparisons,
        )
        if not saved_winner or not saved_loser:
            logger.error(
                "Failed to sync JSON history for comparison %s (%s vs %s)",
                comp_id,
                winner_filename,
                loser_filename,
            )
            return False

        return True
