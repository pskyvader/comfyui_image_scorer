from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any, Callable, TypeVar, cast
from tqdm import tqdm
import time

from ..observability.logger import get_logger, ModuleLogger

R = TypeVar("R")
logger: ModuleLogger = get_logger(__name__)


def parallel_batch(fn: Callable[..., R], items: list[tuple[Any, ...]]) -> list[R]:
    results: list[R] = []
    for item in items:
        results.append(fn(*item))
    return results


def parallel_for(
    fn: Callable[..., R],
    items: list[tuple[Any, ...]],
    *,
    max_workers: int = 1,
    batch_size: int = 0,
    desc: str = "Processing",
    unit: str = "items",
    on_progress: Callable[[], None] | None = None,
) -> list[R]:
    """Execute fn(*item) for each item across a thread pool.

    Results are returned in input order regardless of completion order, so
    callers that persist or aggregate them get a stable result across runs.

    Args:
        fn: The callable to invoke for each item.
        items: Argument tuples, each unpacked as ``fn(*item)``.
        max_workers: Maximum number of concurrent threads.
        batch_size: If > 0, submit items in batches of this size.
        desc: tqdm description prefix.
        unit: tqdm unit label.
        on_progress: Optional callback invoked after each completed item.

    Returns:
        List of results in input order.
    """
    logger.info(f"starting parallel workers for {str(fn)[:10]}...")
    n: int = len(items)
    ordered: list[R | None] = [None] * n
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        with tqdm(total=n, desc=desc, unit=unit, leave=False, position=0, delay=3.0) as pbar:
            if batch_size > 0:
                batches = [
                    items[i : i + batch_size] for i in range(0, n, batch_size)
                ]
                started_batches: dict[Future[list[R]], int] = {
                    executor.submit(parallel_batch, fn, batch): index
                    for index, batch in enumerate(batches)
                }
                for future in as_completed(started_batches):
                    res: list[R] = future.result()
                    offset = started_batches[future] * batch_size
                    ordered[offset : offset + len(res)] = res
                    pbar.update(len(res))
                    if on_progress:
                        on_progress()
            else:
                started: dict[Future[R], int] = {
                    executor.submit(fn, *item): index
                    for index, item in enumerate(items)
                }
                recent: deque[float] = deque(maxlen=100)
                for future in as_completed(started):
                    elapsed = time.perf_counter() - started[future]
                    recent.append(elapsed)
                    ordered[started[future]] = future.result()
                    pbar.update(1)
                    pbar.set_postfix(avg=f"{sum(recent)/len(recent):.4f}s")
                    if on_progress:
                        on_progress()
    return cast(list[R], ordered)
