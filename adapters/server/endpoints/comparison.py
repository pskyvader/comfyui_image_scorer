"""Ranking API v2 endpoints."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from flask import Blueprint, current_app, jsonify, request

from ....core.observability.logger import get_logger, ModuleLogger
from ....core.configuration.settings import config
from ....domain.comparison.algorithm import merge_sort_ranker
from ....domain.comparison.algorithm.view import (
    describe_image,
    describe_pair,
)
from ....domain.comparison.algorithm.phase_order import get_phases
from ....domain.comparison.comparison_recorder import ComparisonRecorder
from ..deps import ServerDeps, get_server_deps

ranking_bp = Blueprint("ranking_v2", __name__, url_prefix="/api/ranking")
logger: ModuleLogger = get_logger(__name__)


class SkipRequest(BaseModel):
    """Payload for POST /api/ranking/skip."""

    filename: str = Field(..., min_length=1)


class SubmitComparisonRequest(BaseModel):
    """Payload for POST /api/ranking/submit-comparison."""

    filename_a: str = Field(..., min_length=1)
    filename_b: str = Field(..., min_length=1)
    winner: str = Field(..., min_length=1)


def _get_processor():
    attr = getattr(current_app, "image_processor", None) or current_app.extensions.get(
        "image_processor"
    )
    if attr is None:
        raise RuntimeError("image processor failed")
    return attr


def _get_level_progress_stats(
    all_images: list[dict[str, Any]],
) -> dict[str, int]:
    _start = time.perf_counter()
    comp_counts = [int(img["comparison_count"]) for img in all_images]
    base_level = min(comp_counts)
    active_nodes = sum(1 for count in comp_counts if count == base_level)
    next_level_count = sum(1 for count in comp_counts if count == base_level + 1)
    stats = get_server_deps().graph.get_graph_stats()
    result = {
        "base_level": base_level,
        "current_target": base_level + 1,
        "active_nodes": active_nodes,
        "next_level_count": next_level_count,
        "total_components": stats["total_components"],
        "total_chains": stats["total_chains"],
    }

    return result


@ranking_bp.route("/config", methods=["GET"])
def get_ranking_config():
    _start = time.perf_counter()
    ranking_conf = config["ranking"]
    all_images = get_server_deps().graph.get_all_images()
    seed_percentage = int(ranking_conf["seed_percentage"])
    seed_size = max(1, len(all_images) * seed_percentage // 100)
    result = jsonify(
        {
            "reserve_count": int(ranking_conf["reserve_count"]),
            "parallel_requests": bool(ranking_conf["parallel_requests"]),
            "timeout_ms": int(ranking_conf["timeout_ms"]),
            "seed_size": seed_size,
            "seed_target_comparisons": int(ranking_conf["seed_target_comparisons"]),
            "insertion_target_comparisons": int(
                ranking_conf["insertion_target_comparisons"]
            ),
            "sigma_threshold": float(ranking_conf["sigma_threshold"]),
        }
    )

    return result


@ranking_bp.route("/phases", methods=["GET"])
def get_ranking_phases():
    return jsonify(get_phases())


@ranking_bp.route("/status", methods=["GET"])
def get_status():
    _start = time.perf_counter()
    deps = get_server_deps()
    all_images = deps.graph.get_all_images()
    total = len(all_images)
    if total == 0:
        result = jsonify(
            {
                "total_images": 0,
                "ranked_images": 0,
                "unranked_images": 0,
                "total_comparisons": 0,
                "skipped_comparisons": 0,
                "min_images": 2,
                "current_target": 1,
                "baseline_comparisons": 0,
                "total_components": 0,
                "total_chains": 0,
                "active_nodes": 0,
                "next_level_count": 0,
                "base_level": 0,
            }
        )

        return result

    level_stats = _get_level_progress_stats(all_images)
    ranked = sum(1 for img in all_images if int(img["comparison_count"]) > 0)
    result = jsonify(
        {
            "total_images": total,
            "ranked_images": ranked,
            "unranked_images": total - ranked,
            "total_comparisons": deps.graph.get_total_comparisons(),
            "skipped_comparisons": deps.graph.get_skipped_comparison_count(),
            "min_images": 2,
            "current_target": level_stats["current_target"],
            "baseline_comparisons": level_stats["base_level"],
            "total_components": level_stats["total_components"],
            "total_chains": level_stats["total_chains"],
            "active_nodes": level_stats["active_nodes"],
            "next_level_count": level_stats["next_level_count"],
            "base_level": level_stats["base_level"],
        }
    )

    return result


@ranking_bp.route("/next-pair", methods=["GET"])
def get_next_pair():
    _start = time.perf_counter()
    deps = get_server_deps()
    processor = _get_processor()
    recent_files_ordered: list[str] = []
    if processor:
        with processor.recent_lock:
            recent_files_ordered = list(processor.recent_images)

    total_images = deps.graph.get_image_count()
    if total_images < 2:
        result = (
            jsonify(
                {
                    "error": "Not Enough Images",
                    "message": "At least two valid images are required to start ranking.",
                }
            ),
            400,
        )
        return result

    full_exclude = set(recent_files_ordered)
    pair, phase_index = merge_sort_ranker.select_pair_for_comparison(
        exclude_set=full_exclude,
        crystal_graph=deps.graph,
    )
    logger.debug(f"phase {phase_index}", start_timer=_start)
    if not pair:
        logger.warning("pair not found")
        result = "", 204
        return result

    filename_a, filename_b = pair
    node_a = deps.graph.get_node(filename_a)
    node_b = deps.graph.get_node(filename_b)
    if node_a is None or node_b is None:
        logger.warning(
            f"filename not in node: node a:{node_a} ({filename_a}), node b:{node_b} ({filename_b})"
        )
        result = "", 204
        return result

    if processor:
        with processor.recent_lock:
            processor.recent_images.append(filename_a)
            processor.recent_images.append(filename_b)

    left = describe_image(node_a, deps.graph)
    right = describe_image(node_b, deps.graph)
    pair_payload = describe_pair(node_a, node_b, phase_index, deps.graph)

    response_data = {
        "left": left,
        "right": right,
        "pair": pair_payload,
    }

    result = jsonify(response_data)
    return result


@ranking_bp.route("/reset", methods=["POST"])
def reset_ranking_queue():
    _start = time.perf_counter()
    processor = _get_processor()
    if processor:
        with processor.recent_lock:
            processor.clear_old_cache(force=True)
    result = jsonify({"status": "success", "message": "Ranking queue reset."})
    return result


@ranking_bp.route("/skip", methods=["POST"])
def skip_image():
    _start = time.perf_counter()
    req = SkipRequest.model_validate(request.get_json(silent=True) or {}, strict=False)
    processor = _get_processor()
    if processor and req.filename:
        with processor.recent_lock:
            processor.recent_images.append(req.filename)
    result = jsonify({"status": "ok"})
    return result


@ranking_bp.route("/submit-comparison", methods=["POST"])
def submit_comparison():
    _start = time.perf_counter()
    deps = get_server_deps()
    processor = _get_processor()
    req = SubmitComparisonRequest.model_validate(request.get_json(), strict=False)
    if req.filename_a == req.filename_b:
        result = jsonify({"error": "Cannot compare image to itself"}), 400
        return result
    if req.winner not in (req.filename_a, req.filename_b):
        result = jsonify({"error": "Winner must be one of the images"}), 400
        return result

    recorder = ComparisonRecorder(
        path_syncer=deps.path_resolver,
        graph_service=deps.graph,
    )
    success = recorder.record_comparison(req.filename_a, req.filename_b, req.winner, 1.0, 0)
    if not success:
        result = jsonify({"error": "Failed to record comparison"}), 500
        return result

    processor.clear_old_cache(force=False)

    data_a = deps.graph.get_image(req.filename_a)
    data_b = deps.graph.get_image(req.filename_b)
    if data_a is None or data_b is None:
        result = jsonify({"error": "Image not found"}), 404
        return result

    result = jsonify(
        {
            "ok": True,
            "images": {
                req.filename_a: {
                    "score": round(float(data_a["score"]), 3),
                    "comparison_count": int(data_a["comparison_count"]),
                },
                req.filename_b: {
                    "score": round(float(data_b["score"]), 3),
                    "comparison_count": int(data_b["comparison_count"]),
                },
            },
        }
    )
    return result


@ranking_bp.route("/sync-all", methods=["POST"])
def sync_all_to_json():
    _start = time.perf_counter()
    deps = get_server_deps()
    images = deps.graph.get_all_images()
    all_comparisons = deps.graph.get_all_comparisons()
    count = 0
    errors = 0
    for img in images:
        success = deps.path_resolver.sync_image_metadata_to_json(
            filename=img["filename"],
            score=float(img["score"]),
            rating_mu=float(img["rating_mu"]),
            rating_sigma=float(img["rating_sigma"]),
            comparison_count=int(img["comparison_count"]),
            all_comparisons=all_comparisons,
        )
        if success:
            count += 1
        else:
            errors += 1
    result = jsonify(
        {"status": "success", "synced_count": count, "error_count": errors}
    )
    return result


def register_ranking_routes(app, deps: ServerDeps) -> None:
    app.extensions["server_deps"] = deps
    app.register_blueprint(ranking_bp)
