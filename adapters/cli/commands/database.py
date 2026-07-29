from typing import Any

from ....core.observability.logger import get_logger

logger = get_logger(__name__)


def cleanup(**kwargs: Any) -> int:
    from ....infrastructure.persistence.comparisons_repository import clean_comparisons
    from ....infrastructure.persistence.database import vacuum_database

    comp_result = clean_comparisons()
    logger.info("Comparisons cleaned: %s", comp_result)

    vacuum_database()

    return comp_result


def rebuild(**kwargs: Any) -> int:
    from ...server.processor import ImageProcessor
    from ....core.configuration.settings import config

    processor = ImageProcessor(max_workers=int(config["ranking"]["max_workers"]))
    processor.rebuild_database_from_ranked()
    logger.info("Database rebuilt from ranked files.")
    return 0


def recalculate(**kwargs: Any) -> int:
    from ....infrastructure.persistence.images_repository import (
        reset_all_image_ratings, get_all_images,
    )
    from ....infrastructure.persistence.comparisons_repository import get_all_comparisons
    from ....domain.comparison.comparison_recorder import (
        update_scores_after_comparison,
    )
    from ....infrastructure.persistence.images_repository import update_image_rating_state
    from ....core.configuration.settings import config

    if not reset_all_image_ratings(score=float(config["ranking"]["default_score"])):
        logger.error("Failed to reset ratings")
        return 1

    all_comparisons = get_all_comparisons()
    all_images_map = {img["filename"]: img for img in get_all_images()}

    from ....domain.analysis.trueskill import replay_ratings
    replayed = replay_ratings(all_comparisons)

    updated = 0
    for filename, (rating, count) in replayed.items():
        from ....domain.analysis.trueskill import public_score_from_rating
        if update_image_rating_state(
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



