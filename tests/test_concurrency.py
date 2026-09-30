"""parallel_for must return results in input order, not completion order.

Callers persist and aggregate these results, so completion order would make
every rebuild produce a different order and therefore different float results.
"""

from __future__ import annotations

import time

from comfyui_image_scorer.core.utilities.concurrency import parallel_for


def _jittery(index: int) -> int:
    # finish in reverse order of the input so completion order differs from
    # input order every time
    time.sleep((17 - index % 17) / 1000.0)
    return index * 10


def test_unbatched_results_keep_input_order() -> None:
    items = [(i,) for i in range(40)]
    for _ in range(3):
        assert parallel_for(_jittery, items, max_workers=8, desc="t") == [
            i * 10 for i in range(40)
        ]


def test_batched_results_keep_input_order() -> None:
    items = [(i,) for i in range(40)]
    for _ in range(3):
        assert parallel_for(
            _jittery, items, max_workers=8, batch_size=6, desc="t"
        ) == [i * 10 for i in range(40)]


def test_uneven_final_batch_keeps_input_order() -> None:
    # 23 items with batch_size 5 leaves a short trailing batch
    items = [(i,) for i in range(23)]
    assert parallel_for(
        _jittery, items, max_workers=8, batch_size=5, desc="t"
    ) == [i * 10 for i in range(23)]


def test_empty_input() -> None:
    assert parallel_for(_jittery, [], max_workers=4, desc="t") == []
    assert parallel_for(_jittery, [], max_workers=4, batch_size=5, desc="t") == []


def test_on_progress_is_called_per_completion() -> None:
    seen: list[int] = []
    parallel_for(
        _jittery,
        [(i,) for i in range(10)],
        max_workers=4,
        desc="t",
        on_progress=lambda: seen.append(1),
    )
    assert len(seen) == 10
