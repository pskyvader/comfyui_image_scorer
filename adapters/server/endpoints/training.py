"""Training API - endpoints for model training and HPO.

Every route is one call to the CLI command function it maps to (§1.1),
with log output captured for the response.
"""

from typing import Any

from flask import Blueprint, Flask, jsonify, request

from ....core.observability.logger import capture_log_output, get_logger, ModuleLogger
from ...cli.commands.training import run_hpo, train_model
from ..deps import ServerDeps, get_server_deps

training_bp = Blueprint("training", __name__, url_prefix="/api/training")
logger: ModuleLogger = get_logger(__name__)


@training_bp.route("/train", methods=["POST"])
def train():
    deps = get_server_deps()
    with capture_log_output() as lines:
        code = train_model(deps=deps.to_cli_deps())
    return jsonify({"status": "done", "result": code, "log": lines})


@training_bp.route("/hpo", methods=["POST"])
def hpo():
    deps = get_server_deps()
    data: dict[str, Any] = request.get_json() or {}
    with capture_log_output() as lines:
        code = run_hpo(
            deps=deps.to_cli_deps(),
            cycles=data.get("cycles"),
            optimization_steps=data.get("optimization_steps"),
            max_combos=data.get("max_combos"),
        )
    return jsonify({"status": "done", "result": code, "log": lines})


def register_training_routes(app: Flask, deps: ServerDeps) -> None:
    app.extensions["server_deps"] = deps
    app.register_blueprint(training_bp)