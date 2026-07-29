from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

from ...core.observability.logger import get_logger, ModuleLogger
from ...core.filesystem.paths import (
    vectors_dir, split_dir, vectors_file, scores_file,
    comparisons_file, index_file, text_data_file,
    image_root_processed,
)
from ...core.io.serialization import (
    load_single_jsonl, write_single_jsonl,
    discover_files, collect_valid_files,
)
from ...core.configuration.settings import config
from ...domain.vectors.helpers import get_value_from_entry

logger: ModuleLogger = get_logger(__name__)


def _count_jsonl(path: str) -> int:
    if not os.path.exists(path):
        return 0
    count = 0
    for _ in load_single_jsonl(path):
        count += 1
    return count


_EXCLUDED_KEYS = frozenset({
    "comparison_history", "bbox", "nose", "left_eye_inner", "left_eye",
    "left_eye_outer", "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear", "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_pinky", "right_pinky",
    "left_index", "right_index", "left_thumb", "right_thumb",
    "left_hip", "right_hip", "left_knee", "right_knee",
    "left_ankle", "right_ankle", "left_heel", "right_heel",
    "left_foot_index", "right_foot_index", "face_bbox", "body_pose",
    "last_compared", "prompt_tags", "filename",
    "negative_prompt", "positive_prompt", "custom_text",
    "artifact_score", "colorfulness", "contrast", "edge_density",
    "noise_score", "sharpness", "texture_lbp",
})


def _flatten_to_vector(value: Any, key: str | None = None) -> list[float]:
    if key is not None and key in _EXCLUDED_KEYS:
        return []
    result: list[float] = []
    if isinstance(value, dict):
        for k, v in value.items():
            result.extend(_flatten_to_vector(v, k))
    elif isinstance(value, (list, tuple)):
        for v in value:
            result.extend(_flatten_to_vector(v))
    elif isinstance(value, (int, float)):
        result.append(float(value))
    return result


def _build_vectors_from_analysis(limit: int = 0) -> dict[str, Any]:
    prepare_conf = config["prepare"]
    max_workers = int(prepare_conf["max_workers"])

    pairs = list(discover_files(image_root_processed))
    if limit > 0:
        pairs = pairs[:limit]

    entries = collect_valid_files(
        pairs, set(), image_root_processed, limit=0,
        max_workers=max_workers, scored_only=True,
    )
    os.makedirs(vectors_dir, exist_ok=True)
    os.makedirs(split_dir, exist_ok=True)

    from ...application.services.vector_list import VectorList
    from ...infrastructure.loading.maps_loader import maps_list

    for _path, entry, _timestamp, _file_id in entries:
        if not isinstance(entry, dict):
            continue
        for v in config["vector"]["vectors"]:
            if v["type"] in ("map", "person_map"):
                value = get_value_from_entry(entry, v["name"], v.get("alias"))
                if value is not None:
                    maps_list.register_value(v["name"], value)

    vector_list = VectorList(entries, read_only=False)

    vector_list.create_vectors()
    vector_list.export_split_files()

    vector_entries: list[dict[str, Any]] = []
    index_entries: list[str] = []
    text_entries: list[dict[str, Any]] = []

    for img_path, entry, timestamp, file_id in entries:
        flat_vec = _flatten_to_vector(entry)
        vector_entries.append({file_id: flat_vec})
        index_entries.append(file_id)
        text_part = {k: v for k, v in entry.items() if isinstance(v, (str, int, float, bool))}
        text_entries.append({"id": file_id, **text_part})

    write_single_jsonl(vectors_file, vector_entries, "w")
    write_single_jsonl(index_file, index_entries, "w")
    write_single_jsonl(text_data_file, text_entries, "w")

    return {
        "entries": len(entries),
        "split_files": len(vector_list.sorted_vectors),
    }


def run_prepare(limit: int = 0, batch: bool = False) -> dict[str, Any]:
    os.makedirs(split_dir, exist_ok=True)
    build_result = _build_vectors_from_analysis(limit=limit)
    rebuild_result = run_rebuild_scores_only()
    return {
        "vectors": _count_jsonl(vectors_file),
        "scores": _count_jsonl(scores_file),
        "index": _count_jsonl(index_file),
        "text_data": _count_jsonl(text_data_file),
        "build": build_result,
        "scores": rebuild_result,
    }


def run_rebuild_scores_only() -> dict[str, Any]:
    if not os.path.exists(vectors_file):
        return {"error": "vectors.jsonl must exist before rebuilding scores"}
    if not os.path.exists(index_file):
        return {"error": "index.jsonl must exist before rebuilding scores"}

    scores: list[dict[str, float]] = []
    comparisons: list[dict[str, Any]] = []
    vector_data = list(load_single_jsonl(vectors_file))

    from ...infrastructure.persistence.images_repository import get_all_images
    from ...infrastructure.persistence.comparisons_repository import get_all_comparisons

    db_images = {img["filename"]: img for img in get_all_images()}
    db_compares = get_all_comparisons()

    for entry in vector_data:
        for file_id, meta in entry.items():
            db_entry = db_images.get(str(file_id))
            if db_entry:
                scores.append({file_id: float(db_entry["score"])})

    for comp in db_compares:
        comparisons.append({
            "comparison_id": comp["id"],
            "filename_a": comp["filename_a"],
            "filename_b": comp["filename_b"],
            "winner": comp["winner"],
            "timestamp": comp["timestamp"],
        })

    write_single_jsonl(scores_file, scores, "w")
    write_single_jsonl(comparisons_file, comparisons, "w")

    return {
        "scores": len(scores),
        "comparisons": len(comparisons),
    }
