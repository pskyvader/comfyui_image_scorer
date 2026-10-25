"""Enumerate supported condition combinations from per-image Boolean masks."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from threading import Lock
from typing import Callable, Protocol

import numpy as np
from tqdm import tqdm

from ...core.configuration.settings import config
from ...core.filesystem.paths import analysis_dir
from ...core.io.serialization import atomic_write_json
from ...core.observability.logger import ModuleLogger, get_logger
from ...core.utilities.concurrency import parallel_for

logger: ModuleLogger = get_logger(__name__)


def _worker_count() -> int:
    """Return the configured worker count, with one worker as the minimum."""
    return max(1, int(config["prepare"]["max_workers"]))


class CombinationFinder(Protocol):
    """Callable that returns qualifying parent/property column pairs."""

    def __call__(
        self,
        current_combination_image_masks: np.ndarray,
        image_property_matrix: np.ndarray,
        count_dtype: np.dtype[np.generic],
        current_combinations: list[tuple[int, ...]],
        property_columns: np.ndarray,
        minimum_matching_images: int,
        parent_combinations_per_batch: int,
        combination_depth: int,
        multiplied_matrix_cache_path: Path | None = None,
        image_row_indices: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]: ...


def create_image_property_matrix(
    property_image_bitmasks: list[int], image_count: int
) -> np.ndarray:
    """Unpack one image bitmask per property into an image-by-property Boolean matrix."""
    bitmask_byte_count = (image_count + 7) // 8
    image_property_matrix = np.empty(
        (image_count, len(property_image_bitmasks)), dtype=bool
    )
    for property_column, property_image_bitmask in enumerate(property_image_bitmasks):
        bitmask_bytes = property_image_bitmask.to_bytes(bitmask_byte_count, "little")
        image_property_matrix[:, property_column] = np.unpackbits(
            np.frombuffer(bitmask_bytes, dtype=np.uint8), bitorder="little"
        )[:image_count]
    return image_property_matrix


def calculate_batch_capacity(
    image_property_matrix: np.ndarray,
    memory_budget_bytes: int,
) -> int:
    """Fit as many initial-matrix-sized work units as the memory budget allows."""
    initial_matrix_bytes = image_property_matrix.nbytes
    batch_capacity = memory_budget_bytes // max(1, initial_matrix_bytes)
    if batch_capacity < 1:
        logger.warning(
            "initial matrix is %s bytes, over the %s-byte budget; using batch size 1",
            f"{initial_matrix_bytes:,}",
            f"{memory_budget_bytes:,}",
        )
        return 1
    return batch_capacity


def _cache_directory(
    image_property_matrix: np.ndarray,
    image_row_ids: np.ndarray,
    minimum_matching_images: int,
) -> Path:
    fingerprint = hashlib.blake2b(digest_size=16)
    fingerprint.update(b"frequent-combinations-v1")
    fingerprint.update(repr(image_property_matrix.shape).encode())
    fingerprint.update(memoryview(np.ascontiguousarray(image_property_matrix)).cast("B"))
    encoded_image_ids = json.dumps(
        [_json_scalar(image_id) for image_id in image_row_ids],
        separators=(",", ":"),
    )
    fingerprint.update(encoded_image_ids.encode())
    fingerprint.update(str(minimum_matching_images).encode())
    # Finder strategies may differ on excluded columns, but agree on eligible extensions.
    directory = Path(analysis_dir) / "frequent_combinations" / fingerprint.hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _json_scalar(value: object) -> str | int | float | bool | None:
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"image IDs must be JSON-compatible scalars, got {type(value).__name__}.")


def _level_cache_paths(cache_directory: Path, level: int) -> tuple[Path, Path, Path]:
    stem = f"level_{level:02d}"
    return (
        cache_directory / f"{stem}_multiplied.npy",
        cache_directory / f"{stem}_intersected.npy",
        cache_directory / f"{stem}_maps.json",
    )


def _save_matrix_cache(cache_path: Path, matrix: np.ndarray) -> None:
    temporary_path = cache_path.with_name(cache_path.name + ".tmp")
    with temporary_path.open("wb") as output:
        np.save(output, matrix, allow_pickle=False)
    os.replace(temporary_path, cache_path)


def _load_multiplication_cache(
    cache_path: Path,
    expected_shape: tuple[int, int],
    expected_dtype: np.dtype[np.generic] | None = None,
) -> np.ndarray | None:
    if not cache_path.is_file():
        return None
    multiplied_matrix = np.load(cache_path, mmap_mode="r", allow_pickle=False)
    if multiplied_matrix.shape != expected_shape or (
        expected_dtype is not None and multiplied_matrix.dtype != expected_dtype
    ):
        raise ValueError(f"Cached multiplication matrix has an unexpected shape or dtype: {cache_path}")
    logger.info("loaded multiplied matrix from %s", cache_path)
    return multiplied_matrix


def _save_level_maps(
    maps_path: Path,
    combinations: list[tuple[int, ...]],
    image_row_ids: np.ndarray,
) -> None:
    payload = {
        "combinations": [list(combination) for combination in combinations],
        "image_ids": [_json_scalar(image_id) for image_id in image_row_ids],
    }
    atomic_write_json(str(maps_path), payload, indent=None)


def _load_level_cache(
    intersected_path: Path,
    maps_path: Path,
    source_image_property_matrix: np.ndarray,
    source_image_row_ids: np.ndarray,
) -> tuple[np.ndarray, list[tuple[int, ...]], np.ndarray, np.ndarray] | None:
    if not intersected_path.is_file() or not maps_path.is_file():
        return None

    with maps_path.open("r", encoding="utf-8") as source:
        maps = json.load(source)
    combinations = [tuple(map(int, combination)) for combination in maps["combinations"]]
    image_row_ids = np.asarray(maps["image_ids"], dtype=source_image_row_ids.dtype)
    source_positions = {image_id: row for row, image_id in enumerate(source_image_row_ids)}
    image_rows = np.fromiter(
        (source_positions[image_id] for image_id in image_row_ids),
        dtype=np.intp,
        count=len(image_row_ids),
    )
    image_property_matrix = source_image_property_matrix[image_rows]
    if len(image_row_ids) == 0 or len(combinations) == 0:
        intersected_matrix = np.load(intersected_path, allow_pickle=False)
    else:
        intersected_matrix = np.load(intersected_path, mmap_mode="r", allow_pickle=False)
    if intersected_matrix.shape != (len(image_row_ids), len(combinations)):
        raise ValueError(f"Cached level matrix and maps do not align: {intersected_path}")
    logger.info("loaded cached level output from %s", intersected_path.parent)
    return intersected_matrix, combinations, image_property_matrix, image_row_ids


def _load_or_create_multiplication_matrix(
    cache_path: Path | None,
    shape: tuple[int, int],
    dtype: np.dtype[np.generic],
    *,
    initialize_zero: bool,
    calculate: Callable[[np.ndarray], None],
) -> np.ndarray:
    if cache_path is not None:
        multiplied_matrix = _load_multiplication_cache(cache_path, shape, dtype)
        if multiplied_matrix is not None:
            return multiplied_matrix

    temporary_path = None
    if cache_path is None:
        multiplied_matrix = np.zeros(shape, dtype=dtype) if initialize_zero else np.empty(shape, dtype=dtype)
    else:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = cache_path.with_name(cache_path.name + ".tmp")
        multiplied_matrix = np.lib.format.open_memmap(
            temporary_path, mode="w+", dtype=dtype, shape=shape
        )
        if initialize_zero:
            multiplied_matrix.fill(0)

    calculate(multiplied_matrix)

    if cache_path is not None and temporary_path is not None:
        multiplied_matrix.flush()
        del multiplied_matrix
        os.replace(temporary_path, cache_path)
        multiplied_matrix = np.load(cache_path, mmap_mode="r", allow_pickle=False)
        logger.info("saved multiplied matrix to %s", cache_path)
    return multiplied_matrix


def count_shared_images(
    current_combination_image_masks: np.ndarray,
    image_property_matrix: np.ndarray,
    count_dtype: np.dtype[np.generic],
    batch_start: int,
    batch_stop: int,
    image_row_indices: np.ndarray | None = None,
) -> np.ndarray:
    """Return shared-image counts for one batch of parent combinations against all properties."""
    if image_row_indices is None:
        parent_mask_batch = current_combination_image_masks[:, batch_start:batch_stop]
    else:
        parent_mask_batch = current_combination_image_masks[
            image_row_indices, batch_start:batch_stop
        ]
    return np.matmul(
        parent_mask_batch.T,
        image_property_matrix,
        dtype=count_dtype,
    )


def create_qualifying_extension_mask(
    shared_image_counts: np.ndarray,
    last_property_by_parent: np.ndarray,
    property_columns: np.ndarray,
    minimum_matching_images: int,
) -> np.ndarray:
    """Keep parent/property pairs meeting the image-count and ordering rules."""
    qualifying_extensions = shared_image_counts >= minimum_matching_images
    qualifying_extensions &= (
        property_columns[None, :] > last_property_by_parent[:, None]
    )
    return qualifying_extensions


def _find_qualifying_extensions(
    multiplied_matrix: np.ndarray,
    current_combinations: list[tuple[int, ...]],
    property_columns: np.ndarray,
    minimum_matching_images: int,
    parent_combinations_per_batch: int,
    combination_depth: int,
) -> tuple[np.ndarray, np.ndarray]:
    candidate_batches = [
        (start, min(start + parent_combinations_per_batch, len(current_combinations)))
        for start in range(0, len(current_combinations), parent_combinations_per_batch)
    ]
    worker_count = _worker_count()
    logger.info(
        "level %d: filtering multiplied matrix %s in %s batches",
        combination_depth,
        multiplied_matrix.shape,
        f"{len(candidate_batches):,}",
    )

    def filter_parent_batch(start: int, stop: int) -> tuple[np.ndarray, np.ndarray]:
        last_property_by_parent = np.fromiter(
            (current_combinations[parent][-1] for parent in range(start, stop)),
            dtype=np.int64,
            count=stop - start,
        )
        qualifying_extensions = create_qualifying_extension_mask(
            multiplied_matrix[start:stop],
            last_property_by_parent,
            property_columns,
            minimum_matching_images,
        )
        local_parent_columns, added_property_columns = np.nonzero(qualifying_extensions)
        return local_parent_columns + start, added_property_columns

    batch_results = parallel_for(
        filter_parent_batch,
        candidate_batches,
        max_workers=worker_count,
        desc=f"level {combination_depth} candidate image-count masks",
        unit="batch",
    )
    surviving_parents = [parents for parents, _ in batch_results if parents.size]
    surviving_properties = [properties for parents, properties in batch_results if parents.size]
    if not surviving_parents:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    return np.concatenate(surviving_parents), np.concatenate(surviving_properties)


def find_qualifying_combinations(
    current_combination_image_masks: np.ndarray,
    image_property_matrix: np.ndarray,
    count_dtype: np.dtype[np.generic],
    current_combinations: list[tuple[int, ...]],
    property_columns: np.ndarray,
    minimum_matching_images: int,
    parent_combinations_per_batch: int,
    combination_depth: int,
    multiplied_matrix_cache_path: Path | None = None,
    image_row_indices: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Multiply parent masks by all property masks, then return qualifying extensions."""
    batch_ranges = [
        (
            batch_start,
            min(batch_start + parent_combinations_per_batch, len(current_combinations)),
        )
        for batch_start in range(
            0, len(current_combinations), parent_combinations_per_batch
        )
    ]
    worker_count = _worker_count()
    count_cells = len(current_combinations) * len(property_columns)
    logger.info(
        "level %d support multiplication: %s parents x %s properties = %s count cells; "
        "%s batches of up to %s parents; up to %s workers",
        combination_depth,
        f"{len(current_combinations):,}",
        f"{len(property_columns):,}",
        f"{count_cells:,}",
        f"{len(batch_ranges):,}",
        f"{parent_combinations_per_batch:,}",
        f"{worker_count:,}",
    )

    def multiply_parent_batch(
        multiplied_matrix: np.ndarray, batch_start: int, batch_stop: int
    ) -> None:
        logger.debug(
            "level %d: multiplying parent columns %d-%d",
            combination_depth,
            batch_start,
            batch_stop,
        )
        multiplied_matrix[batch_start:batch_stop] = count_shared_images(
            current_combination_image_masks,
            image_property_matrix,
            count_dtype,
            batch_start,
            batch_stop,
            image_row_indices,
        )

    def calculate(multiplied_matrix: np.ndarray) -> None:
        parallel_for(
            multiply_parent_batch,
            [(multiplied_matrix, start, stop) for start, stop in batch_ranges],
            max_workers=worker_count,
            desc=f"level {combination_depth} candidate image-count multiplication",
            unit="batch",
        )

    multiplied_matrix = _load_or_create_multiplication_matrix(
        multiplied_matrix_cache_path,
        (len(current_combinations), len(property_columns)),
        count_dtype,
        initialize_zero=False,
        calculate=calculate,
    )
    return _find_qualifying_extensions(
        multiplied_matrix,
        current_combinations,
        property_columns,
        minimum_matching_images,
        parent_combinations_per_batch,
        combination_depth,
    )


def find_qualifying_combinations_blocked(
    current_combination_image_masks: np.ndarray,
    image_property_matrix: np.ndarray,
    count_dtype: np.dtype[np.generic],
    current_combinations: list[tuple[int, ...]],
    property_columns: np.ndarray,
    minimum_matching_images: int,
    parent_combinations_per_batch: int,
    combination_depth: int,
    property_block_size: int,
    multiplied_matrix_cache_path: Path | None = None,
    image_row_indices: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Multiply only extension columns, cache the counts, and return qualifying pairs."""
    if property_block_size < 1:
        raise ValueError("property_block_size must be at least 1.")

    parents_by_last_property_block: dict[int, list[int]] = {}
    for parent_column, combination in enumerate(current_combinations):
        block_start = (combination[-1] // property_block_size) * property_block_size
        parents_by_last_property_block.setdefault(block_start, []).append(parent_column)

    parent_groups = [
        (block_start, np.asarray(parent_columns, dtype=np.int64))
        for block_start, parent_columns in sorted(parents_by_last_property_block.items())
    ]
    total_batches = sum(
        (len(parent_columns) + parent_combinations_per_batch - 1)
        // parent_combinations_per_batch
        for _, parent_columns in parent_groups
    )
    parent_batches = [
        (
            block_start,
            parent_columns[batch_start : batch_start + parent_combinations_per_batch],
        )
        for block_start, parent_columns in parent_groups
        for batch_start in range(0, len(parent_columns), parent_combinations_per_batch)
    ]
    worker_count = _worker_count()
    count_cells = sum(
        len(parent_columns) * (len(property_columns) - block_start)
        for block_start, parent_columns in parent_groups
    )
    logger.info(
        "level %d blocked support multiplication: %s parents across %s property blocks; "
        "%s count cells; %s batches of up to %s parents; up to %s workers",
        combination_depth,
        f"{len(current_combinations):,}",
        f"{len(parent_groups):,}",
        f"{count_cells:,}",
        f"{total_batches:,}",
        f"{parent_combinations_per_batch:,}",
        f"{worker_count:,}",
    )

    def multiply_parent_batch(
        multiplied_matrix: np.ndarray,
        block_start: int,
        parent_column_batch: np.ndarray,
    ) -> None:
        block_stop = min(block_start + property_block_size, len(property_columns))
        if image_row_indices is None:
            parent_image_masks = current_combination_image_masks[
                :, parent_column_batch
            ]
        else:
            parent_image_masks = current_combination_image_masks[
                np.ix_(image_row_indices, parent_column_batch)
            ]
        logger.debug(
            "level %d: blocked multiplication for property block %d-%d across %d parents "
            "(parent columns spanning %d-%d)",
            combination_depth,
            block_start,
            block_stop,
            len(parent_column_batch),
            int(parent_column_batch[0]),
            int(parent_column_batch[-1]),
        )

        if block_stop < len(property_columns):
            later_property_image_masks = image_property_matrix[:, block_stop:]
            later_property_counts = np.matmul(
                parent_image_masks.T,
                later_property_image_masks,
                dtype=count_dtype,
            )
            multiplied_matrix[parent_column_batch, block_stop:] = later_property_counts

        diagonal_property_image_masks = image_property_matrix[:, block_start:block_stop]
        diagonal_property_counts = np.matmul(
            parent_image_masks.T,
            diagonal_property_image_masks,
            dtype=count_dtype,
        )
        multiplied_matrix[parent_column_batch, block_start:block_stop] = (
            diagonal_property_counts
        )

    def calculate(multiplied_matrix: np.ndarray) -> None:
        parallel_for(
            multiply_parent_batch,
            [
                (multiplied_matrix, block_start, parent_columns)
                for block_start, parent_columns in parent_batches
            ],
            max_workers=worker_count,
            desc=f"level {combination_depth} blocked image-count multiplication",
            unit="batch",
        )

    multiplied_matrix = _load_or_create_multiplication_matrix(
        multiplied_matrix_cache_path,
        (len(current_combinations), len(property_columns)),
        count_dtype,
        initialize_zero=True,
        calculate=calculate,
    )
    return _find_qualifying_extensions(
        multiplied_matrix,
        current_combinations,
        property_columns,
        minimum_matching_images,
        parent_combinations_per_batch,
        combination_depth,
    )


def create_possible_image_mask(
    current_combination_image_masks: np.ndarray,
    image_property_matrix: np.ndarray,
    current_combinations: list[tuple[int, ...]],
    parent_combinations_per_batch: int,
    combination_depth: int,
) -> np.ndarray:
    """Keep rows that can match at least one legally ordered extension."""
    image_count = current_combination_image_masks.shape[0]
    property_count = image_property_matrix.shape[1]
    parent_columns_by_last_property: list[list[int]] = [
        [] for _ in range(property_count)
    ]
    for parent_column, combination in enumerate(current_combinations):
        last_property = combination[-1]
        if last_property + 1 < property_count:
            parent_columns_by_last_property[last_property].append(parent_column)

    expandable_parent_count = sum(
        len(parent_columns)
        for parent_columns in parent_columns_by_last_property
    )
    logger.info(
        "level %d prefilter: checking %s expandable parents across %s properties",
        combination_depth,
        f"{expandable_parent_count:,}",
        f"{property_count:,}",
    )

    possible_image_mask = np.zeros(image_count, dtype=bool)
    has_later_property = np.zeros(image_count, dtype=bool)
    for last_property in tqdm(
        range(property_count - 1, -1, -1),
        total=property_count,
        desc=f"level {combination_depth} potential image prefilter",
        unit="property",
    ):
        parent_columns = parent_columns_by_last_property[last_property]
        if parent_columns:
            parent_image_mask = np.zeros(image_count, dtype=bool)
            for batch_start in range(
                0, len(parent_columns), parent_combinations_per_batch
            ):
                batch_stop = min(
                    batch_start + parent_combinations_per_batch,
                    len(parent_columns),
                )
                np.logical_or(
                    parent_image_mask,
                    current_combination_image_masks[
                        :, parent_columns[batch_start:batch_stop]
                    ].any(axis=1),
                    out=parent_image_mask,
                )
            parent_image_mask &= has_later_property
            np.logical_or(
                possible_image_mask,
                parent_image_mask,
                out=possible_image_mask,
            )

        np.logical_or(
            has_later_property,
            image_property_matrix[:, last_property],
            out=has_later_property,
        )

    return possible_image_mask


def create_candidate_image_masks(
    current_combination_image_masks: np.ndarray,
    image_property_matrix: np.ndarray,
    parent_combination_columns: np.ndarray,
    added_property_columns: np.ndarray,
    candidate_pairs_per_batch: int,
    combination_depth: int,
    intersected_matrix_cache_path: Path,
    image_row_indices: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the retained image-row mask and its cached candidate intersections."""
    image_count = image_property_matrix.shape[0]
    candidate_pair_count = len(parent_combination_columns)
    image_filter = np.zeros(image_count, dtype=bool)
    if candidate_pair_count == 0:
        empty_intersections = np.empty((0, 0), dtype=bool)
        _save_matrix_cache(intersected_matrix_cache_path, empty_intersections)
        logger.info(
            "level %d intersection passes: no supported candidates; saved empty matrix",
            combination_depth,
        )
        return empty_intersections, image_filter

    worker_count = _worker_count()
    intersection_batches = [
        (start, min(start + candidate_pairs_per_batch, candidate_pair_count))
        for start in range(0, candidate_pair_count, candidate_pairs_per_batch)
    ]
    used_image_bits = np.zeros((image_count + 7) // 8, dtype=np.uint8)
    used_image_bits_lock = Lock()
    logger.info(
        "level %d intersection pass 1/2: finding used images across %s candidate batches "
        "using up to %s workers",
        combination_depth,
        f"{len(intersection_batches):,}",
        f"{worker_count:,}",
    )

    def find_used_image_rows(batch_start: int, batch_stop: int) -> None:
        if image_row_indices is None:
            parent_image_masks = current_combination_image_masks[
                :, parent_combination_columns[batch_start:batch_stop]
            ]
        else:
            parent_image_masks = current_combination_image_masks[
                np.ix_(
                    image_row_indices,
                    parent_combination_columns[batch_start:batch_stop],
                )
            ]
        added_property_image_masks = image_property_matrix[
            :, added_property_columns[batch_start:batch_stop]
        ]
        np.logical_and(
            parent_image_masks,
            added_property_image_masks,
            out=parent_image_masks,
        )
        batch_image_bits = np.packbits(
            parent_image_masks.any(axis=1), bitorder="little"
        )
        with used_image_bits_lock:
            np.bitwise_or(used_image_bits, batch_image_bits, out=used_image_bits)

    parallel_for(
        find_used_image_rows,
        intersection_batches,
        max_workers=worker_count,
        desc=f"level {combination_depth} image filter pass 1/2",
        unit="batch",
    )
    image_filter = np.unpackbits(used_image_bits, bitorder="little")[:image_count]

    retained_image_rows = np.flatnonzero(image_filter)
    retained_image_count = len(retained_image_rows)
    filtered_cell_count = retained_image_count * candidate_pair_count
    filtered_matrix_bytes = filtered_cell_count * np.dtype(np.bool_).itemsize
    logger.info(
        "level %d pass 1/2 complete: %s / %s image rows retained; pass 2/2 will "
        "recompute intersections for those rows and write %s x %s = %s bool cells (%s bytes)",
        combination_depth,
        f"{retained_image_count:,}",
        f"{image_count:,}",
        f"{retained_image_count:,}",
        f"{candidate_pair_count:,}",
        f"{filtered_cell_count:,}",
        f"{filtered_matrix_bytes:,}",
    )

    if retained_image_count == 0:
        empty_intersections = np.empty((0, candidate_pair_count), dtype=bool)
        _save_matrix_cache(intersected_matrix_cache_path, empty_intersections)
        logger.info(
            "level %d intersection pass 2/2 complete: no image rows to write",
            combination_depth,
        )
        return empty_intersections, image_filter

    temporary_path = intersected_matrix_cache_path.with_name(
        intersected_matrix_cache_path.name + ".tmp"
    )
    filtered_candidate_masks = np.lib.format.open_memmap(
        temporary_path,
        mode="w+",
        dtype=bool,
        shape=(retained_image_count, candidate_pair_count),
    )

    def write_filtered_intersection_batch(batch_start: int, batch_stop: int) -> None:
        if image_row_indices is None:
            parent_rows = retained_image_rows
        else:
            parent_rows = image_row_indices[retained_image_rows]
        parent_image_masks = current_combination_image_masks[
            np.ix_(
                parent_rows,
                parent_combination_columns[batch_start:batch_stop],
            )
        ]
        added_property_image_masks = image_property_matrix[
            np.ix_(
                retained_image_rows,
                added_property_columns[batch_start:batch_stop],
            )
        ]
        np.logical_and(
            parent_image_masks,
            added_property_image_masks,
            out=filtered_candidate_masks[:, batch_start:batch_stop],
        )

    logger.info(
        "level %d intersection pass 2/2: writing %s retained candidate masks in %s batches using up to %s workers",
        combination_depth,
        f"{candidate_pair_count:,}",
        f"{len(intersection_batches):,}",
        f"{worker_count:,}",
    )
    parallel_for(
        write_filtered_intersection_batch,
        intersection_batches,
        max_workers=worker_count,
        desc=f"level {combination_depth} filtered intersections pass 2/2",
        unit="batch",
    )
    del write_filtered_intersection_batch
    filtered_candidate_masks.flush()
    del filtered_candidate_masks
    os.replace(temporary_path, intersected_matrix_cache_path)
    filtered_candidate_masks = np.load(
        intersected_matrix_cache_path,
        mmap_mode="r",
        allow_pickle=False,
    )
    logger.info(
        "level %d intersection pass 2/2 complete: saved %s",
        combination_depth,
        intersected_matrix_cache_path,
    )

    return filtered_candidate_masks, image_filter


def collect_level_image_matches(
    current_combination_image_masks: np.ndarray,
    current_combinations: list[tuple[int, ...]],
    image_row_ids: np.ndarray,
    property_labels: np.ndarray,
) -> tuple[list[tuple[object, ...]], list[np.ndarray]]:
    """Return each combination and the image IDs whose rows match it."""
    level_combinations: list[tuple[object, ...]] = []
    level_matching_image_rows: list[np.ndarray] = []
    for combination_column, combination in enumerate(current_combinations):
        matching_image_rows = np.flatnonzero(
            current_combination_image_masks[:, combination_column]
        )
        level_combinations.append(tuple(property_labels[p] for p in combination))
        level_matching_image_rows.append(image_row_ids[matching_image_rows])
    return level_combinations, level_matching_image_rows


def generate_combinations(
    image_property_matrix: np.ndarray,
    image_row_ids: np.ndarray,
    max_combination_size: int,
    combination_finder: CombinationFinder,
    *,
    minimum_matching_images: int = 2,
    memory_budget_gb: float = 4.0,
    property_labels: np.ndarray | None = None,
) -> tuple[list[tuple[object, ...]], list[np.ndarray]]:
    """Return supported property combinations and their matching image IDs.

    Multiplied counts, filtered intersections, and per-level combination/image
    maps are cached under the module's analysis output directory. Image rows
    unused by all combinations at a level are removed from both working matrices;
    their original IDs are retained in the level map.

    Args:
        image_property_matrix: Boolean or 0/1 matrix shaped (images, properties).
        image_row_ids: IDs aligned with rows of image_property_matrix.
        max_combination_size: Maximum number of properties in a combination.
        combination_finder: Batched support-count strategy, such as the full or blocked finder.
        minimum_matching_images: Minimum matching image count for each combination.
        memory_budget_gb: Batch sizing budget; divided by the initial matrix byte size.
        property_labels: IDs aligned with matrix columns; defaults to column indices.

    Returns:
        Supported property tuples and aligned arrays of matching image IDs.
    """
    image_property_matrix = np.asarray(image_property_matrix, dtype=bool)
    image_row_ids = np.asarray(image_row_ids)
    image_count, initial_property_count = image_property_matrix.shape

    if len(image_row_ids) != image_count:
        raise ValueError("image_row_ids must have one ID for each image row.")
    if max_combination_size < 1:
        return [], []
    if minimum_matching_images < 1:
        raise ValueError("minimum_matching_images must be at least 1.")
    if memory_budget_gb <= 0:
        raise ValueError("memory_budget_gb must be greater than 0.")

    memory_budget_bytes = int(memory_budget_gb * 1e9)

    if property_labels is None:
        property_labels = np.arange(initial_property_count)
    else:
        property_labels = np.asarray(property_labels)
        if len(property_labels) != initial_property_count:
            raise ValueError("property_labels must have one ID for each matrix column.")

    source_image_property_matrix = image_property_matrix
    source_image_row_ids = image_row_ids.copy()
    cache_directory = _cache_directory(
        source_image_property_matrix,
        source_image_row_ids,
        minimum_matching_images,
    )
    logger.info("combination cache: %s", cache_directory)
    (
        level_one_multiplied_path,
        level_one_intersected_path,
        level_one_maps_path,
    ) = _level_cache_paths(cache_directory, 1)
    level_one_multiplication = _load_multiplication_cache(
        level_one_multiplied_path,
        (1, initial_property_count),
    )
    cached_level_one = (
        _load_level_cache(
            level_one_intersected_path,
            level_one_maps_path,
            source_image_property_matrix,
            source_image_row_ids,
        )
        if level_one_multiplication is not None
        else None
    )
    if cached_level_one is not None:
        (
            current_combination_image_masks,
            current_combinations,
            image_property_matrix,
            image_row_ids,
        ) = cached_level_one
    else:
        if level_one_multiplication is not None:
            image_counts_by_property = level_one_multiplication[0]
        else:
            image_counts_by_property = np.count_nonzero(
                image_property_matrix, axis=0
            )[None, :]
            _save_matrix_cache(level_one_multiplied_path, image_counts_by_property)
            image_counts_by_property = image_counts_by_property[0]
        active_property_columns = np.flatnonzero(
            image_counts_by_property >= minimum_matching_images
        )
        current_combination_image_masks = image_property_matrix[
            :, active_property_columns
        ].copy()
        current_combinations = [(int(p),) for p in active_property_columns]
        image_filter = current_combination_image_masks.any(axis=1)
        current_combination_image_masks = current_combination_image_masks[image_filter]
        image_property_matrix = image_property_matrix[image_filter]
        image_row_ids = image_row_ids[image_filter]
        _save_matrix_cache(level_one_intersected_path, current_combination_image_masks)
        _save_level_maps(level_one_maps_path, current_combinations, image_row_ids)

    count_dtype = np.min_scalar_type(image_count)
    property_columns = np.arange(initial_property_count)
    all_combinations = []
    all_matching_image_rows = []

    initial_survivor_count = len(current_combinations)
    initial_survival_percent = (
        100.0 * initial_survivor_count / initial_property_count
        if initial_property_count
        else 0.0
    )
    logger.info(
        "level 1 combinations: %s / %s properties meet minimum image count (%.2f%%)",
        f"{initial_survivor_count:,}",
        f"{initial_property_count:,}",
        initial_survival_percent,
    )
    logger.info(
        "level 1 image filter: %s / %s image rows retained",
        f"{len(image_row_ids):,}",
        f"{image_count:,}",
    )

    for combination_size in range(1, max_combination_size + 1):
        if not current_combinations:
            break

        logger.info(
            "level %d | %s combinations",
            combination_size,
            f"{len(current_combinations):,}",
        )
        logger.info(
            "  matrices: image-property %s bool (%s cells, %s bytes); "
            "current-combination %s bool (%s cells, %s bytes); count dtype=%s",
            image_property_matrix.shape,
            f"{image_property_matrix.size:,}",
            f"{image_property_matrix.nbytes:,}",
            current_combination_image_masks.shape,
            f"{current_combination_image_masks.size:,}",
            f"{current_combination_image_masks.nbytes:,}",
            count_dtype.name,
        )
        logger.info(
            "  collecting image matches for %s combinations",
            f"{len(current_combinations):,}",
        )
        level_combinations, level_matching_image_rows = collect_level_image_matches(
            current_combination_image_masks,
            current_combinations,
            image_row_ids,
            property_labels,
        )
        all_combinations.extend(level_combinations)
        all_matching_image_rows.extend(level_matching_image_rows)

        if combination_size == max_combination_size:
            break

        next_level = combination_size + 1
        multiplied_path, intersected_path, maps_path = _level_cache_paths(
            cache_directory, next_level
        )
        cached_multiplication = _load_multiplication_cache(
            multiplied_path,
            (len(current_combinations), initial_property_count),
            count_dtype,
        )
        cached_level = (
            _load_level_cache(
                intersected_path,
                maps_path,
                source_image_property_matrix,
                source_image_row_ids,
            )
            if cached_multiplication is not None
            else None
        )
        if cached_level is not None:
            (
                current_combination_image_masks,
                current_combinations,
                image_property_matrix,
                image_row_ids,
            ) = cached_level
            logger.info(
                "level %d cache hit; skipping multiplication and intersection",
                next_level,
            )
            continue

        batch_item_capacity = calculate_batch_capacity(
            image_property_matrix, memory_budget_bytes
        )
        worker_count = _worker_count()
        initial_matrix_bytes = image_property_matrix.nbytes
        logger.info(
            "level %d batch size fixed for this level: %s initial-matrix units "
            "(%s bytes each); budget=%s bytes; %s candidate pairs per batch; "
            "up to %s workers",
            next_level,
            f"{batch_item_capacity:,}",
            f"{initial_matrix_bytes:,}",
            f"{memory_budget_bytes:,}",
            f"{batch_item_capacity:,}",
            f"{worker_count:,}",
        )
        prefilter_input_row_count = len(image_row_ids)
        possible_image_mask = create_possible_image_mask(
            current_combination_image_masks,
            image_property_matrix,
            current_combinations,
            batch_item_capacity,
            next_level,
        )
        possible_image_count = np.count_nonzero(possible_image_mask)
        if possible_image_count < prefilter_input_row_count:
            image_row_indices = np.flatnonzero(possible_image_mask)
            image_property_matrix = image_property_matrix[possible_image_mask]
            image_row_ids = image_row_ids[possible_image_mask]
        else:
            image_row_indices = None
        logger.info(
            "level %d prefilter applied: %s / %s image rows retained; batch size remains %s candidate pairs",
            next_level,
            f"{possible_image_count:,}",
            f"{prefilter_input_row_count:,}",
            f"{batch_item_capacity:,}",
        )

        parent_combination_count = current_combination_image_masks.shape[1]
        maximum_candidate_pair_count = sum(
            initial_property_count - combination[-1] - 1
            for combination in current_combinations
        )
        maximum_intersection_cells = (
            image_property_matrix.shape[0] * maximum_candidate_pair_count
        )
        maximum_intersection_bytes = (
            maximum_intersection_cells * np.dtype(np.bool_).itemsize
        )
        maximum_candidate_batch_count = (
            maximum_candidate_pair_count + batch_item_capacity - 1
        ) // batch_item_capacity
        candidate_pairs_per_batch = batch_item_capacity

        logger.info(
            "level %d possible extensions: %s from %s parents across %s properties",
            next_level,
            f"{maximum_candidate_pair_count:,}",
            f"{parent_combination_count:,}",
            f"{initial_property_count:,}",
        )
        logger.info(
            "  maximum intersection work per pass=%s x %s = %s bool cells (%s bytes)",
            f"{image_property_matrix.shape[0]:,}",
            f"{maximum_candidate_pair_count:,}",
            f"{maximum_intersection_cells:,}",
            f"{maximum_intersection_bytes:,}",
        )
        logger.info(
            "  intersection batches: %s x up to %s pairs; up to %s workers",
            f"{maximum_candidate_batch_count:,}",
            f"{candidate_pairs_per_batch:,}",
            f"{min(worker_count, maximum_candidate_batch_count):,}",
        )

        parent_combination_columns, added_property_columns = combination_finder(
            current_combination_image_masks,
            image_property_matrix,
            count_dtype,
            current_combinations,
            property_columns,
            minimum_matching_images,
            batch_item_capacity,
            next_level,
            multiplied_matrix_cache_path=multiplied_path,
            image_row_indices=image_row_indices,
        )
        surviving_combination_count = len(parent_combination_columns)
        survival_percent = (
            100.0 * surviving_combination_count / maximum_candidate_pair_count
            if maximum_candidate_pair_count
            else 0.0
        )
        logger.info(
            "level %d combinations surviving minimum image count: %s / %s (%.2f%%)",
            next_level,
            f"{surviving_combination_count:,}",
            f"{maximum_candidate_pair_count:,}",
            survival_percent,
        )

        candidate_batch_count = (
            surviving_combination_count + candidate_pairs_per_batch - 1
        ) // candidate_pairs_per_batch
        intersection_cell_count = image_property_matrix.shape[0] * surviving_combination_count
        intersection_bytes = intersection_cell_count * np.dtype(np.bool_).itemsize
        if surviving_combination_count:
            logger.info(
                "  pass 1 scan: %s images x %s candidates = %s bool cells (%s bytes)",
                f"{image_property_matrix.shape[0]:,}",
                f"{surviving_combination_count:,}",
                f"{intersection_cell_count:,}",
                f"{intersection_bytes:,}",
            )
            logger.info(
                "  each pass: %s candidate batches; up to %s workers at once",
                f"{candidate_batch_count:,}",
                f"{min(worker_count, candidate_batch_count):,}",
            )
        else:
            logger.info("  intersection passes: skipped (no supported candidates)")
        current_combination_image_masks, image_filter = create_candidate_image_masks(
            current_combination_image_masks,
            image_property_matrix,
            parent_combination_columns,
            added_property_columns,
            candidate_pairs_per_batch,
            next_level,
            intersected_path,
            image_row_indices=image_row_indices,
        )
        next_combinations = [
            current_combinations[parent_column] + (int(property_column),)
            for parent_column, property_column in zip(
                parent_combination_columns, added_property_columns
            )
        ]
        if not image_filter.all():
            image_property_matrix = image_property_matrix[image_filter]
            image_row_ids = image_row_ids[image_filter]
        current_combinations = next_combinations
        logger.info(
            "level %d image filter: %s / %s image rows retained",
            next_level,
            f"{len(image_row_ids):,}",
            f"{image_filter.size:,}",
        )
        _save_level_maps(maps_path, current_combinations, image_row_ids)
        logger.info("saved level %d intersection and maps", next_level)

    return all_combinations, all_matching_image_rows
