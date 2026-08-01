from typing import Any

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

logger: ModuleLogger = get_logger(__name__)


def run_split_vectors(limit: int = 0, batch: bool = False) -> int:
    from ....application.data_transform.prepare_data import build_split_files

    logger.info("Building split vector files (limit=%s, batch=%s)...", limit, batch)
    changed = False
    if limit > 0 and batch:
        logger.info("batch process enabled")
        step = 0
        while True:
            logger.info(f"step: {step}")
            logger.info("-" * 100)
            summary = build_split_files(limit=limit)
            if int(summary["new"]) == 0:
                break
            step += 1
            changed = True
    else:
        summary = build_split_files(limit=limit)
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
        logger.info(
            "Prepare found no new images; no split files written, no " "caches removed."
        )
    return 0


def run_full_vectors(**kwargs: Any) -> int:
    from ....application.data_transform.prepare_data import build_full_files

    logger.info("Building full vectors + text data from existing splits...")
    result = build_full_files()
    logger.info("Full vectors done: %s", result)
    return 0


def run_scores(**kwargs: Any) -> int:
    from ....application.data_transform.prepare_data import run_rebuild_scores_only

    logger.info("Building scores + comparisons...")
    result = run_rebuild_scores_only()
    logger.info("Scores done: %s", result)
    return 0


def run_all(limit: int = 0, batch: bool = False, **kwargs: Any) -> int:
    logger.info("Running full build pipeline (limit=%s, batch=%s)...", limit, batch)
    run_split_vectors(limit=limit, batch=batch)
    run_full_vectors()
    run_scores()
    logger.info("Full pipeline done.")
    return 0
