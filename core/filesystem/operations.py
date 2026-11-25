import shutil
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path

from send2trash import send2trash
from tqdm import tqdm


class DeletionMode(StrEnum):
    PERMANENT = "permanent"
    TRASH = "trash"


def file_exists(path: str) -> bool:
    return Path(path).is_file()


def list_directory(path: str) -> list[str]:
    return [entry.name for entry in Path(path).iterdir() if entry.is_file()]


def make_directory(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def move_file(src: Path, dst: Path) -> bool:
    if not src.exists():
        return dst.exists()
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.replace(dst)
    return True


def _as_paths(paths: Path | Iterable[Path]) -> tuple[Path, ...]:
    return (paths,) if isinstance(paths, Path) else tuple(paths)


def delete_file(paths: Path | Iterable[Path], *, mode: DeletionMode) -> None:
    for path in tqdm(
        _as_paths(paths),
        desc="Deleting files",
        unit="file",
        delay=3.0,
        leave=False,
    ):
        if not path.exists():
            continue
        if path.is_dir() and not path.is_symlink():
            raise ValueError(f"Use delete_directory for {path}")
        if mode is DeletionMode.TRASH:
            send2trash(path)
        else:
            path.unlink()


def delete_directory(paths: Path | Iterable[Path], *, mode: DeletionMode) -> None:
    for path in tqdm(
        _as_paths(paths),
        desc="Deleting directories",
        unit="dir",
        delay=3.0,
        leave=False,
    ):
        if not path.exists():
            continue
        if mode is DeletionMode.TRASH:
            send2trash(path)
        else:
            shutil.rmtree(path)
