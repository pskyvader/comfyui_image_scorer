import os
import shutil
import urllib.request

from ...core.configuration.settings import config
from ...core.filesystem.paths import mediapipe_models_dir
from ...core.observability.logger import get_logger

logger = get_logger(__name__)


def download_mediapipe_models() -> None:
    os.makedirs(mediapipe_models_dir, exist_ok=True)
    for key, model_config in config["prepare"]["attribute_models"].items():
        if "url" not in model_config:
            continue
        dest = os.path.join(mediapipe_models_dir, model_config["name"])
        if os.path.exists(dest):
            logger.info("MediaPipe model '%s' already downloaded", key)
            continue
        _download_to(model_config["url"], dest, key)


def _download_to(url: str, dest: str, key: str) -> None:
    tmp = f"{dest}.part"
    try:
        with urllib.request.urlopen(url, timeout=60) as response, open(tmp, "wb") as out:
            shutil.copyfileobj(response, out)
        os.replace(tmp, dest)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    logger.info("MediaPipe model '%s' downloaded", key)
