"""Core utility analysis helpers (stateless functions).

These are generic helpers that do not depend on domain types and belong in
`core` as pure utilities.
"""

from __future__ import annotations

from typing import List, Tuple, Dict


def distribute(values: List[float], buckets: List[Tuple[str, float]]) -> Dict[str, int]:
    """Distribute values into named buckets by threshold.

    Kept simple and stateless so callers can use it from adapters without
    importing domain modules.
    """
    result: dict[str, int] = {}
    for label, _ in buckets:
        result[label] = 0
    for v in values:
        for label, threshold in buckets:
            if v < threshold:
                result[label] += 1
                break
        else:
            result[buckets[-1][0]] += 1
    return result
