"""Analyze API - endpoints for statistics, parameter analysis, and matrix analysis.

Every route is one call to the function CLI `main.py` runs for that
command (§1.1), with log output captured for the response.
"""

from flask import Blueprint, Flask, jsonify

from ....application.analysis.run_matrix_analysis import run_matrix_analysis
from ....application.analysis.run_parameter_analysis import run_parameter_analysis
from ....application.analysis.run_stats import run_stats
from ....core.observability.logger import capture_log_output, get_logger, ModuleLogger
from ..deps import ServerDeps, get_server_deps

analyze_bp = Blueprint("analyze", __name__, url_prefix="/api/analyze")
logger: ModuleLogger = get_logger(__name__)


@analyze_bp.route("/stats", methods=["GET"])
def stats():
    deps = get_server_deps()
    with capture_log_output() as lines:
        code = run_stats(
            image_repo=deps.image_repo, comparison_repo=deps.comparison_repo
        )
    return jsonify({"status": "done", "result": code, "log": lines})


@analyze_bp.route("/analyze-parameters", methods=["POST"])
def analyze_parameters():
    with capture_log_output() as lines:
        code = run_parameter_analysis()
    return jsonify({"status": "done", "result": code, "log": lines})


@analyze_bp.route("/analyze-matrix", methods=["POST"])
def analyze_matrix():
    with capture_log_output() as lines:
        code = run_matrix_analysis()
    return jsonify({"status": "done", "result": code, "log": lines})


def register_analyze_routes(app: Flask, deps: ServerDeps) -> None:
    app.extensions["server_deps"] = deps
    app.register_blueprint(analyze_bp)