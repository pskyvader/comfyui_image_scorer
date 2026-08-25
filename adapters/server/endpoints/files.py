"""Files API - endpoints for file management operations.

Every route body is the exact body CLI `main.py` runs for the matching
`files` command (§1.1).
"""

from pathlib import Path

from flask import Blueprint, Flask, jsonify, request

from pydantic import BaseModel, Field

from ....core.filesystem.paths import maps_dir, mediapipe_models_dir, split_dir
from ....core.observability.logger import capture_log_output, get_logger, ModuleLogger
from ....core.utilities.helpers import remove_directory, remove_models
from ..deps import ServerDeps, get_server_deps


class FilesCleanupRequest(BaseModel):
    """Payload for POST /api/files/cleanup."""

    limit: int = Field(default=0, ge=0)


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
        deps.set_hub_offline(False)
        # #37a: restore the process's offline default even when a download fails
        try:
            deps.download_configured_models()
            deps.download_mediapipe_models()
        finally:
            deps.set_hub_offline(True)
    return jsonify({"status": "done", "result": None, "log": lines})


@files_bp.route("/cleanup", methods=["POST"])
def cleanup():
    req = FilesCleanupRequest.model_validate(
        request.get_json(silent=True) or {}, strict=False
    )
    deps = get_server_deps()
    with capture_log_output() as lines:
        dedup_count = deps.deduplicate_scored(root=None, limit=req.limit)
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