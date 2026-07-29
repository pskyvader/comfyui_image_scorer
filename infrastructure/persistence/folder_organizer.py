"""Folder organizer - maintain score folder structure."""

import time

from ...core.observability.logger import get_logger, ModuleLogger
from .path_handler import get_ranked_root

logger: ModuleLogger = get_logger(__name__)


def ensure_tier_structure() -> bool:
    """Ensure score folders exist (scored_0.0 through scored_1.0).

    Called once during initialization. Returns True if successful.
    """
    _start = time.perf_counter()
    try:
        ranked_root = get_ranked_root()
        ranked_root.mkdir(parents=True, exist_ok=True)

        for i in range(11):
            score = i / 10.0
            score_folder = ranked_root / f"scored_{score:.1f}"
            score_folder.mkdir(parents=True, exist_ok=True)

        return True
    except Exception as e:
        logger.error(f"Error creating score structure: {e}")
        return False
