from typing import Any
from ....core.observability.logger import (
    get_logger,
    ModuleLogger,
    configure_package_logging,
)

logger: ModuleLogger = get_logger(__name__)


def run_server(host: str = "0.0.0.0", port: int = 5001, **kwargs: Any) -> int:
    from ....infrastructure.persistence.database import init_database

    init_database()
    from ...server.main import app, init_ranking_system
    import os

    should_init = True
    if kwargs.get("debug") and (
        "WERKZEUG_RUN_MAIN" not in os.environ
        or os.environ["WERKZEUG_RUN_MAIN"] != "true"
    ):
        should_init = False

    if should_init:
        init_ranking_system()

    debug = kwargs.get("debug", False)
    configure_package_logging(10 if debug else 20)
    app.run(host=host, port=port, debug=debug)
    return 0
