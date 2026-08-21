"""Database endpoints - API routes for maintenance.

Every route is one call to the CLI command function it maps to (§1.1),
with log output captured for the response.
"""

from flask import Blueprint, Flask, jsonify

from ....core.observability.logger import capture_log_output, get_logger, ModuleLogger
from ...cli.commands.database import cleanup, rebuild, recalculate
from ..deps import ServerDeps, get_server_deps

logger: ModuleLogger = get_logger(__name__)
database_bp = Blueprint("database", __name__, url_prefix="/api/database")


@database_bp.route("/rebuild-db", methods=["POST"])
def rebuild_database():
    deps = get_server_deps()
    with capture_log_output() as lines:
        code = rebuild(deps=deps.to_cli_deps())
    return jsonify({"status": "done", "result": code, "log": lines})


@database_bp.route("/recalculate", methods=["POST"])
def recalculate_ratings():
    deps = get_server_deps()
    with capture_log_output() as lines:
        code = recalculate(deps=deps.to_cli_deps())
    return jsonify({"status": "done", "result": code, "log": lines})


@database_bp.route("/cleanup", methods=["POST"])
def clean_database():
    deps = get_server_deps()
    with capture_log_output() as lines:
        code = cleanup(deps=deps.to_cli_deps())
    return jsonify({"status": "done", "result": code, "log": lines})


def register_database_routes(app: Flask, deps: ServerDeps) -> None:
    app.extensions["server_deps"] = deps
    app.register_blueprint(database_bp)