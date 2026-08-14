"""Database endpoints - API routes for maintenance and file operations."""

from pathlib import Path
from typing import Any

from flask import Blueprint, Flask, jsonify, request, current_app

from ....core.observability.logger import get_logger, ModuleLogger
from ....core.filesystem.paths import image_root_processed
from ..tasks import start_task, get_task_status, set_task_output
from ..deps import ServerDeps, get_server_deps

logger: ModuleLogger = get_logger(__name__)
database_bp = Blueprint("database", __name__, url_prefix="/api/database")


def _get_processor():
    return getattr(current_app, "image_processor", None) or current_app.extensions.get(
        "image_processor"
    )


@database_bp.route("/status", methods=["GET"])
def get_status():
    deps = get_server_deps()
    result = jsonify(
        {
            "status": "ok",
            "images": deps.image_repo.get_image_count(),
            "comparisons": deps.comparison_repo.get_total_comparisons(),
        }
    )
    return result


@database_bp.route("/normalize-comparisons", methods=["POST"])
def normalize():
    deps = get_server_deps()
    try:
        stats = deps.comparison_repo.clean_comparisons()
        deps.graph.rebuild_from_database()
        result = jsonify({"status": "success", "stats": stats})
        return result
    except Exception as exc:
        result = jsonify({"status": "error", "message": str(exc)}), 500
        return result


@database_bp.route("/rebuild-db", methods=["POST"])
def rebuild_database():
    deps = get_server_deps()
    processor = _get_processor()
    if processor is None:
        return (
            jsonify({"status": "error", "error": "Image processor not available"}),
            500,
        )

    def _run(tid: str):
        processor.rebuild_database_from_ranked()
        deps.graph.rebuild_from_database()
        set_task_output(
            tid,
            {
                "status": "done",
            },
        )

    _, body = start_task(_run, task_prefix="rebuild", args=())
    return jsonify(body)


@database_bp.route("/sync-all", methods=["POST"])
def sync_all():
    deps = get_server_deps()

    def _run(tid: str):
        _deps = deps
        images = _deps.image_repo.get_all_images()
        all_comparisons = _deps.comparison_repo.get_all_comparisons()
        count = 0
        errors = 0
        total = len(images)
        print(f"Syncing {total} images...")
        for img in images:
            ok = _deps.path_resolver.sync_image_metadata_to_json(
                filename=img["filename"],
                score=float(img["score"]),
                rating_mu=float(img["rating_mu"]),
                rating_sigma=float(img["rating_sigma"]),
                comparison_count=int(img["comparison_count"]),
                all_comparisons=all_comparisons,
            )
            if ok:
                count += 1
            else:
                errors += 1
            print(
                f"[{count + errors}/{total}] {img['filename']} {'OK' if ok else 'FAIL'}"
            )
        print(f"Done: {count} synced, {errors} errors")
        set_task_output(
            tid,
            {
                "status": "done",
                "result": {"synced_count": count, "error_count": errors},
            },
        )

    _, body = start_task(_run, task_prefix="sync", args=())
    return jsonify(body)


@database_bp.route("/cleanup-orphans", methods=["POST"])
def run_cleanup_orphans():
    deps = get_server_deps()
    data: dict[str, Any] = request.json if isinstance(request.json, dict) else {}
    dry_run: bool = bool(data.get("dry_run", True))
    try:
        result = deps.cleanup_orphans(
            root=None, dry_run=dry_run, delete_enabled=not dry_run
        )
        result = jsonify({"status": "success", "result": result})
        return result
    except Exception as exc:
        result = jsonify({"status": "error", "message": str(exc)}), 500
        return result


@database_bp.route("/deduplicate", methods=["POST"])
def run_deduplicate():
    deps = get_server_deps()
    data: dict[str, Any] = request.json if isinstance(request.json, dict) else {}
    dry_run: bool = bool(data.get("dry_run", True))
    limit: int = int(data.get("limit", 0))
    try:
        result = deps.deduplicate_scored(
            root=Path(image_root_processed), dry_run=dry_run, limit=limit
        )
        result = jsonify({"status": "success", "result": result})
        return result
    except Exception as exc:
        result = jsonify({"status": "error", "message": str(exc)}), 500
        return result


@database_bp.route("/task/<task_id>", methods=["GET"])
def get_task(task_id: str):
    since = request.args.get("since", 0, type=int)
    info = get_task_status(task_id, since=since)
    if info is None:
        result = jsonify({"error": "Task not found"}), 404
        return result
    result = jsonify(info)
    return result


def register_database_routes(app: Flask, deps: ServerDeps) -> None:
    app.extensions["server_deps"] = deps
    app.register_blueprint(database_bp)
