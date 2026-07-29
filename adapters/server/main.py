"""Main server - Flask application for ranking system."""

import sys
import threading
import time
import os
from pathlib import Path
from typing import Any, Callable
import argparse
import logging

from flask import Flask, send_from_directory, request, send_file, Response
from urllib.parse import unquote

from ...core.observability.logger import (
    get_logger,
    configure_package_logging,
    SharedLogger,
    set_log_filter_hook,
)
from ...core.configuration.settings import config
from ...core.filesystem.paths import image_root, output_dir
from ...infrastructure.persistence.folder_organizer import ensure_tier_structure
from ...infrastructure.persistence.path_handler import (
    get_ranked_root,
    compute_path_from_filename,
    find_image_path,
)
from ...infrastructure.persistence.images_repository import get_image as get_db_image
from .processor import ImageProcessor

logger = get_logger(__name__)

image_processor = ImageProcessor(max_workers=int(config["ranking"]["max_workers"]))

app = Flask(__name__, static_folder=None)
app.extensions["image_processor"] = image_processor
setattr(app, "image_processor", image_processor)

app.config["JSON_SORT_KEYS"] = False

from .endpoints.comparison import register_ranking_routes
from .endpoints.gallery import register_gallery_routes
from .endpoints.maps import register_maps_routes
from .endpoints.database import register_database_routes
from .endpoints.data_transform import register_data_transform_routes
from .endpoints.training import register_training_routes
from .endpoints.analysis import register_analysis_routes

SECTION_FRONTENDS = {
    "comparison": Path(__file__).parent.parent / "comparison" / "frontend",
    "gallery": Path(__file__).parent.parent / "gallery" / "frontend",
    "maps": Path(__file__).parent.parent / "maps" / "frontend",
    "database": Path(__file__).parent.parent / "database_structure" / "frontend",
    "data": Path(__file__).parent.parent / "data_transform" / "frontend",
    "training": Path(__file__).parent.parent / "training_hyperparameters" / "frontend",
    "analysis": Path(__file__).parent.parent / "analysis" / "frontend",
}

SERVER_FRONTEND = Path(__file__).parent / "frontend"

register_ranking_routes(app)
register_gallery_routes(app)
register_maps_routes(app)
register_database_routes(app)
register_data_transform_routes(app)
register_training_routes(app)
register_analysis_routes(app)


@app.route("/")
def serve_index() -> Response:
    return send_from_directory(str(SERVER_FRONTEND / "html"), "index.html")


@app.route("/css/<path:filename>")
def serve_css(filename: str) -> Response:
    return send_from_directory(str(SERVER_FRONTEND / "css"), filename)


@app.route("/js/<path:filename>")
def serve_js(filename: str) -> Response:
    return send_from_directory(str(SERVER_FRONTEND / "js"), filename)


@app.route("/static/<section>/<path:filename>")
def serve_section_static(section: str, filename: str):
    if section not in SECTION_FRONTENDS:
        return {"error": f"Unknown section: {section}"}, 404
    return send_from_directory(str(SECTION_FRONTENDS[section]), filename)


@app.route("/output/ranked/<path:filepath>")
def serve_ranked_image(filepath: str):
    ranked_root = get_ranked_root()
    filepath_decoded = unquote(filepath)

    direct_path = ranked_root / filepath_decoded
    if direct_path.exists() and direct_path.is_file():
        response = send_file(str(direct_path))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    filename = Path(filepath_decoded).name
    found = find_image_path(filename)
    if found:
        response = send_file(str(Path(found)))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    logger.warning(f"Image not found in ranked folders: {filepath}")
    return {"error": "Image not found"}, 404


@app.route("/images/<path:filename>")
def serve_image_by_name(filename: str):
    ranked_root = get_ranked_root()
    fname = Path(unquote(filename)).name

    score_q = float(request.args["score"]) if "score" in request.args else None

    if score_q is not None:
        dest = compute_path_from_filename(fname, score_q)
        if dest.exists() and dest.is_file():
            return send_file(str(dest))

    db_entry = get_db_image(fname)
    if db_entry and db_entry["score"] is not None:
        dest = compute_path_from_filename(fname, db_entry["score"])
        if dest.exists() and dest.is_file():
            return send_file(str(dest))

    found = find_image_path(fname)
    if found:
        return send_file(str(found))

    return {"error": "Image not found"}, 404


@app.route("/image/<path:filename>")
def serve_image_alias(filename: str) -> Response:
    return serve_image_by_name(filename)


@app.route("/api/<path:path>")
def catch_api_404(path: str):
    return {"error": f"API endpoint not found: /api/{path}"}, 404


@app.route("/<path:filename>")
def serve_html(filename: str) -> Response:
    base_dir = Path(__file__).parent
    return send_from_directory(str(base_dir / "frontend" / "html"), filename)


@app.errorhandler(404)
def not_found(e: Exception):
    return {"error": "Not found"}, 404


@app.errorhandler(500)
def server_error(e: Exception):
    logger.error(f"Server error: {e}")
    return {"error": "Server error"}, 500


scanner_thread: threading.Thread | None = None


def scanner_task(img_root: str) -> None:
    sleep_time = 30
    while True:
        stats = image_processor.process_next_batch(img_root, batch_size=100)
        added = stats["added"]
        if added > 0:
            sleep_time = 30
        else:
            sleep_time *= 2
            sleep_time = min(sleep_time, 600)

        logger.info(f"Added:{added}, Sleeping {sleep_time}s...")
        time.sleep(sleep_time)


def start_background_scanner(img_root: str) -> None:
    global scanner_thread
    if scanner_thread:
        logger.info(f"[SCANNER] Scanner already running. Alive: {scanner_thread.is_alive()}")
        return
    scanner_thread = threading.Thread(target=scanner_task, daemon=True, args=(img_root,))
    scanner_thread.start()
    logger.info("[SCANNER] Global image scanner started.")


def startup_worker() -> None:
    if not ensure_tier_structure():
        return

    scanner_task(str(image_root))


def init_ranking_system() -> bool:
    threading.Thread(
        target=startup_worker, daemon=True
    ).start()
    logger.info("[OK] Background initialization triggered.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Ranking System Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5001, help="Port to bind to (default: 5001)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    configure_package_logging(10 if args.debug else 20)

    should_init = True
    if args.debug and (
        "WERKZEUG_RUN_MAIN" not in os.environ
        or os.environ["WERKZEUG_RUN_MAIN"] != "true"
    ):
        should_init = False

    if should_init:
        if not init_ranking_system():
            return 1

    logger.info(f"Starting ranking server on {args.host}:{args.port}...\n")
    app.run(host=args.host, port=args.port, debug=args.debug)

    return 0


if __name__ == "__main__":
    sys.exit(main())
