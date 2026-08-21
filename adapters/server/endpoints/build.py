"""Build API - endpoints for the data preparation pipeline.

Every route is one call to the CLI command function it maps to (§1.1),
with log output captured for the response.
"""

from typing import Any

from flask import Blueprint, Flask, jsonify, request

from ....core.observability.logger import capture_log_output, get_logger, ModuleLogger
from ....core.utilities.helpers import delete_full_vectors
from ...cli.commands.vectors import run_all, run_full_vectors, run_split_vectors
from ..deps import ServerDeps, get_server_deps

build_bp = Blueprint("build", __name__, url_prefix="/api/build")
logger: ModuleLogger = get_logger(__name__)

_PREPARE_MODES = ("split", "full", "all")


@build_bp.route("/prepare", methods=["POST"])
def prepare():
    data: dict[str, Any] = request.get_json() or {}
    mode = data.get("mode", "all")
    if mode not in _PREPARE_MODES:
        return jsonify({"error": f"Unknown mode: {mode}"}), 400
    limit = int(data.get("limit", 0))
    batch = bool(data.get("batch", False))
    deps = get_server_deps()
    with capture_log_output() as lines:
        if mode == "split":
            code = run_split_vectors(limit=limit, batch=batch, deps=deps.to_cli_deps())
        elif mode == "full":
            code = run_full_vectors(deps=deps.to_cli_deps())
        else:
            code = run_all(limit=limit, batch=batch, deps=deps.to_cli_deps())
    return jsonify({"status": "done", "result": code, "log": lines})


@build_bp.route("/delete-vectors", methods=["POST"])
def delete_vectors():
    """Delete the full vector files and all split categories except image/."""
    with capture_log_output() as lines:
        delete_full_vectors()
    return jsonify(
        {
            "status": "done",
            "result": {
                "type": "delete_vectors",
                "message": "Full vector files and splits removed (image/ kept)",
            },
            "log": lines,
        }
    )


def register_build_routes(app: Flask, deps: ServerDeps) -> None:
    app.extensions["server_deps"] = deps
    app.register_blueprint(build_bp)