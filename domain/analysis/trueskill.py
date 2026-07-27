from __future__ import annotations

from dataclasses import dataclass
from math import erf, exp, pi, sqrt

from comfyui_image_scorer.core.configuration.settings import config

INITIAL_MEAN = 25.0
INITIAL_UNCERTAINTY = INITIAL_MEAN / 3.0
PERFORMANCE_VARIATION = INITIAL_MEAN / 6.0
DYNAMICS_NOISE = INITIAL_MEAN / 300.0
EPSILON = 1e-9
SCORE_STEEPNESS: float = float(config["ranking"]["score_steepness"])


@dataclass(frozen=True)
class Rating:
    mu_skill: float = INITIAL_MEAN
    sigma_uncertainty: float = INITIAL_UNCERTAINTY


def normal_cumulative_distribution(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _clamp_uncertainty(uncertainty: float) -> float:
    return max(uncertainty, EPSILON)


def expected_win_probability(first_rating: Rating, second_rating: Rating) -> float:
    denominator = sqrt(
        (2.0 * (PERFORMANCE_VARIATION**2))
        + (_clamp_uncertainty(first_rating.sigma_uncertainty) ** 2)
        + (_clamp_uncertainty(second_rating.sigma_uncertainty) ** 2)
    )
    return normal_cumulative_distribution(
        SCORE_STEEPNESS * (first_rating.mu_skill - second_rating.mu_skill)
        / max(denominator, EPSILON)
    )


def public_score_from_rating(rating: Rating) -> float:
    return expected_win_probability(
        rating, Rating(mu_skill=INITIAL_MEAN, sigma_uncertainty=INITIAL_UNCERTAINTY)
    )


def normal_probability_density(x: float) -> float:
    return exp(-(x * x) / 2.0) / sqrt(2.0 * pi)


def _add_dynamics_noise(uncertainty: float) -> float:
    return sqrt((max(uncertainty, EPSILON) ** 2) + (DYNAMICS_NOISE**2))


def update_ratings(winner: Rating, loser: Rating) -> tuple[Rating, Rating]:
    winner_uncertainty = _add_dynamics_noise(winner.sigma_uncertainty)
    loser_uncertainty = _add_dynamics_noise(loser.sigma_uncertainty)

    combined_variance = (
        (2.0 * (PERFORMANCE_VARIATION**2))
        + (winner_uncertainty**2)
        + (loser_uncertainty**2)
    )
    combined_deviation = sqrt(max(combined_variance, EPSILON))

    mean_difference = winner.mu_skill - loser.mu_skill
    normalised_difference = mean_difference / combined_deviation

    cumulative_probability = normal_cumulative_distribution(normalised_difference)
    skill_adjustment_weight = (
        normal_probability_density(normalised_difference) / cumulative_probability
    )
    variance_adjustment_weight = skill_adjustment_weight * (
        skill_adjustment_weight + normalised_difference
    )

    winner_variance = winner_uncertainty**2
    loser_variance = loser_uncertainty**2

    winner_new_mean = (
        winner.mu_skill + (winner_variance / combined_deviation) * skill_adjustment_weight
    )
    loser_new_mean = (
        loser.mu_skill - (loser_variance / combined_deviation) * skill_adjustment_weight
    )

    winner_new_variance = winner_variance * max(
        1.0 - (winner_variance / combined_variance) * variance_adjustment_weight,
        EPSILON,
    )
    loser_new_variance = loser_variance * max(
        1.0 - (loser_variance / combined_variance) * variance_adjustment_weight,
        EPSILON,
    )

    return (
        Rating(mu_skill=winner_new_mean, sigma_uncertainty=sqrt(winner_new_variance)),
        Rating(mu_skill=loser_new_mean, sigma_uncertainty=sqrt(loser_new_variance)),
    )


def replay_ratings(rows: list[dict]) -> dict[str, tuple[Rating, int]]:
    ordered = sorted(rows, key=lambda r: int(r.get("id", 0) or 0))
    ratings: dict[str, Rating] = {}
    counts: dict[str, int] = {}

    for row in ordered:
        left = str(row["filename_a"])
        right = str(row["filename_b"])
        winner = str(row["winner"])
        if winner not in (left, right):
            continue
        loser = right if winner == left else left

        winner_rating = ratings.get(winner, Rating())
        loser_rating = ratings.get(loser, Rating())
        ratings[winner], ratings[loser] = update_ratings(winner_rating, loser_rating)
        counts[winner] = counts.get(winner, 0) + 1
        counts[loser] = counts.get(loser, 0) + 1

    return {fid: (rating, counts.get(fid, 0)) for fid, rating in ratings.items()}


def rating_from_row(row: dict) -> Rating:
    return Rating(
        mu_skill=float(row["rating_mu"]),
        sigma_uncertainty=float(row["rating_sigma"]),
    )
