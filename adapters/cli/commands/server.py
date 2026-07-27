from typing import Any


def run_server(host: str, port: int, **kwargs: Any) -> int:
    from comfyui_image_scorer.infrastructure.persistence.database import init_database

    init_database()
    return 0