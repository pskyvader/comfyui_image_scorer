"""Database maintenance commands: rebuild, sync, recalculate, cleanup."""

import time

from tqdm import tqdm
from ....core.configuration.settings import config
from ....core.observability.logger import get_logger
from ....domain.analysis.trueskill import replay_ratings, public_score_from_rating
from ....domain.ports.repository import RatingStateUpdate
from ..deps import CLIDeps

logger = get_logger(__name__)


def cleanup(deps: CLIDeps) -> int:
    _start = time.perf_counter()
    comp_result = deps.graph.clean_comparisons()
    logger.info(f"Comparisons cleaned: {comp_result}", start_timer=_start)

    deps.vacuum_database()

    return 0


def rebuild(deps: CLIDeps) -> int:
    _start = time.perf_counter()
    deps.processor.rebuild_database_from_ranked()
    logger.info("Database rebuilt from ranked files.", start_timer=_start)
    return 0


def sync(deps: CLIDeps) -> int:
    _start = time.perf_counter()
    deps.graph.rebuild_from_database()
    deps.processor.sync_ranked_files_from_database()
    logger.info("Ranked files synced from the database.", start_timer=_start)
    return 0


def recalculate(deps: CLIDeps) -> int:
    _start = time.perf_counter()
    if not deps.graph.reset_all_image_ratings(
        score=float(config["ranking"]["default_score"])
    ):
        logger.error("Failed to reset ratings")
        return 1
    deps.graph.rebuild_from_database()
    all_comparisons = [link.data for link in deps.graph.get_all_links()]
    logger.debug(
        f"Recalculating ratings from {len(all_comparisons)} comparisons",
        start_timer=_start,
    )
    replayed = replay_ratings(all_comparisons, order="default")
    logger.debug(f"Replayed ratings for {len(replayed)} images", start_timer=_start)
    rating_updates: list[RatingStateUpdate] = [
        (
            filename,
            public_score_from_rating(rating),
            rating.mu_skill,
            rating.sigma_uncertainty,
            count,
        )
        for filename, (rating, count) in replayed.items()
    ]
    updated = 0
    chunk_rows = int(config["prepare"]["database_bulk_chunk_rows"])
    for chunk_start in tqdm(
        range(0, len(rating_updates), chunk_rows),
        desc="Updating ratings",
        unit="chunk",
        delay=3.0,
    ):
        updated += deps.graph.update_image_rating_states_bulk(
            rating_updates[chunk_start : chunk_start + chunk_rows]
        )
    logger.info(f"Recalculated ratings for {updated} images", start_timer=_start)
    return 0
