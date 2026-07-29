from typing import Any

from ....core.observability.logger import get_logger
from ....core.utilities.helpers import delete_full_vectors

logger = get_logger(__name__)


def run_split_vectors(limit: int = 0, batch: bool = False, **kwargs: Any) -> int:
    from ....application.data_transform.prepare_data import run_prepare
    logger.info("Building split vector files (limit=%s, batch=%s)...", limit, batch)
    result = run_prepare(limit=limit, batch=batch)
    logger.info("Split vectors done: %s", result)
    return 0


def run_full_vectors(**kwargs: Any) -> int:
    from ....application.data_transform.prepare_data import run_prepare
    logger.info("Building full vectors + text data from existing splits...")
    result = run_prepare(limit=0, batch=False)
    logger.info("Full vectors done: %s", result)
    return 0


def run_scores(**kwargs: Any) -> int:
    from ....application.data_transform.prepare_data import run_rebuild_scores_only
    logger.info("Building scores + comparisons...")
    result = run_rebuild_scores_only()
    logger.info("Scores done: %s", result)
    return 0


def run_all(limit: int = 0, batch: bool = False, **kwargs: Any) -> int:
    from ....application.data_transform.prepare_data import run_prepare
    logger.info("Running full build pipeline (limit=%s, batch=%s)...", limit, batch)
    result = run_prepare(limit=limit, batch=batch)
    logger.info("Full pipeline done: %s", result)
    return 0
