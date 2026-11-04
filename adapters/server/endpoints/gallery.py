"""Gallery API - endpoints for viewing and filtering ranked images."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Flask, jsonify, request

from ....core.observability.logger import get_logger, ModuleLogger
from ....domain.graph.node_proxy import NodeProxy
from ....domain.ports.repository import ImageRow
from ..deps import ServerDeps, get_server_deps

gallery_bp = Blueprint("gallery_v2", __name__, url_prefix="/api/gallery")
logger: ModuleLogger = get_logger(__name__)


def _selected_score(node: NodeProxy, score_type: str) -> float:
    """Score value in the requested form: public, trueskill, or position_score."""
    if score_type == "trueskill":
        return float(node.trueskill_score)
    if score_type == "position_score":
        return float(node.position_score)
    return node.score


@gallery_bp.route("/images", methods=["GET"])
def list_images():
    deps = get_server_deps()
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = request.args.get("per_page", 20, type=int)
    if per_page < 1 or per_page > 100:
        per_page = 20

    nodes = deps.graph.get_all_nodes()
    score_type = request.args.get("score_type", "public").lower()
    score_min = request.args.get("score_min", 0.0, type=float)
    score_max = request.args.get("score_max", 1.0, type=float)
    comparisons_min = request.args.get("comparisons_min", 0, type=int)
    comparisons_max = request.args.get("comparisons_max", 999999, type=int)
    search_mode = request.args.get("search_mode", "both").lower()
    tags_query = request.args.get("tags", "").strip().lower()
    search_tags = [tag.strip() for tag in tags_query.split(",")] if tags_query else []

    filtered_and: list[tuple[float, ImageRow]] = []
    filtered_or: list[tuple[float, ImageRow]] = []
    for node in nodes:
        img = node.data
        score_value = _selected_score(node, score_type)
        if not (score_min <= score_value <= score_max):
            continue
        comp_count = int(img.get("comparison_count", 0))
        if not (comparisons_min <= comp_count <= comparisons_max):
            continue

        if not search_tags:
            filtered_and.append((score_value, img))
            continue

        img_tags = ((img.get("prompt_tags") or "") + " " + img["filename"]).lower()
        if all(tag in img_tags for tag in search_tags):
            filtered_and.append((score_value, img))
        elif search_mode != "and" and any(tag in img_tags for tag in search_tags):
            filtered_or.append((score_value, img))

    sort_by = request.args.get("sort", "score_desc")

    def sort_list(items: list[tuple[float, ImageRow]]) -> None:
        if sort_by == "score_asc":
            items.sort(key=lambda item: item[0])
        elif sort_by == "score_desc":
            items.sort(key=lambda item: item[0], reverse=True)
        elif sort_by == "comparisons_asc":
            items.sort(key=lambda item: int(item[1]["comparison_count"]))
        elif sort_by == "comparisons_desc":
            items.sort(key=lambda item: int(item[1]["comparison_count"]), reverse=True)
        elif sort_by in {"last_compared_desc", "newest"}:
            items.sort(
                key=lambda item: item[1].get("last_compared_at") or "", reverse=True
            )
        elif sort_by == "last_compared_asc":
            items.sort(
                key=lambda item: item[1].get("last_compared_at") or "9999-99-99"
            )

    if search_tags:
        sort_list(filtered_and)
        sort_list(filtered_or)
        filtered = (
            filtered_or
            if search_mode == "or"
            else filtered_and if search_mode == "and" else filtered_and + filtered_or
        )
    else:
        filtered = filtered_and
        sort_list(filtered)

    total = len(filtered)
    offset = (page - 1) * per_page
    paginated = filtered[offset : offset + per_page]
    images = [
        {
            "filename": item[1]["filename"],
            "score": round(item[0], 3),
            "file": f"{item[1]['filename']}?score={round(item[0], 3)}",
            "comparison_count": int(item[1].get("comparison_count", 0)),
            "prompt_tags": item[1].get("prompt_tags"),
        }
        for item in paginated
    ]
    result = jsonify(
        {
            "images": images,
            "total": total,
            "page": page,
            "per_page": per_page,
            "max_comparison_count": max(
                (int(item[1].get("comparison_count", 0)) for item in filtered_and + filtered_or), default=0
            ),
        }
    )
    return result


@gallery_bp.route("/image/<path:filename>", methods=["GET"])
def get_image_info(filename: str):
    node = get_server_deps().graph.get_node(filename)
    if node is None:
        result = jsonify({"error": "Image not found"}), 404
        return result
    result = jsonify(
        {
            "filename": node.filename,
            "score": round(node.score, 4),
            "link_count": node.link_count,
            "last_compared_at": node.last_compared_at,
            "prompt_tags": node.prompt_tags,
        }
    )
    return result


@gallery_bp.route("/history/<path:filename>", methods=["GET"])
def get_image_history(filename: str):
    deps = get_server_deps()
    score_type = request.args.get("score_type", "public").lower()
    wins: list[dict[str, Any]] = []
    losses: list[dict[str, Any]] = []
    for link in deps.graph.get_all_links():
        if link.winner != filename and link.loser != filename:
            continue
        opponent = link.loser if link.winner == filename else link.winner
        opponent_node = deps.graph.get_node(opponent)
        if opponent_node is None:
            opponent_score = 0.5
        else:
            opponent_score = _selected_score(opponent_node, score_type)
        item = {
            "opponent": opponent,
            "opponent_score": opponent_score,
            "timestamp": link.timestamp,
        }
        if link.winner == filename:
            wins.append(item)
        else:
            losses.append(item)

    result = jsonify(
        {
            "filename": filename,
            "wins": wins,
            "losses": losses,
            "total_comparisons": len(wins) + len(losses),
        }
    )
    return result


def register_gallery_routes(app: Flask, deps: ServerDeps) -> None:
    app.extensions["server_deps"] = deps
    app.register_blueprint(gallery_bp)
