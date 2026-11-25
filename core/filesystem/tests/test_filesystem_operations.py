from pathlib import Path

import pytest

from comfyui_image_scorer.core.filesystem.operations import (
    DeletionMode,
    delete_directory,
    delete_file,
    file_exists,
    list_directory,
    make_directory,
    move_file,
)


def test_path_helpers_round_trip(tmp_path: Path) -> None:
    make_directory(str(tmp_path / "nested"))
    source = tmp_path / "nested" / "a.json"
    source.write_text("{}", encoding="utf-8")
    dest = tmp_path / "moved" / "a.json"

    assert file_exists(str(source))
    assert list_directory(str(source.parent)) == ["a.json"]
    assert move_file(source, dest)
    assert not source.exists()
    assert dest.is_file()
    assert not move_file(source, dest.parent / "missing.json")


def test_delete_file_permanent_single_and_list(tmp_path: Path) -> None:
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")

    delete_file(first, mode=DeletionMode.PERMANENT)
    delete_file([first, second], mode=DeletionMode.PERMANENT)

    assert not first.exists()
    assert not second.exists()


def test_delete_file_trash_delegates_without_unlinking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Path] = []
    monkeypatch.setattr(
        "comfyui_image_scorer.core.filesystem.operations.send2trash", calls.append
    )
    target = tmp_path / "a.txt"
    target.write_text("a", encoding="utf-8")

    delete_file(target, mode=DeletionMode.TRASH)

    assert calls == [target]
    assert target.is_file()


def test_delete_directory_permanent(tmp_path: Path) -> None:
    folder = tmp_path / "dir"
    child = folder / "child.txt"
    child.parent.mkdir()
    child.write_text("x", encoding="utf-8")

    delete_directory(folder, mode=DeletionMode.PERMANENT)

    assert not folder.exists()


def test_delete_directory_trash_delegates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Path] = []
    monkeypatch.setattr(
        "comfyui_image_scorer.core.filesystem.operations.send2trash", calls.append
    )
    folder = tmp_path / "dir"
    folder.mkdir()

    delete_directory(folder, mode=DeletionMode.TRASH)

    assert calls == [folder]
    assert folder.is_dir()


def test_delete_file_rejects_directory(tmp_path: Path) -> None:
    folder = tmp_path / "dir"
    folder.mkdir()

    with pytest.raises(ValueError, match="delete_directory"):
        delete_file(folder, mode=DeletionMode.PERMANENT)


def test_delete_skips_missing_paths(tmp_path: Path) -> None:
    delete_file(tmp_path / "missing.txt", mode=DeletionMode.PERMANENT)
    delete_directory(tmp_path / "missing_dir", mode=DeletionMode.PERMANENT)
