"""Files API - endpoints for file management operations.

Every route body is the exact body CLI `main.py` runs for the matching
`files` command (§1.1).
"""

import os
from pathlib import Path
from typing import Any

from flask import Blueprint, Flask, jsonify, request

from ....core.filesystem.paths import maps_dir, mediapipe_models_dir, split_dir
from ....core.observability.logger import capture_log_output, get_logger, ModuleLogger
from ....core.utilities.helpers import remove_directory, remove_models
from ..deps import ServerDeps, get_server_deps

files_bp = Blueprint("files", __name__, url_prefix="/api/files")
logger: ModuleLogger = get_logger(__name__)


@files_bp.route("/remove-generated-models", methods=["POST"])
def delete_models():
    with capture_log_output() as lines:
        remove_models()
    return jsonify({"status": "done", "result": None, "log": lines})


@files_bp.route("/remove-vector-maps", methods=["POST"])
def delete_maps():
    with capture_log_output() as lines:
        remove_directory(Path(maps_dir))
        remove_directory(Path(split_dir) / "map")
    return jsonify({"status": "done", "result": None, "log": lines})


@files_bp.route("/remove-downloaded-models", methods=["POST"])
def delete_downloaded_models():
    with capture_log_output() as lines:
        remove_directory(Path(mediapipe_models_dir))
    return jsonify({"status": "done", "result": None, "log": lines})


@files_bp.route("/download-models", methods=["POST"])
def download_models():
    deps = get_server_deps()
    with capture_log_output() as lines:
        os.environ["HF_HUB_OFFLINE"] = "0"
        deps.download_configured_models()
        deps.download_mediapipe_models()
    return jsonify({"status": "done", "result": None, "log": lines})


@files_bp.route("/cleanup", methods=["POST"])
def cleanup():
    data: dict[str, Any] = request.get_json() or {}
    limit = int(data.get("limit") or 0)
    deps = get_server_deps()
    with capture_log_output() as lines:
        dedup_count = deps.deduplicate_scored(root=None, limit=limit)
        logger.info("Duplicates removed: %s", dedup_count)
        orphan_count = deps.cleanup_orphans(root=None)
        logger.info("Orphans cleaned: %s", orphan_count)
    return jsonify(
        {
            "status": "done",
            "result": {"duplicates_removed": dedup_count, "orphans_cleaned": orphan_count},
            "log": lines,
        }
    )


def register_files_routes(app: Flask, deps: ServerDeps) -> None:
    app.extensions["server_deps"] = deps
    app.register_blueprint(files_bp)