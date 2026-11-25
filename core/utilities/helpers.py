from pathlib import Path

from ..filesystem.operations import DeletionMode, delete_directory, delete_file
from ..filesystem.paths import (
    split_dir,
    vectors_file,
    scores_file,
    comparisons_file,
    index_file,
    text_data_file,
)
from ..observability.logger import get_logger, ModuleLogger

logger: ModuleLogger = get_logger(__name__)


def delete_full_vectors() -> None:
    """Delete the full vector files and all split categories except image/."""
    delete_file(
        [
            Path(path)
            for path in (
                vectors_file,
                scores_file,
                index_file,
                text_data_file,
                comparisons_file,
            )
        ],
        mode=DeletionMode.PERMANENT,
    )
    for split_path in Path(split_dir).iterdir():
        if split_path.name == "image":
            continue
        delete_directory(split_path, mode=DeletionMode.PERMANENT)


def remove_derived_caches(*paths: str) -> None:
    """Delete only the named derived cache files. Each file is removed
    independently and missing files are skipped, so a prepare step can drop
    exactly the caches whose source inputs changed -- without wiping the whole
    models/ directory or touching caches that are still valid.
    """
    stale = [Path(path) for path in paths if Path(path).exists()]
    delete_file(stale, mode=DeletionMode.PERMANENT)
    for path in stale:
        logger.debug(f"Removed stale cache: {path}")
