"""Database maintenance commands: rebuild, recalculate, cleanup."""
from ....core.configuration.settings import config
from ....core.observability.logger import get_logger
from ....domain.analysis.trueskill import replay_ratings, public_score_from_rating
from ..deps import CLIDeps

logger = get_logger(__name__)


def cleanup(deps: CLIDeps) -> int:
    comp_result = deps.graph.clean_comparisons()
    logger.info("Comparisons cleaned: %s", comp_result)

    deps.vacuum_database()

    return comp_result


def rebuild(deps: CLIDeps) -> int:
    deps.processor.rebuild_database_from_ranked()
    logger.info("Database rebuilt from ranked files.")
    return 0


def recalculate(deps: CLIDeps) -> int:
    if not deps.graph.reset_all_image_ratings(
        score=float(config["ranking"]["default_score"])
    ):
        logger.error("Failed to reset ratings")
        return 1

    all_comparisons = [link.data for link in deps.graph.get_all_links()]

    replayed = replay_ratings(all_comparisons)

    updated = 0
    for filename, (rating, count) in replayed.items():
        if deps.graph.update_image_rating_state(
            filename=filename,
            score=public_score_from_rating(rating),
            rating_mu=rating.mu_skill,
            rating_sigma=rating.sigma_uncertainty,
            comparison_count=count,
            touch_timestamp=False,
        ):
            updated += 1

    logger.info("Recalculated ratings for %s images", updated)
    return 0
