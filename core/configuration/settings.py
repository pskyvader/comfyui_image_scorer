"""Validated configuration — read-only typed sections plus one explicit save API.

Root config.json maps section names to their JSON files. Every section parses
into a frozen pydantic model at first access; writes go exclusively through
``Config.set_root`` / ``Config.save_section`` which validate and persist.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ..io.serialization import load_json

PathLike = str | Path
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
CONFIG_FILE: Path = PROJECT_ROOT.joinpath("config", "config.json")
SUB_CONFIG_MAPPING: dict[str, str] = {
    "prepare": "prepare_config",
    "training": "training_config",
    "vector": "vector_config",
    "ranking": "ranking_config",
}


class SectionModel(BaseModel):
    """Base for section models: immutable, bracket-accessible, unknown-key tolerant."""

    model_config = ConfigDict(extra="allow", frozen=True)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


class PrepareSection(SectionModel):
    """prepare_config.json."""

    max_workers: int
    batch_size: int
    memory_usage: float


class RankingSection(SectionModel):
    """ranking_config.json."""

    subfolder_threshold: int
    lru_size: int
    max_workers: int
    default_score: float
    reserve_count: int
    parallel_requests: bool
    timeout_ms: int
    seed_percentage: int
    seed_target_comparisons: int
    insertion_target_comparisons: int
    score_steepness: float
    sigma_threshold: float


class TrainingSection(SectionModel):
    """training_config.json; HPO results (top1..N, used_keys) ride as extras."""

    random_state: int
    optimization_steps: int
    cycles: int
    max_combos: int
    device: str
    objective: str
    min_comparisons_threshold: int
    verbosity: int


class VectorSection(SectionModel):
    """vector_config.json; the vectors list rides as an extra."""


SECTION_MODELS: dict[str, type[SectionModel]] = {
    "prepare": PrepareSection,
    "ranking": RankingSection,
    "training": TrainingSection,
    "vector": VectorSection,
}


def _get_config_file(path: PathLike) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT.joinpath(p)
    return p


def _save_raw(data: dict[str, Any], path: PathLike) -> None:
    config_file = _get_config_file(path)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


class Config:
    """Read-only validated view over config.json with explicit persistence."""

    def __init__(self, config_file: PathLike) -> None:
        self._root_path: Path = _get_config_file(config_file)
        self._root_raw: dict[str, Any] = self._read_json(self._root_path)
        self._sections: dict[str, SectionModel] = {}
        self._section_raw: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        data, err = load_json(str(path), expect=dict)
        if err:
            raise RuntimeError(f"Malformed config file {path}: {err}")
        return data or {}

    def _section_file(self, section: str) -> Path:
        pointer = SUB_CONFIG_MAPPING[section]
        return _get_config_file(self._root_raw[pointer])

    def __getitem__(self, key: str) -> Any:
        if key == "image_root":
            return self._root_raw["image_root"]
        if key in SUB_CONFIG_MAPPING:
            if key not in self._sections:
                if key not in self._section_raw:
                    self._section_raw[key] = self._read_json(self._section_file(key))
                self._sections[key] = SECTION_MODELS[key].model_validate(
                    self._section_raw[key]
                )
            return self._sections[key]
        return self._root_raw[key]

    def set_root(self, key: str, value: Any) -> None:
        """Persist a root-level value (e.g. image_root bootstrap)."""
        self._root_raw[key] = value
        _save_raw(self._root_raw, self._root_path)

    def section_data(self, section: str) -> dict[str, Any]:
        """Raw copy of a section's data for read-modify-write via save_section."""
        if section not in self._section_raw:
            self._section_raw[section] = self._read_json(self._section_file(section))
        return json.loads(json.dumps(self._section_raw[section]))

    def save_section(self, section: str, data: dict[str, Any]) -> None:
        """Validate and persist a whole section, refreshing cached reads."""
        SECTION_MODELS[section].model_validate(data)
        self._section_raw[section] = data
        self._sections.pop(section, None)
        _save_raw(data, self._section_file(section))


config = Config(CONFIG_FILE)
