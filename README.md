# ComfyUI Image Scorer — Architecture Documentation

## Overview

This custom node provides aesthetic scoring, pairwise comparison ranking, gallery browsing, latent map visualization, and hyperparameter optimization for generated images. The codebase follows a **strict layered architecture** with **dependency inversion**: dependencies point inward only.

```
core → domain → application → adapters → infrastructure
```

No layer may import from a layer to its right. The **ComfyUI node integration is the primary deliverable**; all other layers exist to serve it.

The codebase still violates parts of this documented architecture. The known violations (layer imports, `core` purity, structural defects) are enumerated in `REORGANIZATION_PLAN.md`, which is the live remediation roadmap and the source of truth for what must change.

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
| `typings/` | Stale stubs from the old structure — cleanup pending (REORGANIZATION_PLAN §2.3) |
| `pyrightconfig.json` | Static type checker configuration — **currently missing on disk**, must be restored (strict mode) before `pyright` can run; see Development Conventions |

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
│  stdlib only               │
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
├── core/                                  ← imports: stdlib only
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
│   └── loading/                           loader port interfaces (planned — not yet on disk)
│
├── application/                           ← imports: core, domain
│   ├── analysis/                          run_stats, run_matrix/run_parameter_analysis
│   ├── data_transform/                    data preparation, map configs
│   ├── hyperparameters/                   hyperparameter optimizer
│   ├── services/                          scoring service, vector list, crystal graph
│   ├── dto/                               empty shell (no symbols yet)
│   └── ports/                             empty shell (no symbols yet)
│
├── adapters/                              ← imports: core, domain, application
│   ├── __init__.py                        lazy node exports
│   ├── cli/                               argparse router + commands (server, training,
│   │                                      vectors, database, files, analyze)
│   ├── comfyui/                           ComfyUI node integration (primary deliverable)
│   ├── server/                            Flask app (main.py) + endpoints
│   ├── analysis/ comparison/ data_transform/ database_structure/ gallery/
│   ├── maps/ maps2/ training_hyperparameters/
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
- `loading/` — Loader **port interfaces** (planned — not on disk yet; implementations live in `infrastructure/loading/`)

**Rule:** `domain` defines **ports** (interfaces) for persistence, external APIs, and ML runtimes. Implementations live in `infrastructure/`.

---

### `application/` — Application Layer
**Depends on `core` + `domain`.** Orchestrates domain objects into use cases. Thin, stateless services.
- `services/` — `scoring_service.py` (`ScoringService`), `vector_list.py` (`VectorList`), `graph_service.py` (`CrystalGraph`)
- `analysis/` — `run_stats.py`, `run_matrix_analysis.py`, `run_parameter_analysis.py`
- `data_transform/` — `prepare_data.py`, `config/maps.py`
- `hyperparameters/` — `hyperparameter_optimizer.py`
- `dto/`, `ports/` — empty shells (only `__init__.py`), awaiting content

**Rule:** No Flask, no ComfyUI, no SQL. Pure orchestration.

---

### `adapters/` — Adapter Layer (Framework Boundaries)
**Depends on `core` + `domain` + `application`.** Translates framework protocols → domain calls.

#### `adapters/server/` — Flask REST API
- `routing/` — Blueprint registration, URL prefixes
- `endpoints/` — Thin request/response handlers (validation → service call → JSON)
- `middleware/` — Error handling, CORS, request logging

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
- `loading/` — Training data / maps loaders (implement the `domain.loading` ports once Phase 2a creates them)
- `ml_models/` — Model loader, batch sizer, LightGBM model trainer
- `external_services/` — MediaPipe model downloads

---

## Dependency Rules (Enforced by Architecture)

| Layer | May Import From | Must Not Import From |
|---|---|---|
| `core` | (stdlib only) | `domain`, `application`, `adapters`, `infrastructure` |
| `domain` | `core` | `application`, `adapters`, `infrastructure` |
| `application` | `core`, `domain` | `adapters`, `infrastructure` |
| `adapters/*` | `core`, `domain`, `application` | other `adapters/*`, `infrastructure` |
| `infrastructure` | `core`, `domain` | `application`, `adapters` |

**Violations are architectural errors.** Use dependency injection (pass implementations as arguments) to cross boundaries outward.

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
enforcement script in `REORGANIZATION_PLAN.md` §6 is the gate today (run
manually). It currently reports **66 layer violations across 26 files**
(`domain → infrastructure` 8, `domain → application` 1, `application →
infrastructure` 17, `adapters → infrastructure` 40) plus 2 cross-adapter edges —
all enumerated in REORGANIZATION_PLAN §2.1 with per-file line numbers.

Existing violations must be fixed by moving code across the boundary — never by
relaxing the rule or deleting the check. The `core` row has an empty allowed
set on purpose: `core` imports only stdlib. Note that AGENTS.md documents the
one sanctioned exception: **nothing imports `infrastructure`**, except the
wiring at the composition roots in `adapters` (`adapters/server/main.py`,
`adapters/cli/main.py`, `adapters/comfyui/`), where infra singletons are
constructed and injected.

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
4. **Typing:** Full type hints on public APIs. `pyright` must pass in strict mode (`"typeCheckingMode": "strict"` in `pyrightconfig.json`). Note: `pyrightconfig.json` is currently missing on disk and the stale `typings/` folder interferes with analysis — recreating the config is tracked in REORGANIZATION_PLAN Phase 1.
5. **No global mutable state** in `core`/`domain`/`application`. State lives in `adapters` or `infrastructure`.
6. **Configuration** enters only via `core.configuration` — no `os.getenv` scattered in domain code.
7. **No defaults:** `.get(..., default)` is highly discouraged and strictly forbidden for config objects; avoid default function arguments. When a parameter's default is ambiguous, state it explicitly at every call site.
8. **Verification order** after a change: `pytest` → `pyright` → AST layer scan (REORGANIZATION_PLAN §6) → unused-arguments check (§6b) → installable-module check (§6c) → node registration smoke check.
9. **Never install the module itself:** no `setup.py`, no `pip install .`/`pip install -e .` — only its dependencies via `pip install -r requirements.txt` (REORGANIZATION_PLAN §6c).
10. **No unused arguments:** remove them from the signature and fix all callers. Framework callbacks that must keep a positional slot (Flask error handlers, monkey-patched stdlib hooks) keep the slot with an underscore-prefixed name (`_e`). Gate: `ruff check --select ARG --target-version py313 --exclude comfyui_image_scorer_old --exclude typings .` (REORGANIZATION_PLAN §6b).

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

## Development Rules (from AGENTS.md)

### Engineering Style
- **Small, direct changes** — touch the narrowest code path that explains the bug/behavior
- **Minimize files changed** — a change touching many files is suspect
- **Practical over architectural** — add abstractions only when they remove real duplication or match existing ComfyUI patterns
- **Fewer dependencies** — no new deps unless absolutely necessary
- **Delete dead code aggressively** — no fallbacks, migration paths, debug prints, or compatibility branches that aren't needed

- **Preserve APIs** — node names, model-loading behavior, file layout, workflow compatibility unless explicitly replacing them
- **No AI-generated code style** — no unnecessary helper layers, vague names, boilerplate comments, defensive branches without real failure modes, broad rewrites, try catch blocks, default values


### Architecture Boundaries
- **Layer focus** — each layer owns its concepts; don't leak UI, API, workflow, queue, persistence, telemetry, model-loading, node, or execution concerns across layers
- **Shared modules depend down** — only on lower primitives and own domain concepts
- **Narrow data across boundaries** — no broad context objects, request metadata, IDs, bookkeeping state, or callbacks unless the receiver genuinely needs them
- **Identify smallest owner layer** before touching many files

### No Internet Requests
- **No outbound network calls** from core/domain/application layers — no telemetry, analytics, tracking, usage reporting, crash reporting, update checks, remote config, feature flags, metrics, licensing checks
- **Model downloading only when explicitly user-initiated** — limited to requested artifact, no background activity. The only download path is the `files download models` CLI command (all models in `prepare_config.json`: HF/timm/torch.hub + MediaPipe). Runtime model loading is offline-only: missing models fail fast with a hint to run that command
- **Local-only behavior allowed** — if it stays on user's machine with no network access, tracking, or persistent identification

### State Ownership
- **State lives on the object that owns the behavior** using it
- **No probing children** with `getattr(child, "...", default)` to decide parent control flow — if parent needs to branch on a capability, initialize an explicit parent-owned field when child is constructed/attached
- **Prefer direct attributes with clear defaults** over implicit feature detection through arbitrary child attributes
- **Child capability checks only when child owns the behavior** and parent is simply delegating

### Interface Contracts
- **Public methods = stable contracts** — don't change return shapes, add sentinel wrappers, or alter signatures without updating all callers
- **Preserve caller invocation** — required args, order, return type, side effects, error behavior
- **No compatibility params/flags** unless read by current code and changing behavior
- **No model-specific options in shared helpers** — keep one-off behavior at the integration boundary
- **Normalize third-party returns at the boundary** — core code sees expected types, not model-specific variants

### Autograd / Model Freezing
- **No `torch.no_grad`, `torch.inference_mode` wrappers** — ComfyUI models are always frozen for inference
- **No freeze/unfreeze/trainability toggles** on model classes
- **Remove training-only behavior** (dropout) from inference code; preserve checkpoint compatibility with `nn.Identity` if needed

### Python Style
- **Imports at module scope** — relative imports; lazy inline imports allowed only in the CLI command modules (established pattern, not to be spread to new code)
- **No `try`/`except`** — no fallbacks; let failures surface with clear errors. Only exception: the batch size profiler, where it is part of the function's working
- **No defaults** — `.get(..., default)` is highly discouraged and strictly forbidden for config objects; avoid default function arguments; state ambiguous parameter values explicitly at every call site
- **No version workarounds** for pinned library versions
- **Fail clearly** on unsupported formats, invalid quantization, bad state — no silent quality degradation
- **Match local file style** — long lines, simple helpers, module-level state, direct tensor ops are fine when clearer

### Model / Device / Memory
- **dtype, device, VRAM, offloading = core correctness** — check CPU/CUDA/ROCm/MPS/DirectML/XPU/NPU/low-VRAM implications
- **Use ComfyUI helpers** — `comfy.quant_ops`, `model_management`, `memory_management`, `pinned_memory`, `comfy-kitchen`
- **Use optimized kernels** — prefer shared ops over handwritten; adapt inputs to documented layout
- **All models use ComfyUI-selected attention** — treat backend as opaque; don't inspect function identity/names/modules
- **No custom ops duplicating existing ones with float32 upcast** — use generic ComfyUI ops / native torch
- **`operations` param in `__init__` is never `None`** — no fallback branches
- **No unnecessary params** in model/block/ops classes — only values actually used for inference
- **Reuse existing model classes/blocks/ops/helpers** before implementing new ones
- **Model detection uses first dimension only** — second dim may be half for NVFP4/4-bit
- **Guard every state-dict key** in detection — no partial match then KeyError
- **No `einops` in core inference** — use native torch `reshape`, `view`, `permute`, `transpose`, `flatten`, `unflatten`, `unsqueeze`, `squeeze`
- **No tensors for Python-side metadata** — sequence lengths, offsets, indices, counts stay as Python ints/lists
- **No unnecessary casts/transfers** — preserve compute dtype, storage dtype, bias dtype, shape metadata
- **Trust optimized backend dtype contract** — don't cast results back unless documented
- **Model-native latent layout stays in model** — no collapsing/expanding in nodes
- **DiT models: pad to patch size, crop output only** — use `comfy.ldm.common_dit.pad_to_patch_size`
- **No defensive shape checks** that just replace the tensor op's own error — validate only at real boundaries
- **Inputs to model forward = compute dtype** (except integer timesteps) — no convenience casts
- **Raw params not owned by ops: cast at use** with `comfy.ops.cast_to_input` or `model_management.cast_to`
- **Model code doesn't manage memory** — loading, offloading, device movement, VRAM policy, cache lifetime belong in execution/model-management layers
- **No global/module/class/singleton stores for tensors** across executions — temporary caches scoped to single forward/encode/decode call

### Nodes & User-Facing Behavior
- **Follow conventions**: `INPUT_TYPES`, `RETURN_TYPES`, `FUNCTION`, `CATEGORY`, local registration mapping
- **Backward compatible by default** — add inputs with sensible defaults; don't change output types unless required
- **Minimal nodes** — reuse existing nodes; adapt model to existing nodes > create new nodes
- **`io.Autogrow`** for variable repeated inputs — min 0 when valid no-item path, cap only when real limit
- **Mark inputs optional** when execution has valid path without them
- **Conditioning nodes output conditioning only** — no convenience image outputs
- **Nodes output only what they own** — no pass-through outputs unless explicitly an output node
- **Nodes expose only inputs they read** — no placeholder/pass-through/compatibility inputs
- **Node code never patches model code directly** — use model patcher class
- **Warnings/info = short and actionable** — remove noisy messages rather than adding more

### Commit & Review
- **Subjects**: `Fix ...`, `Add ...`, `Support ...`, `Remove ...`, `Update ...`, `Make ...`, `Use ...`, `Disable ...`, `Bump ...`, `Revert ...`
- **PR descriptions**: problem, behavioral change, tests run — no long narratives
- **One coherent behavioral change per commit**
- **Review priority**: crashes, wrong dtype/device, memory regressions, broken model loading, workflow incompatibility, noisy/misleading output

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

# Run type checks (strict). pyrightconfig.json is currently missing on disk —
# recreate it (typeCheckingMode: "strict", exclude comfyui_image_scorer_old/)
# until it is restored (REORGANIZATION_PLAN Phase 1):
pyright

# Node registration smoke check
python -c "import sys; sys.path.insert(0, '..'); from comfyui_image_scorer.adapters.comfyui import NODE_CLASS_MAPPINGS; print(list(NODE_CLASS_MAPPINGS))"
```

This folder already lives in `ComfyUI/custom_nodes/` — no symlink needed.

---

## License

MIT — see `LICENSE`.