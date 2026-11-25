from pathlib import Path

import pytest

from comfyui_image_scorer.core.io.operations import read_json, write_json


def test_json_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "record.json"

    write_json(str(target), {"value": 3})

    assert target.is_file()
    assert read_json(str(target)) == {"value": 3}


def test_read_json_rejects_non_object(tmp_path: Path) -> None:
    target = tmp_path / "list.json"
    target.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object required"):
        read_json(str(target))
