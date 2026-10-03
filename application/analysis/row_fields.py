"""Reading parameter values out of the text sidecar.

`VectorList.join_text_data` writes every column through `str()`, so the sidecar
holds numbers as strings (`"20"`) and one-hot parameter maps as Python repr
strings (`"{'euler_ancestral': 1.0}"`), which is not JSON. Each helper below
prefers the real type and falls back to parsing the stringified form, so the
analyzers keep working if the writer ever stops stringifying.

Parsing uses `ast.literal_eval`, which accepts only literals, so a malformed
cell degrades to `None` rather than executing anything.
"""

from __future__ import annotations

import ast
from typing import Any, cast


def as_number(value: Any) -> float | None:
    """Return a numeric parameter, or None when the cell is not one."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def as_weight_map(value: Any) -> dict[str, float]:
    """Return a one-hot parameter map, or an empty dict when there is none.

    Covers the sampler, scheduler, model and LoRA columns, which the writer
    stores as `{name: weight}` once stringified.
    """
    parsed = value
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return {}
    if not isinstance(parsed, dict):
        return {}
    raw_map = cast("dict[Any, Any]", parsed)
    return {
        str(key): float(weight)
        for key, weight in raw_map.items()
        if isinstance(weight, (int, float)) and not isinstance(weight, bool)
    }


def strongest(weights: dict[str, float]) -> tuple[str, float]:
    """Return the highest-weighted key of a one-hot map, defaulting to empty."""
    if not weights:
        return "", 0.0
    name = max(weights.items(), key=lambda item: item[1])
    return name


def as_pairs(weights: dict[str, float]) -> list[tuple[str, float]]:
    """Convert a one-hot map into the pair form the matrix analyzer reads."""
    return [(name, weight) for name, weight in weights.items() if name]