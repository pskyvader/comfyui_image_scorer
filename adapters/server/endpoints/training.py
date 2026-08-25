"""Training API - endpoints for model training and HPO.

Every route is one call to the CLI command function it maps to (§1.1),
with log output captured for the response.
"""

from flask import Blueprint, Flask, jsonify, request

from pydantic import BaseModel, Field

from ....core.observability.logger import capture_log_output, get_logger, ModuleLogger
from ...cli.commands.training import run_hpo, train_model
from ..deps import ServerDeps, get_server_deps


class HpoRequest(BaseModel):
    """Payload for POST /api/training/hpo; None fields fall back to config defaults."""

    cycles: int | None = Field(default=None, ge=1)
    optimization_steps: int | None = Field(default=None, ge=1)
    max_combos: int | None = Field(default=None, ge=1)


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
    req = HpoRequest.model_validate(request.get_json(silent=True) or {}, strict=False)
    with capture_log_output() as lines:
        code = run_hpo(
            deps=deps.to_cli_deps(),
            cycles=req.cycles,
            optimization_steps=req.optimization_steps,
            max_combos=req.max_combos,
        )
    return jsonify({"status": "done", "result": code, "log": lines})


def register_training_routes(app: Flask, deps: ServerDeps) -> None:
    app.extensions["server_deps"] = deps
    app.register_blueprint(training_bp)