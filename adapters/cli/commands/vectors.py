from ....application.data_transform.prepare_data import (
    build_full_files,
    build_split_files,
    run_rebuild_scores_only,
)
from ....core.observability.logger import get_logger, ModuleLogger
from ....core.filesystem.paths import (
    vectors_data,
    scores_data,
    feature_rule,
    comparison_rule,
    training_model,
    vectors_file,
    text_data_file,
    index_file,
)
from ....core.utilities.helpers import remove_derived_caches
from ..deps import CLIDeps

logger: ModuleLogger = get_logger(__name__)


def run_split_vectors(limit: int, batch: bool, deps: CLIDeps) -> int:
    logger.info("Building split vector files (limit=%s, batch=%s)...", limit, batch)
    changed = False
    if limit > 0 and batch:
        logger.info("batch process enabled")
        step = 0
        while True:
            logger.info(f"step: {step}")
            logger.info("-" * 100)
            summary = build_split_files(
                limit=limit,
                model_loader=deps.model_loader,
                batch_sizer_factory=deps.batch_sizer_factory,
                maps_provider=deps.maps_provider,
            )
            if int(summary["new"]) == 0:
                break
            step += 1
            changed = True
    else:
        summary = build_split_files(
            limit=limit,
            model_loader=deps.model_loader,
            batch_sizer_factory=deps.batch_sizer_factory,
            maps_provider=deps.maps_provider,
        )
        changed = int(summary["new"]) > 0

    if changed:
        logger.info(
            "New split files written; full vectors and text data are stale "
            "and were removed. Run the full-build step to rebuild them; "
            "scores and comparisons are kept."
        )
        remove_derived_caches(
            vectors_file,
            text_data_file,
            index_file,
            vectors_data,
            scores_data,
            feature_rule,
            comparison_rule,
            training_model,
        )
    else:
        logger.info("Prepare found no new images; no split files written, no caches removed.")
    return 0


def run_full_vectors(deps: CLIDeps) -> int:
    logger.info("Building full vectors + text data from existing splits...")
    result = build_full_files(
        model_loader=deps.model_loader,
        batch_sizer_factory=deps.batch_sizer_factory,
        maps_provider=deps.maps_provider,
    )
    logger.info("Full vectors done: %s", result)
    return 0


def run_scores(deps: CLIDeps) -> int:
    logger.info("Building scores + comparisons...")
    result = run_rebuild_scores_only(comparison_repo=deps.comparison_repo)
    logger.info("Scores done: %s", result)
    return 0


def run_all(limit: int, batch: bool, deps: CLIDeps) -> int:
    logger.info("Running full build pipeline (limit=%s, batch=%s)...", limit, batch)
    run_split_vectors(limit=limit, batch=batch, deps=deps)
    run_full_vectors(deps=deps)
    run_scores(deps=deps)
    logger.info("Full pipeline done.")
    return 0
