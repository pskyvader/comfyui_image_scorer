from __future__ import annotations

import itertools
import os
from typing import Any, Iterator

from ...core.observability.logger import get_logger, ModuleLogger
from ...core.filesystem.paths import (
    vectors_file,
    scores_file,
    comparisons_file,
    text_data_file,
    vectors_dir,
    image_root,
)
from ...core.io.serialization import (
    write_single_jsonl,
    discover_files,
    collect_valid_files,
)
from ...core.configuration.settings import config
from ...domain.analysis.image_analysis import ImageAnalysis
from ...domain.analysis.trueskill import replay_ratings, public_score_from_rating
from ...domain.database.ports import ComparisonRepository
from ...domain.loading import BatchSizerFactory, MapsProvider, ModelLoader
from ...application.services.vector_list import VectorList
from ...application.data_transform.config.maps import register_map_values

logger: ModuleLogger = get_logger(__name__)


def build_split_files(
    limit: int,
    model_loader: ModelLoader,
    batch_sizer_factory: BatchSizerFactory,
    maps_provider: MapsProvider,
) -> dict[str, int]:
    logger.info("Starting image processing...")

    if not os.path.isdir(image_root):
        raise FileNotFoundError(
            f"Configured image_root does not exist or is not a directory: {image_root}"
        )
    batch_size = config["prepare"]["batch_size"]
    max_workers = config["prepare"]["max_workers"]

    logger.debug("loading already-processed ids from split files...")
    split_ids = VectorList(
        [], read_only=False, model_loader=model_loader, batch_sizer_factory=batch_sizer_factory, maps_provider=maps_provider
    )
    processed_files: set[str] | None = None
    for c in split_ids.sorted_vectors.values():
        ids = set(c["vector"].vector_list.keys())
        if ids:
            processed_files = ids if processed_files is None else processed_files & ids
    processed_files = processed_files or set()

    logger.info(f"collecting files in {image_root}...")
    files: Iterator[tuple[str, str]] = discover_files(image_root)
    if processed_files:
        files = (f for f in files if os.path.basename(f[0]) not in processed_files)
    if limit > 0:
        files = itertools.islice(files, limit)
    collected_data = collect_valid_files(
        files,
        max_workers=max_workers,
        scored_only=True,
    )

    if len(collected_data) == 0:
        logger.info("No new valid files found. Exiting.")
        result = {"total": len(processed_files), "new": 0}

        return result

    logger.info("analyzing images ...")
    image_analysis = ImageAnalysis(collected_data, model_loader, batch_sizer_factory)
    processed_data = image_analysis.analyze_images_from_paths(batch_size, max_workers)
    register_map_values(processed_data, maps_provider)
    logger.info(f"processed data:{len(processed_data)}. Creating vector list object...")
    vectors_list_parser = VectorList(
        processed_data,
        read_only=False,
        model_loader=model_loader,
        batch_sizer_factory=batch_sizer_factory,
        maps_provider=maps_provider,
    )

    vectors_list_parser.create_vectors()
    vectors_list_parser.export_split_files()

    summary = {
        "total": len(processed_files) + len(processed_data),
        "new": len(processed_data),
    }

    logger.info("=== DONE ===")
    logger.info(f"Total: {summary['total']} ({summary['new']} new)")

    return summary


def build_full_files(
    model_loader: ModelLoader,
    batch_sizer_factory: BatchSizerFactory,
    maps_provider: MapsProvider,
) -> dict[str, Any]:
    os.makedirs(vectors_dir, exist_ok=True)

    vector_list = VectorList(
        [],
        read_only=False,
        model_loader=model_loader,
        batch_sizer_factory=batch_sizer_factory,
        maps_provider=maps_provider,
    )

    if not vector_list.unique_ids:
        logger.info("No split data found, skipping full file build.")
        return {"vectors": 0, "text_data": 0}

    vector_list.filter_missing_vectors()
    vector_list.join_vectors()
    vector_list.join_text_data()
    vector_list.update_lists()

    write_single_jsonl(vectors_file, vector_list.vectors_list, mode="w")
    write_single_jsonl(text_data_file, vector_list.text_list, mode="w")

    return {
        "vectors": len(vector_list.vectors_list),
        "text_data": len(vector_list.text_list),
    }


def run_rebuild_scores_only(
    comparison_repo: ComparisonRepository,
) -> dict[str, Any]:
    rows = comparison_repo.get_all_comparisons()

    comparisons = [
        {
            "id": comp["id"],
            "comparison_id": comp["id"],
            "filename_a": comp["filename_a"],
            "filename_b": comp["filename_b"],
            "winner": comp["winner"],
            "timestamp": comp["timestamp"],
        }
        for comp in rows
    ]
    write_single_jsonl(comparisons_file, comparisons, "w")

    replayed = replay_ratings(rows)
    scores = [
        {fid: public_score_from_rating(rating)}
        for fid, (rating, _count) in replayed.items()
    ]
    write_single_jsonl(scores_file, scores, "w")

    return {"scores": len(scores)}
