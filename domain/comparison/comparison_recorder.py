"""Comparison recording and rating updates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import time

from comfyui_image_scorer.core.observability.logger import get_logger, ModuleLogger
from comfyui_image_scorer.domain.comparison.state import invalidate_images_cache
from comfyui_image_scorer.domain.analysis.trueskill import (
    Rating,
    public_score_from_rating,
    rating_from_row,
    update_ratings,
)
logger: ModuleLogger = get_logger(__name__)


def update_scores_after_comparison(
    winner_filename: str,
    loser_filename: str,
    winner_data: dict[str, Any],
    loser_data: dict[str, Any],
    impact_factor: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
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
