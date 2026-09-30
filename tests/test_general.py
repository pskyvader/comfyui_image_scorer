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
from typing import Any, Callable, cast

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
    (
        "/api/build/prepare",
        ("build", "all"),
        {"run_all", "run_split_vectors", "run_full_vectors"},
    ),
    (
        "/api/build/delete-vectors",
        ("files", "remove", "vectors"),
        {"delete_full_vectors"},
    ),
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
    (
        "/api/analyze/analyze-parameters",
        ("analyze", "parameters"),
        {"run_parameter_analysis"},
    ),
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
    # The parser builders are typed against argparse's concrete base classes;
    # the recorder implements the same surface structurally.
    any_recorder = cast(Any, recorder)
    cli_main.add_server_parser(any_recorder)
    cli_main.add_training_parser(any_recorder)
    cli_main.add_build_parser(any_recorder)
    cli_main.add_database_parser(any_recorder)
    cli_main.add_files_parser(any_recorder)
    cli_main.add_analyze_parser(any_recorder)

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
        register_analyze_routes,
    )
    from comfyui_image_scorer.adapters.server.endpoints.build import (
        register_build_routes,
    )
    from comfyui_image_scorer.adapters.server.endpoints.comparison import (
        register_ranking_routes,
    )
    from comfyui_image_scorer.adapters.server.endpoints.database import (
        register_database_routes,
    )
    from comfyui_image_scorer.adapters.server.endpoints.files import (
        register_files_routes,
    )
    from comfyui_image_scorer.adapters.server.endpoints.gallery import (
        register_gallery_routes,
    )
    from comfyui_image_scorer.adapters.server.endpoints.maps import (
        register_maps_routes,
    )
    from comfyui_image_scorer.adapters.server.endpoints.training import (
        register_training_routes,
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
    # Flask ships no stubs, so url_map is unknown. The attribute names are part
    # of Flask's documented public Rule surface.
    url_map = cast(Any, app.url_map)
    for rule in url_map.iter_rules():
        rules.append((rule.rule, rule.endpoint, set(rule.methods)))
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
    url_map = cast(Any, app.url_map)

    for route, _path, tokens in CONTRACT:
        for rule in url_map.iter_rules():
            if rule.rule != route:
                continue
            view = view_functions[rule.endpoint]
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


class StubGraph:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def list_nodes(self) -> list[dict[str, Any]]:
        self.calls.append("list_nodes")
        return [
            {
                "filename": "stub.png",
                "score": 0.5,
                "rating_mu": 25.0,
                "rating_sigma": 8.0,
                "comparison_count": 0,
            }
        ]

    def get_all_nodes(self) -> list[Any]:
        self.calls.append("get_all_nodes")
        return [SimpleNamespace(filename="stub.png", data=self.list_nodes()[0])]

    def get_all_links(self) -> list[Any]:
        self.calls.append("get_all_links")
        return []

    def list_links(self, *_: Any, **__: Any) -> list[dict[str, Any]]:
        self.calls.append("list_links")
        return []

    def clean_comparisons(self, **_: Any) -> int:
        self.calls.append("clean_comparisons")
        return 0

    def reset_all_image_ratings(self, **_: Any) -> bool:
        self.calls.append("reset_all_image_ratings")
        return True

    def update_image_rating_state(self, **_: Any) -> bool:
        self.calls.append("update_image_rating_state")
        return True

    def rebuild_from_database(self) -> None:
        self.calls.append("rebuild_from_database")


class FakeDeps:
    """Stub dependency container shaped like both CLIDeps and ServerDeps."""

    def __init__(self) -> None:
        from comfyui_image_scorer.adapters.cli.deps import CLIDeps

        self.graph: Any = StubGraph()
        self.processor: Any = SimpleNamespace(rebuild_database_from_ranked=Recorder())
        self.model_loader: Any = None
        self.batch_sizer_factory: Any = None
        self.maps_provider: Any = None
        self.training_loader: Any = None
        self.model_trainer: Any = None
        self.cache: Any = StubGraph()  # cache provider stub; never read by these paths
        self.hpo_runner: Any = Recorder()
        self.plot_manager: Any = None
        self.mediapipe: Any = None
        self.vacuum_database: Any = Recorder()
        self.deduplicate_scored: Any = Recorder()
        self.cleanup_orphans: Any = Recorder()
        self.download_configured_models: Any = Recorder()
        self.download_mediapipe_models: Any = Recorder()
        self.set_hub_offline: Any = Recorder()
        self.path_resolver: Any = None
        self._cli_deps = CLIDeps(
            processor=self.processor,
            graph=self.graph,
            model_loader=self.model_loader,
            batch_sizer_factory=self.batch_sizer_factory,
            maps_provider=self.maps_provider,
            training_loader=self.training_loader,
            model_trainer=self.model_trainer,
            cache=self.cache,
            hpo_runner=self.hpo_runner,
            plot_manager=self.plot_manager,
            mediapipe=self.mediapipe,
            vacuum_database=self.vacuum_database,
            deduplicate_scored=self.deduplicate_scored,
            cleanup_orphans=self.cleanup_orphans,
            download_configured_models=self.download_configured_models,
            download_mediapipe_models=self.download_mediapipe_models,
            set_hub_offline=self.set_hub_offline,
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
    assert deps.graph.calls.count("clean_comparisons") == 1
    assert len(deps.vacuum_database.calls) == 1

    assert rebuild(cli) == 0
    assert len(deps.processor.rebuild_database_from_ranked.calls) == 1

    assert recalculate(cli) == 0
    assert deps.graph.calls.count("reset_all_image_ratings") == 1


@pytest.mark.parametrize(
    ("method", "route", "body"),
    [
        ("POST", "/api/database/rebuild-db", None),
        ("POST", "/api/database/recalculate", None),
        ("POST", "/api/database/cleanup", None),
        ("POST", "/api/files/cleanup", None),
        ("POST", "/api/files/download-models", None),
        ("GET", "/api/analyze/stats", None),
    ],
)
def test_endpoints_with_fake_deps(method: str, route: str, body: dict[str, Any] | None):
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
        assert deps.deduplicate_scored.calls == [((), {"root": None})]
        assert deps.cleanup_orphans.calls == [((), {"root": None})]
    elif route == "/api/files/download-models":
        assert len(deps.download_configured_models.calls) == 1
        assert len(deps.download_mediapipe_models.calls) == 1
    elif route == "/api/database/rebuild-db":
        assert len(deps.processor.rebuild_database_from_ranked.calls) == 1
    elif route == "/api/database/cleanup":
        assert deps.graph.calls.count("clean_comparisons") == 1
        assert len(deps.vacuum_database.calls) == 1
    elif route == "/api/database/recalculate":
        assert deps.graph.calls.count("reset_all_image_ratings") == 1


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


def _preview(payload: Any, limit: int = 2000) -> str:
    text = payload if isinstance(payload, str) else json.dumps(payload, default=str)
    if len(text) > limit:
        return f"{text[:limit]}... <truncated, {len(text)} chars total>"
    return text


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


def test_live_server_smoke():
    port = 8321
    print(f"\n=== live-server-smoke: starting server on {port} ===", flush=True)
    proc, log_path = _start_server(port)
    print(f"server log: {log_path}", flush=True)
    try:
        base = f"http://127.0.0.1:{port}"
        _wait_ready(base, timeout=SHORT_TIMEOUT)
        print("server ready; GET /", flush=True)
        req = urllib.request.Request(base + "/", method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
            assert resp.status == 200
        print("=== live-server-smoke: OK (GET / -> 200) ===\n", flush=True)
    except AssertionError as e:
        raise AssertionError(
            f"{e}\n--- server log tail ---\n{_log_tail(log_path)}"
        ) from e
    finally:
        _stop_server(proc)
        print(f"=== live-server-smoke: server stopped ===\n", flush=True)


@pytest.mark.realdata
def test_real_data_pipeline():
    """Runs every command endpoint against the real dataset, grouped by
    section: files (strip, dedup, download) -> database (cleanup/rebuild/
    recalculate on the stripped tree) -> build (limit=100 subset) ->
    training -> analyze. Destructive."""
    port = 8322
    print(f"\n{'=' * 70}\n=== real-data-pipeline: starting server on {port} ===", flush=True)
    proc, log_path = _start_server(port)
    print(f"server log: {log_path}", flush=True)
    started = time.time()
    try:
        base = f"http://127.0.0.1:{port}"
        _wait_ready(base, timeout=SHORT_TIMEOUT)
        print(f"server ready after {time.time() - started:.1f}s", flush=True)

        steps: list[
            tuple[str, str, str, dict[str, Any] | None, bool, Callable[[], None] | None]
        ] = [
            (
                "remove-generated-models",
                "POST",
                "/api/files/remove-generated-models",
                None,
                False,
                None,
            ),
            (
                "remove-vector-maps",
                "POST",
                "/api/files/remove-vector-maps",
                None,
                False,
                _check_maps_removed,
            ),
            (
                "remove-downloaded-models",
                "POST",
                "/api/files/remove-downloaded-models",
                None,
                False,
                None,
            ),
            (
                "delete-vectors",
                "POST",
                "/api/build/delete-vectors",
                None,
                False,
                _check_vectors_removed,
            ),
            ("files-cleanup", "POST", "/api/files/cleanup", None, True, None),
            ("download-models", "POST", "/api/files/download-models", None, True, None),
            ("db-cleanup", "POST", "/api/database/cleanup", None, True, None),
            ("db-rebuild", "POST", "/api/database/rebuild-db", None, True, None),
            ("db-recalculate", "POST", "/api/database/recalculate", None, True, None),
            (
                "build-all-100",
                "POST",
                "/api/build/prepare",
                {"mode": "all", "limit": 100, "batch": False},
                True,
                _check_vectors_rebuilt,
            ),
            ("train-model", "POST", "/api/training/train", None, True, None),
            (
                "hpo",
                "POST",
                "/api/training/hpo",
                {"cycles": 2, "optimization_steps": 2, "max_combos": 2},
                True,
                None,
            ),
            (
                "analyze-parameters",
                "POST",
                "/api/analyze/analyze-parameters",
                None,
                True,
                None,
            ),
            ("analyze-matrix", "POST", "/api/analyze/analyze-matrix", None, True, None),
            ("stats", "GET", "/api/analyze/stats", None, False, None),
        ]

        failure: str | None = None
        attempted = 0
        for index, (name, method, path, body, long, check) in enumerate(steps, start=1):
            attempted = index
            timeout = LONG_TIMEOUT if long else SHORT_TIMEOUT
            step_start = time.time()
            print(
                f"\n--- step {index}/{len(steps)} START {name}: "
                f"{method} {path} body={_preview(body, 500)} "
                f"(timeout {timeout}s) ---",
                flush=True,
            )
            try:
                status: int
                payload: Any
                status, payload = _request(base, method, path, body, timeout=timeout)
                elapsed = time.time() - step_start
                print(
                    f"--- step {index}/{len(steps)} RESPONSE {name}: "
                    f"HTTP {status} in {elapsed:.1f}s :: {_preview(payload)} ---",
                    flush=True,
                )
                if status != 200:
                    raise AssertionError(f"HTTP {status}: {payload}")
                if payload.get("status") != "done":
                    raise AssertionError(f"unexpected payload: {payload}")
                if check:
                    check()
            except AssertionError as e:
                failure = f"{name}: {e}"
                print(
                    f"--- step {index}/{len(steps)} FAILED {name} after "
                    f"{time.time() - step_start:.1f}s -- stopping remaining steps ---",
                    flush=True,
                )
                break
            print(
                f"--- step {index}/{len(steps)} OK {name} "
                f"(total {time.time() - started:.1f}s) ---",
                flush=True,
            )

        if failure is not None:
            skipped = [s[0] for s in steps[attempted:]]
            skipped_text = ", ".join(skipped) if skipped else "<none>"
            print(
                f"\n=== real-data-pipeline: FAILED after "
                f"{time.time() - started:.1f}s ===\n"
                f"--- skipped {len(skipped)} step(s): {skipped_text} ---\n"
                f"--- server log tail ---\n{_log_tail(log_path, n=200)}\n",
                flush=True,
            )
            raise AssertionError(
                f"{failure}\n"
                f"--- skipped {len(skipped)} step(s): {skipped_text} ---\n"
                f"--- server log tail ---\n{_log_tail(log_path, n=200)}"
            )

        print(
            f"\n=== real-data-pipeline: all {len(steps)} steps passed in "
            f"{time.time() - started:.1f}s ===\n",
            flush=True,
        )
    finally:
        _stop_server(proc)
        print("=== real-data-pipeline: server stopped ===\n", flush=True)


# ── AestheticScoreNode tests ─────────────────────────────────────────────
# These tests live in the general suite (Tier 2 / realdata-blocked by default)
# per plan §0.5. They verify the AestheticScoreNode's wiring and delegation
# to ScoringService without requiring a live server or real models.
# Import path follows the convention at the top of this file:
#   sys.path.insert(0, str(MODULE_ROOT.parent))
#   from comfyui_image_scorer.adapters.comfyui.nodes.aesthetic_score.node import AestheticScoreNode

import torch
from unittest.mock import patch, MagicMock
from comfyui_image_scorer.adapters.comfyui.nodes.aesthetic_score.node import (
    AestheticScoreNode,
)


def _mock_score_return():
    """Return value for ScoringService.score() matching RETURN_TYPES."""
    return (
        torch.zeros(1, 1, 512, 512),  # selected images (IMAGE)
        torch.zeros(1, 1, 512, 512),  # discarded images (IMAGE)
        True,  # available
        [0.7],  # scores (LIST)
    )


class TestAestheticScoreNodeDelegation:
    """Verify the node properly forwards all arguments to ScoringService.score()."""

    def _make_mock(self):
        mock = MagicMock()
        mock.score.return_value = _mock_score_return()
        return mock

    def test_all_kwargs_forwarded_to_scoring_service(self):
        """Ensure calculate_score passes every INPUT_TYPE kwarg to score()."""
        node = AestheticScoreNode()
        with (
            patch(
                "comfyui_image_scorer.adapters.comfyui.nodes.aesthetic_score.node.verify_models_present"
            ),
            patch.object(node, "_scoring_service", self._make_mock()) as mock,
        ):
            result = node.calculate_score(
                image=torch.zeros(1, 512, 512, 3),
                threshold=0.5,
                positive="test prompt",
                negative="",
                steps=20,
                cfg=7.0,
                sampler="euler",
                scheduler="normal",
                model_name="test-model",
                lora_name="",
                lora_strength=0.0,
            )
            # Verify 4-tuple return matching RETURN_TYPES
            assert len(result) == 4, f"Expected 4-tuple, got {len(result)} items"
            _, _, available, scores = result
            assert available is True
            assert isinstance(scores, list) and len(scores) == 1

            # Verify every kwarg was forwarded — use call_args to avoid
            # tensor-comparison pitfalls in assert_called_once_with
            mock.score.assert_called_once()
            _, kwargs = mock.score.call_args
            assert torch.equal(kwargs["image"], torch.zeros(1, 512, 512, 3))
            assert kwargs["threshold"] == 0.5
            assert kwargs["positive"] == "test prompt"
            assert kwargs["negative"] == ""
            assert kwargs["steps"] == 20
            assert kwargs["cfg"] == 7.0
            assert kwargs["sampler"] == "euler"
            assert kwargs["scheduler"] == "normal"
            assert kwargs["model_name"] == "test-model"
            assert kwargs["lora_name"] == ""
            assert kwargs["lora_strength"] == 0.0
            # NOTE: min_images and max_images have defaults in INPUT_TYPES
            # but the node passes them explicitly; check if present
            if "min_images" in kwargs:
                assert kwargs["min_images"] == 1
            if "max_images" in kwargs:
                assert kwargs["max_images"] == 10


class TestAestheticScoreNodeReturnTypes:
    """Verify the node returns a 4-tuple matching RETURN_TYPES."""

    def test_returns_four_tuple(self):
        """RETURN_TYPES = (IMAGE, IMAGE, BOOLEAN, LIST)."""
        node = AestheticScoreNode()
        with (
            patch(
                "comfyui_image_scorer.adapters.comfyui.nodes.aesthetic_score.node.verify_models_present"
            ),
            patch.object(node, "_scoring_service", MagicMock()) as mock,
        ):
            mock.score.return_value = _mock_score_return()
            result = node.calculate_score(
                image=torch.zeros(1, 512, 512, 3),
                threshold=0.5,
                positive="test prompt",
                negative="",
                steps=20,
                cfg=7.0,
                sampler="euler",
                scheduler="normal",
                model_name="test-model",
                lora_name="",
                lora_strength=0.0,
            )
            assert (
                len(result) == 4
            ), f"Expected 4-tuple matching RETURN_TYPES, got {len(result)} items"
            selected_img, discarded_img, available, scores = result
            # Types check (not deep value check — tensor comparison is fragile)
            assert available is True
            assert isinstance(scores, list)
            # Verify selected/discarded are tensors with correct ndim
            assert selected_img.ndim == 4  # (1,1,512,512) from mock
            assert discarded_img.ndim == 4
