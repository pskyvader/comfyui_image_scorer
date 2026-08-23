"""General test for comfyui_image_scorer — covers the whole module.

**Agent guidance:** this is the general suite. Run it ONLY when the user
explicitly prompts for it. For routine verification of a change, run only
the colocated tests next to the module under change
(e.g. `pytest domain/graph/tests`).

Tiers:
- default run: Tier 0 (structural parity, dynamic discovery, dry-run guard)
  + Tier 1 (fakes: stub deps through both CLI functions and endpoints).
- `pytest -m realdata`: Tier 2 (live server smoke) + Tier 3 (real endpoints,
  destructive: removes then rebuilds a limit=100 subset of the real dataset,
  ~30-45 min).

Rule notes:
- plan §0.5 was amended 2026-08-22 to permit new test files; this file is
  the sanctioned general/architecture test.
- "tests use fakes, not real infrastructure": Tiers 2-3 use the real dataset
  through the live server by explicit user request.
"""

from __future__ import annotations

import inspect
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest
from flask import Flask

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT.parent))

from comfyui_image_scorer.core.filesystem.paths import (  # noqa: E402
    maps_dir,
    scores_file,
    split_dir,
    vectors_file,
)

# Endpoint -> (CLI command path, function-name tokens expected in the body).
CONTRACT: list[tuple[str, tuple[str, ...], set[str]]] = [
    ("/api/training/train", ("training", "train-model"), {"train_model"}),
    ("/api/training/hpo", ("training", "hpo"), {"run_hpo"}),
    ("/api/build/prepare", ("build", "all"), {"run_all", "run_split_vectors", "run_full_vectors"}),
    ("/api/build/delete-vectors", ("files", "remove", "vectors"), {"delete_full_vectors"}),
    ("/api/database/rebuild-db", ("database", "rebuild"), {"rebuild"}),
    ("/api/database/recalculate", ("database", "recalculate"), {"recalculate"}),
    ("/api/database/cleanup", ("database", "cleanup"), {"cleanup"}),
    (
        "/api/files/remove-generated-models",
        ("files", "remove", "generated-models"),
        {"remove_models"},
    ),
    (
        "/api/files/remove-vector-maps",
        ("files", "remove", "vector-maps"),
        {"remove_directory"},
    ),
    (
        "/api/files/remove-downloaded-models",
        ("files", "remove", "downloaded-models"),
        {"remove_directory"},
    ),
    (
        "/api/files/download-models",
        ("files", "download", "models"),
        {"download_configured_models", "download_mediapipe_models"},
    ),
    (
        "/api/files/cleanup",
        ("files", "cleanup"),
        {"deduplicate_scored", "cleanup_orphans"},
    ),
    ("/api/analyze/stats", ("analyze", "stats"), {"run_stats"}),
    ("/api/analyze/analyze-parameters", ("analyze", "parameters"), {"run_parameter_analysis"}),
    ("/api/analyze/analyze-matrix", ("analyze", "matrix"), {"run_matrix_analysis"}),
]

# CLI commands without their own endpoint (reachable only through another
# command's pipeline), plus the server frontend command.
NO_ENDPOINT_COMMANDS = {("build", "scores"), ("server",)}

# Additional commands served by /api/build/prepare via its mode parameter.
PREPARE_MODES_COMMANDS = {("build", "split-vectors"), ("build", "full-vectors")}

# Blueprints outside the command/endpoint parity contract (interactive only).
OUT_OF_SCOPE_PREFIXES = ("/api/ranking", "/api/gallery", "/api/maps")

SHORT_TIMEOUT = 120
LONG_TIMEOUT = 600


class _TreeRecorder:
    """Stand-in for argparse parser objects that records the command tree."""

    def __init__(self, path: tuple[str, ...] = ()) -> None:
        self.path = path
        self.children: list[tuple[str, _TreeRecorder]] = []

    def add_parser(self, name: str, **_: Any) -> _TreeRecorder:
        child = _TreeRecorder(self.path + (name,))
        self.children.append((name, child))
        return child

    def add_subparsers(self, **_: Any) -> _TreeRecorder:
        return self

    def add_argument(self, *_: Any, **__: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# Tier 0 - structural parity, dynamic discovery
# ---------------------------------------------------------------------------


def _cli_leaf_commands() -> set[tuple[str, ...]]:
    from comfyui_image_scorer.adapters.cli import main as cli_main

    recorder = _TreeRecorder()
    cli_main._add_server_parser(recorder)  # type: ignore[reportPrivateUsage]
    cli_main._add_training_parser(recorder)  # type: ignore[reportPrivateUsage]
    cli_main._add_build_parser(recorder)  # type: ignore[reportPrivateUsage]
    cli_main._add_database_parser(recorder)  # type: ignore[reportPrivateUsage]
    cli_main._add_files_parser(recorder)  # type: ignore[reportPrivateUsage]
    cli_main._add_analyze_parser(recorder)  # type: ignore[reportPrivateUsage]

    leaves: set[tuple[str, ...]] = set()

    def walk(node: _TreeRecorder) -> None:
        if not node.children:
            leaves.add(node.path)
            return
        for _name, child in node.children:
            walk(child)

    walk(recorder)
    return leaves


def _make_app(deps: Any):
    from comfyui_image_scorer.adapters.server.endpoints.analyze import (
        register_analyze_routes,  # type: ignore[reportUnknownVariableType]
    )
    from comfyui_image_scorer.adapters.server.endpoints.build import (
        register_build_routes,  # type: ignore[reportUnknownVariableType]
    )
    from comfyui_image_scorer.adapters.server.endpoints.comparison import (
        register_ranking_routes,  # type: ignore[reportUnknownVariableType]
    )
    from comfyui_image_scorer.adapters.server.endpoints.database import (
        register_database_routes,  # type: ignore[reportUnknownVariableType]
    )
    from comfyui_image_scorer.adapters.server.endpoints.files import (
        register_files_routes,  # type: ignore[reportUnknownVariableType]
    )
    from comfyui_image_scorer.adapters.server.endpoints.gallery import (
        register_gallery_routes,  # type: ignore[reportUnknownVariableType]
    )
    from comfyui_image_scorer.adapters.server.endpoints.maps import (
        register_maps_routes,  # type: ignore[reportUnknownVariableType]
    )
    from comfyui_image_scorer.adapters.server.endpoints.training import (
        register_training_routes,  # type: ignore[reportUnknownVariableType]
    )

    app = Flask(__name__)
    register_ranking_routes(app, deps)
    register_gallery_routes(app, deps)
    register_maps_routes(app, deps)
    register_database_routes(app, deps)
    register_build_routes(app, deps)
    register_training_routes(app, deps)
    register_analyze_routes(app, deps)
    register_files_routes(app, deps)
    return app


def _api_rules(app: Flask) -> list[tuple[str, str, set[str]]]:
    rules: list[tuple[str, str, set[str]]] = []
    for rule in app.url_map.iter_rules():  # type: ignore[reportUnknownMemberType]
        rules.append((rule.rule, rule.endpoint, set(rule.methods)))  # type: ignore[reportUnknownMemberType, reportArgumentType]
    return rules


def test_cli_command_tree_matches_contract():
    leaves = _cli_leaf_commands()
    expected = (
        NO_ENDPOINT_COMMANDS
        | PREPARE_MODES_COMMANDS
        | {path for _route, path, _fns in CONTRACT}
    )
    assert leaves == expected


def test_endpoint_rules_match_contract():
    deps = _make_fake_deps()
    app = _make_app(deps)
    rules = {rule: methods for rule, _endpoint, methods in _api_rules(app)}

    expected_routes = {route for route, _path, _fns in CONTRACT}
    assert expected_routes <= set(rules)

    for route, methods in rules.items():
        if route == "/api/<path:path>" or route == "/static/<path:filename>":
            continue
        if route.startswith(OUT_OF_SCOPE_PREFIXES):
            continue
        assert route in expected_routes, f"orphan API route: {route}"
        expected_methods = {"GET"} if route == "/api/analyze/stats" else {"POST"}
        assert methods & expected_methods, f"{route} lacks {expected_methods}"


def test_endpoint_bodies_are_single_calls():
    deps = _make_fake_deps()
    app = _make_app(deps)
    view_functions = app.view_functions

    for route, _path, tokens in CONTRACT:
        for rule in app.url_map.iter_rules():  # type: ignore[reportUnknownMemberType]
            if rule.rule != route:  # type: ignore[reportUnknownMemberType]
                continue
            view = view_functions[rule.endpoint]  # type: ignore[reportUnknownMemberType]
            source = inspect.getsource(view)
            assert "capture_log_output" in source, f"{route}: missing log capture"
            for token in tokens:
                assert token in source, f"{route}: missing call {token}"


def test_no_dry_run_references():
    pattern = re.compile(r"dry[_\-]?run|dryRun", re.IGNORECASE)
    ignored = {".git", "output", "comfyui_image_scorer_old", "__pycache__"}
    extensions = {".py", ".js", ".html", ".md"}
    offenders: list[str] = []
    for path in MODULE_ROOT.rglob("*"):
        if any(part in ignored for part in path.parts):
            continue
        if path == Path(__file__):
            continue
        if not path.is_file() or path.suffix not in extensions:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pattern.search(text):
            offenders.append(str(path.relative_to(MODULE_ROOT)))
    assert not offenders, f"dry-run references found: {offenders}"


# ---------------------------------------------------------------------------
# Tier 1 - fakes
# ---------------------------------------------------------------------------


class Recorder:
    def __init__(self, result: int = 0) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self._result = result

    def __call__(self, *args: Any, **kwargs: Any) -> int:
        self.calls.append((args, kwargs))
        return self._result


class StubImageRepo:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_all_images(self) -> list[dict[str, Any]]:
        self.calls.append("get_all_images")
        return [
            {
                "filename": "stub.png",
                "score": 0.5,
                "rating_mu": 25.0,
                "rating_sigma": 8.0,
                "comparison_count": 0,
            }
        ]

    def reset_all_image_ratings(self, **_: Any) -> bool:
        self.calls.append("reset_all_image_ratings")
        return True

    def update_image_rating_state(self, **_: Any) -> bool:
        self.calls.append("update_image_rating_state")
        return True


class StubComparisonRepo:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_all_comparisons(self) -> list[dict[str, Any]]:
        self.calls.append("get_all_comparisons")
        return []

    def clean_comparisons(self, **_: Any) -> int:
        self.calls.append("clean_comparisons")
        return 0


class FakeDeps:
    """Stub dependency container shaped like both CLIDeps and ServerDeps."""

    def __init__(self) -> None:
        from comfyui_image_scorer.adapters.cli.deps import CLIDeps

        self.image_repo = StubImageRepo()
        self.comparison_repo = StubComparisonRepo()
        self.processor: Any = SimpleNamespace(
            rebuild_database_from_ranked=Recorder()
        )
        self.model_loader: Any = None
        self.batch_sizer_factory: Any = None
        self.maps_provider: Any = None
        self.training_loader: Any = None
        self.model_trainer: Any = None
        self.vacuum_database = Recorder()
        self.deduplicate_scored = Recorder()
        self.cleanup_orphans = Recorder()
        self.download_configured_models = Recorder()
        self.download_mediapipe_models = Recorder()
        self.path_resolver: Any = None
        self.graph: Any = None
        self._cli_deps = CLIDeps(
            image_repo=self.image_repo,
            comparison_repo=self.comparison_repo,
            processor=self.processor,  # type: ignore[arg-type]
            model_loader=self.model_loader,  # type: ignore[arg-type]
            batch_sizer_factory=self.batch_sizer_factory,  # type: ignore[arg-type]
            maps_provider=self.maps_provider,  # type: ignore[arg-type]
            training_loader=self.training_loader,
            model_trainer=self.model_trainer,
            vacuum_database=self.vacuum_database,
            deduplicate_scored=self.deduplicate_scored,
            cleanup_orphans=self.cleanup_orphans,
            download_configured_models=self.download_configured_models,
            download_mediapipe_models=self.download_mediapipe_models,
        )

    def to_cli_deps(self):
        return self._cli_deps


def _make_fake_deps() -> FakeDeps:
    return FakeDeps()


def test_cli_database_commands_with_fake_deps():
    from comfyui_image_scorer.adapters.cli.commands.database import (
        cleanup,
        rebuild,
        recalculate,
    )

    deps = _make_fake_deps()
    cli = deps.to_cli_deps()
    assert cleanup(cli) == 0
    assert deps.comparison_repo.calls.count("clean_comparisons") == 1
    assert len(deps.vacuum_database.calls) == 1

    assert rebuild(cli) == 0
    assert len(deps.processor.rebuild_database_from_ranked.calls) == 1

    assert recalculate(cli) == 0
    assert deps.image_repo.calls.count("reset_all_image_ratings") == 1


@pytest.mark.parametrize(
    ("method", "route", "body"),
    [
        ("POST", "/api/database/rebuild-db", None),
        ("POST", "/api/database/recalculate", None),
        ("POST", "/api/database/cleanup", None),
        ("POST", "/api/files/cleanup", {"limit": 3}),
        ("POST", "/api/files/download-models", None),
        ("GET", "/api/analyze/stats", None),
    ],
)
def test_endpoints_with_fake_deps(
    method: str, route: str, body: dict[str, Any] | None
):
    deps = _make_fake_deps()
    app = _make_app(deps)
    client = app.test_client()
    response = client.open(route, method=method, json=body)
    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["status"] == "done"
    assert "result" in payload
    assert isinstance(payload["log"], list)

    if route == "/api/files/cleanup":
        assert deps.deduplicate_scored.calls == [((), {"root": None, "limit": 3})]
        assert deps.cleanup_orphans.calls == [((), {"root": None})]
    elif route == "/api/files/download-models":
        assert len(deps.download_configured_models.calls) == 1
        assert len(deps.download_mediapipe_models.calls) == 1
    elif route == "/api/database/rebuild-db":
        assert len(deps.processor.rebuild_database_from_ranked.calls) == 1
    elif route == "/api/database/cleanup":
        assert deps.comparison_repo.calls.count("clean_comparisons") == 1
        assert len(deps.vacuum_database.calls) == 1
    elif route == "/api/database/recalculate":
        assert deps.image_repo.calls.count("reset_all_image_ratings") == 1


# ---------------------------------------------------------------------------
# Tiers 2-3 - live server (pytest -m realdata)
# ---------------------------------------------------------------------------


def _start_server(port: int) -> tuple[subprocess.Popen[Any], Path]:
    log_path = Path(tempfile.mkstemp(prefix=f"scorer_{port}_", suffix=".log")[1])
    proc = subprocess.Popen(
        [
            sys.executable,
            "scorer.py",
            "server",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(MODULE_ROOT),
        stdout=log_path.open("w"),
        stderr=subprocess.STDOUT,
    )
    return proc, log_path


def _wait_ready(base: str, timeout: int) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/", timeout=5) as resp:
                if resp.status == 200:
                    return
        except OSError:
            pass
        time.sleep(2)
    raise AssertionError(f"server not ready within {timeout}s on {base}")


def _stop_server(proc: subprocess.Popen[Any]) -> None:
    if proc.poll() is None:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
        )


def _log_tail(log_path: Path, n: int = 25) -> str:
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except OSError:
        return "<no server log>"


def _request(
    base: str, method: str, path: str, body: dict[str, Any] | None, timeout: int
) -> tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except OSError as e:
        raise AssertionError(f"{method} {path} failed: {e}") from e


def _assert_absent(path: Path) -> None:
    assert not path.exists(), f"expected removed: {path}"


def _assert_present(path: Path) -> None:
    assert path.exists(), f"expected present: {path}"


def _check_maps_removed() -> None:
    _assert_absent(Path(maps_dir))
    _assert_absent(Path(split_dir) / "map")


def _check_vectors_removed() -> None:
    _assert_absent(Path(vectors_file))
    _assert_absent(Path(split_dir) / "float")
    _assert_present(Path(split_dir) / "image")


def _check_vectors_rebuilt() -> None:
    _assert_present(Path(vectors_file))
    _assert_present(Path(scores_file))


@pytest.mark.realdata
def test_live_server_smoke():
    port = 8321
    proc, log_path = _start_server(port)
    try:
        base = f"http://127.0.0.1:{port}"
        _wait_ready(base, timeout=SHORT_TIMEOUT)
        req = urllib.request.Request(base + "/", method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
            assert resp.status == 200
    except AssertionError as e:
        raise AssertionError(f"{e}\n--- server log tail ---\n{_log_tail(log_path)}") from e
    finally:
        _stop_server(proc)


@pytest.mark.realdata
def test_real_data_pipeline():
    """Runs every command endpoint against the real dataset, in the
    dependency order: removes -> downloads -> build (limit=100 subset) ->
    train -> hpo -> analyze -> database -> cleanup. Destructive."""
    port = 8322
    proc, log_path = _start_server(port)
    try:
        base = f"http://127.0.0.1:{port}"
        _wait_ready(base, timeout=SHORT_TIMEOUT)

        steps: list[tuple[str, str, str, dict[str, Any] | None, bool, Callable[[], None] | None]] = [
            ("remove-generated-models", "POST", "/api/files/remove-generated-models", None, False, None),
            ("remove-vector-maps", "POST", "/api/files/remove-vector-maps", None, False, _check_maps_removed),
            ("remove-downloaded-models", "POST", "/api/files/remove-downloaded-models", None, False, None),
            ("delete-vectors", "POST", "/api/build/delete-vectors", None, False, _check_vectors_removed),
            ("download-models", "POST", "/api/files/download-models", None, True, None),
            ("build-all-100", "POST", "/api/build/prepare", {"mode": "all", "limit": 100, "batch": False}, True, _check_vectors_rebuilt),
            ("train-model", "POST", "/api/training/train", None, True, None),
            ("hpo", "POST", "/api/training/hpo", {"cycles": 2, "optimization_steps": 2, "max_combos": 2}, True, None),
            ("analyze-parameters", "POST", "/api/analyze/analyze-parameters", None, True, None),
            ("analyze-matrix", "POST", "/api/analyze/analyze-matrix", None, True, None),
            ("db-cleanup", "POST", "/api/database/cleanup", None, True, None),
            ("db-rebuild", "POST", "/api/database/rebuild-db", None, True, None),
            ("db-recalculate", "POST", "/api/database/recalculate", None, True, None),
            ("stats", "GET", "/api/analyze/stats", None, False, None),
            ("files-cleanup", "POST", "/api/files/cleanup", {"limit": 100}, True, None),
        ]

        try:
            for name, method, path, body, long, check in steps:
                timeout = LONG_TIMEOUT if long else SHORT_TIMEOUT
                status: int
                payload: Any
                status, payload = _request(base, method, path, body, timeout=timeout)
                assert status == 200, f"{name}: HTTP {status}: {payload}"
                assert payload.get("status") == "done", f"{name}: {payload}"
                if check:
                    check()
        except AssertionError as e:
            raise AssertionError(f"{e}\n--- server log tail ---\n{_log_tail(log_path)}") from e
    finally:
        _stop_server(proc)