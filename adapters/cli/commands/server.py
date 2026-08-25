"""Server command: boots the Flask ranking server from the CLI."""
import os
import subprocess
import sys
from pathlib import Path

from ....core.observability.logger import (
    get_logger,
    ModuleLogger,
)

logger: ModuleLogger = get_logger(__name__)

_MODULE_ROOT = Path(__file__).resolve().parents[3]
_SERVER_ENTRY = "comfyui_image_scorer.adapters.server.main"


def run_server(host: str, port: int, debug: bool) -> int:
    env = dict(os.environ)
    pypath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(_MODULE_ROOT.parent)] + ([pypath] if pypath else [])
    )

    cmd = [
        sys.executable,
        "-m",
        _SERVER_ENTRY,
        "--host",
        host,
        "--port",
        str(port),
    ]
    if debug:
        cmd.append("--debug")

    logger.info("Starting ranking server (pid %s)...", os.getpid())
    return subprocess.call(cmd, env=env)
