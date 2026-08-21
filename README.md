# ComfyUI Image Scorer — Architecture Documentation

## Overview

This custom node provides aesthetic scoring, pairwise comparison ranking, gallery browsing, latent map visualization, and hyperparameter optimization for generated images. The codebase follows a **strict layered architecture** with **dependency inversion**: dependencies point inward only.

```
core → domain → application → adapters → infrastructure
```

No layer may import from a layer to its right. The **ComfyUI node integration is the primary deliverable**; all other layers exist to serve it.

The codebase still violates parts of this documented architecture. The known violations (layer imports, `core` purity, structural defects) are enumerated in `REORGANIZATION_PLAN.md`, which is the live remediation roadmap and the source of truth for what must change.

The v4 revision (2026-08-17) is complete: `adapters/server/` has strict CLI
parity — every command endpoint is one synchronous call to its CLI command
function, all other routes are removed — with a rename cascade to CLI command
names (`build`, `analyze`, `database`, `training`, `files`), no task system
(`tasks.py`/`task_poller.js` deleted), and a synchronous log-capture backend
(`capture_log_output()`). Per the 2026-08-17 scope decision it also covered
the §3.10 rules audit across all layers (try/except, prints, inline imports,
defaults, module-level containers). This document reflects the final state.

---

## Project Root Layout

| Path | Purpose |
|---|---|
| `comfyui_image_scorer/` | Python package (source only — never pip-installed; only its dependencies are installed) |
| `config/` | Runtime configuration files (JSON) — read-only at startup |
| `output/` | **Regeneratable runtime state** (git-ignored). Safe to `rm -rf`. Contains: SQLite DB, vector caches, generated maps, exported models, downloaded model weights, training plots. |
| `pyproject.toml` / `uv.lock` | Build and dependency metadata. `requirements.txt` is regenerated from these (`uv pip compile pyproject.toml -o requirements.txt`), never hand-edited. |
| `AGENTS.md` | Module rules — governs all work in this folder (overrides the ComfyUI root `AGENTS.md` for this module) |
| `comfyui_image_scorer_old/` | Legacy pre-reorganization copy (git-ignored). **Read-only reference material** — never edit; the user removes it manually. |
| `scorer.py` | **Main CLI entry point** — `python scorer.py <command>` (run from this folder in the ComfyUI venv) |
| `typings/` | Stale stubs from the old structure — cleanup pending (see REORGANIZATION_PLAN) |
| `pyrightconfig.json` | Static type checker configuration (strict mode); see Development Conventions |

---

## Package Structure (`comfyui_image_scorer/`)

### `core/` — Kernel
**Zero internal dependencies.** Pure utilities used by every layer.
- `configuration/` — Settings loading, validation, defaults
- `filesystem/` — Path registry, resolution, runtime directories
- `observability/` — Structured logging, correlation IDs
- `io/` — Serialization, atomic writes, binary helpers
- `utilities/` — Pure functions (collections, math, text, time)

**Rule:** `core` imports **nothing** from `domain`, `application`, `adapters`, or `infrastructure`.

### Dependency Tree

**Condensed** — nesting = dependency; each box may import every box that contains it:

```
rule: a box may import every box that contains it (inner builds on outer)
┌────────────────────────────┐
│            core            │
│  utilities, config, paths  │
│  no other layers, no ComfyUI
│ ┌────────────────────────┐ │
│ │         domain         │ │
│ │  business logic,       │ │
│ │  algorithms, ports     │ │
│ │ ┌────────────────────┐ │ │
│ │ │    application     │ │ │
│ │ │  orchestrates      │ │ │
│ │ │  use cases         │ │ │
│ │ │ ┌────────────────┐ │ │ │
│ │ │ │    adapters    │ │ │ │
│ │ │ │  ComfyUI nodes,│ │ │ │
│ │ │ │  CLI, Flask    │ │ │ │
│ │ │ └────────────────┘ │ │ │
│ │ └────────────────────┘ │ │
│ │ ┌────────────────────┐ │ │
│ │ │  infrastructure    │ │ │
│ │ │  SQLite, ML        │ │ │
│ │ │  models, loaders   │ │ │
│ │ └────────────────────┘ │ │
│ └────────────────────────┘ │
└────────────────────────────┘
```

Nothing imports `infrastructure` — its implementations reach callers via
dependency injection; `adapters` depends on everything above it.

**Full layout** — the package root (the `comfyui_image_scorer/` folder itself) is the importable module. Arrows show what each layer may import from — imports point downward only.

```
comfyui_image_scorer/
├── __init__.py                            lazy node exports for ComfyUI discovery
├── core/                                  ← imports: no other layers, no ComfyUI
│   ├── configuration/                     settings loading, validation, defaults
│   ├── filesystem/                        path registry, resolution, runtime dirs
│   ├── observability/                     structured logging, correlation IDs
│   ├── io/                                serialization, atomic writes
│   └── utilities/                         pure functions (collections, math, text, time)
│
├── domain/                                ← imports: core
│   ├── analysis/                          image/attribute analysis, MediaPipe integration
│   ├── comparison/                        TrueSkill rating, pairwise state, phase ordering
│   │   └── algorithm/                     merge-sort ranker, pair activation, graph helpers
│   ├── database/                          repository port interfaces (protocols)
│   ├── data_transformation/               feature pipelines, metadata normalization, map configs
│   ├── graph/                             crystal graph, chain management, proxy objects
│   ├── training/                          HPO orchestration, calibration, parameter analysis
│   ├── vectors/                           embedding, keypoint, position, person-map vectors
│   └── loading/                           loader port interfaces (`ports.py`)
│
├── application/                           ← imports: core, domain
│   ├── analysis/                          run_stats, run_matrix/run_parameter_analysis
│   ├── data_transform/                    data preparation, map configs
│   ├── hyperparameters/                   hyperparameter optimizer
│   ├── services/                          scoring service, vector list, crystal graph
│   │
│
├── adapters/                              ← imports: core, domain, application
│   ├── __init__.py                        lazy node exports
│   ├── cli/                               argparse router + commands (server, training,
│   │                                      vectors, database, files, analyze)
│   ├── comfyui/                           ComfyUI node integration (primary deliverable)
│   ├── server/                            Flask app (main.py) + endpoints
│   ├── analyze/ build/ database/ gallery/
│   ├── training/ maps/ maps2/
│   │                                      server frontends, one folder per feature
│   └── .../frontend/                      static JS/CSS/HTML per feature
│
└── infrastructure/                        ← imports: core, domain (implements domain ports)
    ├── external_services/                 mediapipe model downloads
    ├── loading/                           training data + maps loaders
    ├── ml_models/                         model loader, batch sizer, model trainer
    └── persistence/                       SQLite repositories, folder organizer, cleanup
```

---

### `domain/` — Domain Layer
**Depends only on `core`.** Contains all business logic, algorithms, data structures, and repository interfaces. No framework code (no Flask, no ComfyUI, no SQLAlchemy).
- `comparison/` — TrueSkill rating, pairwise state, phase ordering, graph helpers
- `database/` — Repository port interfaces (protocols), no implementations
- `data_transformation/` — Feature pipelines, metadata normalization, map configs
- `training/` — HPO orchestration, calibration, parameter analysis
- `analysis/` — Image/attribute analysis, MediaPipe integration
- `graph/` — Crystal graph, chain management, proxy objects
- `vectors/` — Embedding, keypoint, position, person-map vectors
- `loading/` — Loader **port interfaces** (`ports.py`); implementations live in `infrastructure/loading/` and `infrastructure/ml_models/`

**Rule:** `domain` defines **ports** (interfaces) for persistence, external APIs, and ML runtimes. Implementations live in `infrastructure/`.

---

### `application/` — Application Layer
**Depends on `core` + `domain`.** Orchestrates domain objects into use cases. Thin, stateless services.
- `services/` — `scoring_service.py` (`ScoringService`), `vector_list.py` (`VectorList`), `graph_service.py` (`CrystalGraph`)
- `analysis/` — `run_stats.py`, `run_matrix_analysis.py`, `run_parameter_analysis.py`
- `data_transform/` — `prepare_data.py`, `config/maps.py`
- `hyperparameters/` — `hyperparameter_optimizer.py`

**Rule:** No Flask, no ComfyUI, no SQL. Pure orchestration.

---

### `adapters/` — Adapter Layer (Framework Boundaries)
**Depends on `core` + `domain` + `application`.** Translates framework protocols → domain calls.

#### `adapters/server/` — Flask REST API
- `main.py` — app factory, blueprint registration (`register_*_routes`), static
  serving, section frontends
- `endpoints/` — Thin request/response handlers; every command route is exactly
  one call to its CLI command function, with log output captured by
  `core.observability.logger.capture_log_output()` into the response `log`
- `deps.py` — `ServerDeps` (superset of `CLIDeps`) + `to_cli_deps()`
- `frontend/` — shared HTML/CSS/JS shell (index page, api/logger utils)

**Commands ↔ endpoints** (parity table — each row is one synchronous call):

| CLI command | Endpoint |
|---|---|
| `server` (frontends) | `GET /`, static assets |
| `build split-vectors` | `POST /api/build/prepare` (`mode: "split"`) |
| `build full-vectors` | `POST /api/build/prepare` (`mode: "full"`) |
| `build` (all) | `POST /api/build/prepare` (`mode: "all"`, default) |
| `files remove vectors` | `POST /api/build/delete-vectors` (all splits except `image/` are removed) |
| `files remove generated-models` | `POST /api/files/remove-generated-models` |
| `files remove vector-maps` | `POST /api/files/remove-vector-maps` (also deletes `split/map/`) |
| `files remove downloaded-models` | `POST /api/files/remove-downloaded-models` |
| `files download models` | `POST /api/files/download-models` (user-initiated only) |
| `files cleanup` | `POST /api/files/cleanup` (`limit` body param) |
| `training train-model` | `POST /api/training/train` |
| `training hpo` | `POST /api/training/hpo` (`cycles`, `optimization_steps`, `max_combos` body params) |
| `database cleanup` | `POST /api/database/cleanup` |
| `database rebuild` | `POST /api/database/rebuild-db` |
| `database recalculate` | `POST /api/database/recalculate` |
| `analyze stats` | `GET /api/analyze/stats` |
| `analyze parameters` | `POST /api/analyze/analyze-parameters` |
| `analyze matrix` | `POST /api/analyze/analyze-matrix` |
| *(out of scope)* | `comparison`, `gallery`, `maps` blueprints keep their routes |

There is no task system: command endpoints run synchronously and return
`{"status": "done", "result", "log"}`.

#### `adapters/comfyui/` — ComfyUI Node Integration (Primary Deliverable)
- `__init__.py` — Exports `NODE_CLASS_MAPPINGS`, `NODE_DISPLAY_NAME_MAPPINGS`
- `nodes/` — Node implementations grouped by feature
  - `aesthetic_score/` — Scoring nodes (the only node group today)
- `node_registry.py` — Central registration, category management

**Rule:** Nodes contain **zero domain logic** — only translation and delegation to `application.services`.

#### `adapters/cli/` — Command-Line Interface
**Depends on `core` + `domain` + `application`.** Translates shell commands → service calls.
- `main.py` — Entry point (argparse), subcommand router; `files` and `analyze`
  subcommands are implemented inline here, with lazy imports for heavy deps
- `commands/`
  - `server.py` — Start Flask server
  - `training.py` — Run training / HPO
  - `vectors.py` — Generate vectors / rebuild scores
  - `database.py` — DB maintenance (cleanup, rebuild, recalculate)

The CLI entry point is the `scorer.py` script at the module root (run from this
folder in the ComfyUI venv):

```bash
python scorer.py --help
python scorer.py build split-vectors --limit 100
```

`pyproject.toml` also defines an equivalent `comfyui-scorer` console script.

---

## `infrastructure/` — Infrastructure Implementations
**Depends on `core` + `domain` (implements domain ports).** Concrete adapters for external systems.
- `persistence/` — SQLite repositories implementing `domain.database` ports
- `loading/` — Training data / maps loaders (implement the `domain.loading` ports)
- `ml_models/` — Model loader, batch sizer, LightGBM model trainer
- `external_services/` — MediaPipe model downloads

---

## Dependency Rules (Enforced by Architecture)

| Layer | May Import From | Must Not Import From |
|---|---|---|
| `core` | (no other layers, no ComfyUI) | `domain`, `application`, `adapters`, `infrastructure` |
| `domain` | `core` | `application`, `adapters`, `infrastructure` |
| `application` | `core`, `domain` | `adapters`, `infrastructure` |
| `adapters/*` | `core`, `domain`, `application` | `infrastructure` |
| `infrastructure` | `core`, `domain` | `application`, `adapters` |

**Violations are architectural errors.** Use dependency injection (pass implementations as arguments) to cross boundaries outward. Two sanctioned exceptions:
- **Adapter wiring:** `infrastructure` is never imported by other layers — its singletons are constructed and injected at the three composition roots (`adapters/server/main.py`, `adapters/cli/deps.py`, `adapters/comfyui/`).
- **CLI parity:** server endpoints delegate to the CLI command functions (`adapters.cli.commands.*`) — that same-layer import is the point of the architecture: the CLI is the single source of command behavior, endpoints just call it.

### Dependency Violation Test

An AST-based import scan is the gate. Parse every module in each layer, resolve
each import to its top-level layer, and assert it is in that layer's allowed set
(stdlib and installed third-party packages are ignored). The documented test
contract is:

```python
# tests/test_architecture.py  (not on disk yet — test authoring is on hold)
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ("core", "domain", "application", "adapters", "infrastructure")
ALLOWED = {
    "core": (),
    "domain": ("core",),
    "application": ("core", "domain"),
    "adapters": ("core", "domain", "application"),
    "infrastructure": ("core", "domain"),
}

def test_no_architectural_violations():
    for layer, allowed in ALLOWED.items():
        for path in sorted((ROOT / layer).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                target = None
                if isinstance(node, ast.ImportFrom) and node.module:
                    target = node.module.split(".")[0]
                elif isinstance(node, ast.Import):
                    target = node.names[0].name.split(".")[0]
                if target in LAYERS and target not in allowed and layer != target:
                    raise AssertionError(f"{path.relative_to(ROOT)}: {layer} imports {target}")
```

**Current status:** the root `tests/` directory does not exist yet, so the
AST layer scan in `REORGANIZATION_PLAN.md` §4 is the gate today (run
manually). The revision closed the enumerated violations: the only
`infrastructure` imports that remain are the 30 adapter-wiring statements in
the three composition roots, and `pytest` passes (34 tests).

Existing violations must be fixed by moving code across the boundary — never by
relaxing the rule or deleting the check. The `core` row has an empty allowed
set on purpose: `core` imports no other layers and no ComfyUI internals.
Nothing imports `infrastructure` except the composition roots listed above.

---

## Runtime Data Rules

| Directory | Content | Lifecycle | Git |
|---|---|---|---|
| `config/` | User-editable JSON settings | Persistent, user-managed | Tracked |
| `output/downloaded_models/` | Downloaded third-party weights (MediaPipe `.task`, HF checkpoints) | Redownloadable via `comfyui-scorer files download models` — no manual backup needed | Ignored (large) |
| `output/training/plots/` | Regeneratable training plots | **Ephemeral** | Ignored |
| `output/` (rest) | SQLite DB, vector caches, generated maps, exported models | **Ephemeral** — safe to delete anytime | **Ignored** |

**Golden rule:** If `rm -rf output/` requires zero manual steps to recover, it belongs in `output/`.

---

## ComfyUI Integration Contract

- Entry point: `comfyui_image_scorer.adapters.comfyui.__init__` (lazy `__getattr__` re-exporting from `.node_registry`)
- Exports: `NODE_CLASS_MAPPINGS`, `NODE_DISPLAY_NAME_MAPPINGS`
- Current node: **`AestheticScore`** (class `AestheticScoreNode`, category `Scoring`) in `adapters/comfyui/nodes/aesthetic_score/node.py`
  - Inputs: `image` (IMAGE), `threshold` (FLOAT, 0.5), `positive`/`negative` (STRING), `steps` (INT, 20), `cfg` (FLOAT, 7.0), `sampler` (STRING, "euler"), `scheduler` (STRING, "normal"), `model_name`/`lora_name` (STRING), `lora_strength` (FLOAT), `min_images`/`max_images` (INT)
  - Outputs: `images` (IMAGE), `discarded images` (IMAGE), `Available` (BOOLEAN), `score` (LIST)
- Nodes declare `INPUT_TYPES`, `RETURN_TYPES`, `FUNCTION`, `CATEGORY` per ComfyUI spec
- All node logic delegates to `application.services.ScoringService`

---

## Development Conventions

1. **Imports:** always relative, otherwise comfyui will struggle. At module scope. The CLI command modules use lazy inline imports for heavy dependencies — that established pattern is allowed, but do not spread it to new code.
2. **No `try`/`except` blocks:** let failures surface with clear errors; no fallbacks. The only exception is the batch size profiler (`infrastructure/ml_models/batch_sizer.py`), where it is part of the function's working.
3. **Tests:** Colocated `tests/` subdirectory next to tested module (e.g., `domain/comparison/tests/test_trueskill.py`).
4. **Typing:** Full type hints on public APIs. `pyright` must pass in strict mode (`"typeCheckingMode": "strict"` in `pyrightconfig.json`). The stale `typings/` folder interferes with analysis — its cleanup is tracked in REORGANIZATION_PLAN.
5. **No global mutable state** in `core`/`domain`/`application`. State lives in `adapters` or `infrastructure`.
6. **Configuration** enters only via `core.configuration` — no `os.getenv` scattered in domain code.
7. **No defaults:** `.get(..., default)` is highly discouraged and strictly forbidden for config objects; avoid default function arguments. When a parameter's default is ambiguous, state it explicitly at every call site.
8. **Verification order** after a change: `pytest` → `ruff` (ARG/F401) → `pyright` → AST layer scan (REORGANIZATION_PLAN §4) → node registration smoke check.
9. **Never install the module itself:** no `setup.py`, no `pip install .`/`pip install -e .` — only its dependencies via `pip install -r requirements.txt`.
10. **No unused arguments:** remove them from the signature and fix all callers. Framework callbacks that must keep a positional slot (Flask error handlers, monkey-patched stdlib hooks) keep the slot with an underscore-prefixed name (`_e`). Gate: `ruff check --select ARG --target-version py313 --exclude comfyui_image_scorer_old --exclude typings .` (REORGANIZATION_PLAN §4).

---

## Node Import Verification

ComfyUI discovers nodes at startup. Verify registration works:

**1. Startup logs** — ComfyUI prints:
```
[ComfyUI] Loaded custom node: comfyui_image_scorer
[ComfyUI] Registered nodes: AestheticScore
```

**2. Node menu** — Right-click canvas → search node name → appears under its `CATEGORY` (`Scoring`).

**3. Programmatic test** (run in CI / locally):
```bash
# From project root (parent dir must be on sys.path — same as ComfyUI loading
# this folder from custom_nodes/, and same as pytest's pythonpath = [".."])
python -c "
import sys
sys.path.insert(0, '..')
from comfyui_image_scorer.adapters.comfyui import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
print('Nodes:', list(NODE_CLASS_MAPPINGS.keys()))
for name, cls in NODE_CLASS_MAPPINGS.items():
    assert hasattr(cls, 'INPUT_TYPES'), f'{name}: missing INPUT_TYPES'
    assert hasattr(cls, 'RETURN_TYPES'), f'{name}: missing RETURN_TYPES'
    assert hasattr(cls, 'FUNCTION'), f'{name}: missing FUNCTION'
    assert hasattr(cls, 'CATEGORY'), f'{name}: missing CATEGORY'
    print(f'  ✓ {name}: {cls.CATEGORY} / {cls.FUNCTION}')
print('All nodes valid.')
```

**4. Unit test** (colocated — pending test authoring, same as `tests/test_architecture.py`):
```python
# adapters/comfyui/nodes/aesthetic_score/tests/test_node_import.py
from comfyui_image_scorer.adapters.comfyui import NODE_CLASS_MAPPINGS

def test_aesthetic_nodes_registered():
    expected = {"AestheticScore"}
    actual = set(NODE_CLASS_MAPPINGS.keys())
    assert expected.issubset(actual), f"Missing: {expected - actual}"
```

---

## Continuous Integration

- **Dependency sync check:** `.github/workflows/check-deps.yml` — fails if `requirements.txt` drifts from `pyproject.toml` (`uv pip compile pyproject.toml --output-file=- | diff - requirements.txt`).
- `requirements.txt` is generated (`uv pip compile pyproject.toml -o requirements.txt`) and committed; regenerate + commit it whenever `pyproject.toml` dependencies change.
- Run locally: `uv pip compile pyproject.toml -o requirements.txt`

---

## Quick Start (Developer)

> **All commands below MUST run inside the ComfyUI virtual environment** (the one ComfyUI uses). Activate it first:
> ```bash
> # Windows (PowerShell)
> & "E:\ComfyUI\.venv\Scripts\Activate.ps1"
> ```
> This ensures `torch`, `comfy`, and all ComfyUI-internal packages resolve correctly for both the server and node entry points.

```bash
# Install dependencies only — the package itself is never pip-installed.
# Regenerate requirements.txt and reinstall after changing pyproject.toml:
uv pip compile pyproject.toml -o requirements.txt
pip install -r requirements.txt

# Run tests
pytest

# Run type checks (strict)
pyright

# Node registration smoke check
python -c "import sys; sys.path.insert(0, '..'); from comfyui_image_scorer.adapters.comfyui import NODE_CLASS_MAPPINGS; print(list(NODE_CLASS_MAPPINGS))"
```

This folder already lives in `ComfyUI/custom_nodes/` — no symlink needed.

---

## License

MIT — see `LICENSE`.