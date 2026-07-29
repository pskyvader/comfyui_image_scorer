from typing import Any


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
    app.run(host=host, port=port, debug=debug)
    return 0
