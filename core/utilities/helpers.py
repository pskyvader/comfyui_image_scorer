import shutil
import time
from pathlib import Path

from ..observability.logger import get_logger, ModuleLogger
from ..filesystem.paths import (
    models_dir,
    split_dir,
    vectors_file,
    scores_file,
    comparisons_file,
    index_file,
    text_data_file,
)

logger: ModuleLogger = get_logger(__name__)


def remove_directory(directory_path: Path) -> None:
    _start = time.perf_counter()
    if directory_path.exists():
        logger.info(f"Removing {directory_path}")
        shutil.rmtree(directory_path)


def delete_full_vectors() -> None:
    """Delete the full vector files and all split categories except image/."""
    for path_str in [
        vectors_file, scores_file, index_file, text_data_file, comparisons_file,
    ]:
        p = Path(path_str)
        if p.exists():
            logger.info(f"Removing {p}")
            p.unlink()
    for split_path in Path(split_dir).iterdir():
        if split_path.name == "image":
            continue
        remove_directory(split_path)


def remove_models() -> None:
    _start = time.perf_counter()
    directory_path = Path(models_dir)
    remove_directory(directory_path)


def remove_derived_caches(*paths: str) -> None:
    """Delete only the named derived cache files. Each file is removed
    independently and missing files are skipped, so a prepare step can drop
    exactly the caches whose source inputs changed -- without wiping the whole
    models/ directory or touching caches that are still valid.
    """
    for p in paths:
        if Path(p).exists():
            Path(p).unlink()
            logger.debug(f"Removed stale cache: {p}")
