# Reorganization Plan — `comfyui_image_scorer` (v2, remediation)

**Status:** The original reorganization (v1 of this file) was **executed**: all file
moves from the v1 "Move Summary" are done. v2 is the plan for the remaining
remediation: the codebase currently violates its own documented architecture
(verified by AST scan, 146 files), contains broken-package artifacts, and
untracked files that break a fresh checkout.

`comfyui_image_scorer_old/` is **read-only reference material**. It is removed
manually by the user; this plan never creates, edits, or deletes anything inside it.

---

## 0. Ground Rules (non-negotiable, from README + AGENTS.md)

1. **Venv:** every command (pytest, pyright, import checks) runs in the **ComfyUI
   venv** (`& "C:\path\to\ComfyUI\venv\Scripts\Activate.ps1"` first).
2. **Imports:** always **relative** (ComfyUI requirement); always at **module
   scope** — no inline imports inside functions, ever.
3. **Typing:** full type hints on public APIs; **pyright strict** must pass
   (`"typeCheckingMode": "strict"` in `pyrightconfig.json`).
4. **No `try`/`except` blocks** anywhere — let failures surface with clear errors.
5. **Tests:** do **not** create any test files in this effort. **Existing tests
   must keep passing** (`pytest`).
6. **Test locations:** colocated `tests/` subdirectory next to the tested module
   (e.g., `domain/graph/tests/`); cross-layer architecture test lives at
   `tests/test_architecture.py`. `pyproject.toml` testpaths:
   `["tests", "adapters", "domain", "core"]`.
7. **Dependency rule:** nothing imports `infrastructure`. Implementations reach
   callers via **dependency injection**; wiring happens at the **composition root**
   in `adapters/`. Violations are fixed by moving code across the boundary —
   never by relaxing the rule.
8. **State:** no global mutable state in `core`/`domain`/`application`. Wiring
   state lives in `adapters` or `infrastructure`.
9. **Configuration** enters only via `core.configuration` — no scattered
   `os.getenv`/path resolution in domain/application code.
10. **No internet requests.** The only download path is the `files download models`
    CLI command; runtime loading is offline with a fail-fast hint.
11. **Compatibility:** preserve node names, APIs, workflow behavior, file layout.
12. **No new dependencies.**
13. Keep changes **small and direct** — narrowest code path per fix.

---

## 1. What v1 Achieved (historical record)

| v1 move | Result |
|---|---|
| `domain/database/schema.py` → `infrastructure/persistence/database.py` | done |
| `domain/database/comparisons_table.py` → `infrastructure/persistence/comparisons_repository.py` | done |
| `domain/graph/crystal_graph.py` → `application/services/graph_service.py` | done, but `_ImageRepo`/`_ComparisonRepo` survived as `_LazyImageRepo`/`_LazyComparisonRepo` with inline infra imports (see §2.1 Root cause) |
| `parallel_batch`/`parallel_for` → `core/utilities/concurrency.py` | done |
| Create `adapters/comfyui/__init__.py` + `node_registry.py` | done |
| Remove root `nodes/` | done |
| Remove global `crystal_graph` instance + auto-rebuild-on-import | done (rebuild now a guarded method) |
| `domain/loading/` | **never created** — loaders went to `infrastructure/loading/` instead |

---

## 2. Verified Violations (AST scan, 146 files)

### 2.1 Layer import violations — 69 statements across 26 files

| Rule broken | Count | Files |
|---|---|---|
| `application → infrastructure` | 20 | `services/scoring_service.py:19-22`, `services/vector_list.py:20,25-26`, `services/graph_service.py:352-366` (inline), `analysis/run_stats.py:4-5`, `data_transform/prepare_data.py:26-32`, `data_transform/config/maps.py:13`, `hyperparameters/hyperparameter_optimizer.py:13-14` |
| `adapters → infrastructure` | 40 | `server/main.py:23-53`, `server/processor.py`, `server/endpoints/*` (17), `cli/main.py:181-191`, `cli/commands/*` (15), `comfyui/nodes/aesthetic_score/node.py:4` |
| `domain → infrastructure` | 8 | `comparison/state.py:10`, `vectors/image_vector.py:12,16`, `vectors/embedding_vector.py:12`, `vectors/map_vector.py:3`, `vectors/person_map_vector.py:3`, `training/plot.py:16`, `graph/tests/test_chain_manager.py:13` |
| `domain → application` | 1 | `graph/tests/test_chain_manager.py:11` |
| **Subtotal (layer violations)** | **69** | **26 files** |
| cross-adapter (`adapters/*` → other `adapters/*`) | 2 | `cli/commands/server.py:8` → `server.main`; `cli/commands/database.py:21` → `server.processor` (same 2 files already counted above) |

**Root cause:** `infrastructure` exposes module-level singletons
(`model_loader`, `training_loader`, `maps_list`, `BatchSizer`, `ModelLoader`) and
free-function repos (`get_all_images`, `get_all_comparisons`, ...), and every
caller imports them directly. The v1 plan itself directed
`graph_service` to import `infrastructure.persistence.*` — that directive is
exactly the violation now banned by the README dependency table.

### 2.2 `core` purity violations (README: "stdlib only")

| File | Imports |
|---|---|
| `core/filesystem/paths.py:15` | `from folder_paths import get_output_directory` (**ComfyUI**) |
| `core/utilities/helpers.py` | `numpy`, `torch`, `PIL` |
| `core/io/serialization.py` | `jsonlines`, `tqdm` |
| `core/utilities/concurrency.py`, `core/observability/logger.py` | `tqdm` |

### 2.3 Structural defects

1. `application/data_transform/__init__.py` and `application/hyperparameters/__init__.py`
   are **empty directories**, not files → those subpackages only import as
   namespace packages; the real `__init__.py` was never committed.
2. **Untracked but imported** (fresh checkout breaks):
   `application/data_transform/config/` (imported by `prepare_data.py`),
   `infrastructure/external_services/mediapipe_models.py` (imported by `cli/main.py:182`).
3. `core/observability/logger.py:728` — leftover debug `print(f"cleared:{_cleared}")`.
4. `comfyui_image_scorer_old/` — legacy copy of the whole codebase (gitignored).
   **Removed manually by the user**; may be read for reference only.
5. `setup.py` — legacy packaging (with `package_dir = {PKG: "."}` hack); the
   package is never pip-installed; `pyproject.toml` is the build config.
6. `scorer.py` — duplicate CLI entry; `pyproject.toml` already defines the
   `comfyui-scorer` console script. (v1's rationale "for `python -m`" is false:
   there is no `__main__.py`.)
7. `FUNCTION_INDEX.md` — verify whether still current; delete if stale.
8. `adapters/server/middleware/`, `adapters/server/tests/`,
   `application/dto/`, `application/ports/`, `domain/database/tests/` — empty
   shells (only `__init__.py`).

### 2.4 README mismatches to fix in Phase 4

- `domain/loading/` listed under domain (README line 133, "Model loaders") —
  does not exist. README line 190 already anticipates it: `ml_models/`
  implements `domain.loading` **ports**. Phase 2a creates `domain/loading/` with
  the port interfaces, so the fix is to reword line 133 to "loader port
  interfaces" (implementations live in `infrastructure/loading/`) — not to
  remove the entry.
- `application/services` lists RankingService/GalleryService/MapService/... —
  actual: `graph_service.py`, `vector_list.py`, `scoring_service.py`.
- `adapters/comfyui/nodes/` lists ranking/, gallery/, maps/ groups — only
  `aesthetic_score/` exists.
- CLI commands list mentions `files`, `analyze`, `output.py` — actual commands:
  server, training, vectors, database.
- `python scorer.py --help` reference — obsolete if `scorer.py` is deleted.
- `tests/test_architecture.py` is documented (lines 214-242) but the root
  `tests/` directory does not exist yet — create it when test authoring is
  allowed (see Phase 5).

---

## 3. Target Architecture

```
core → domain → application → adapters → infrastructure   (imports point inward)
```

- **Ports live in domain:** `domain/database/ports/repository_ports.py` (exists:
  `ImageRepository`, `ComparisonRepository`, `PathResolver` protocols). **New:
  `domain/loading/`** with protocols for `ModelLoader`, `BatchSizer`,
  `MapsProvider`, `TrainingLoader`.
- **Implementations live in infrastructure** and are constructed only by
  **composition roots in adapters**:
  - `adapters/server/main.py` (Flask startup),
  - `adapters/cli/main.py` (CLI entry),
  - `adapters/comfyui/` (node wiring — legal to hold wiring state: adapters
    may hold state).
- **Domain/application never import infrastructure**; they receive
  protocol-typed dependencies via constructor/function parameters.

---

## 4. Remediation Phases

### Phase 1 — Repo hygiene & importability (mechanical, no design change)

1. Replace the two `__init__.py` **directories** in `application/data_transform/`
   and `application/hyperparameters/` with real empty `__init__.py` files
   (delete dirs, `git add` the files).
2. `git add application/data_transform/config/` and
   `infrastructure/external_services/mediapipe_models.py`.
3. Remove the debug print at `core/observability/logger.py:728`.
4. Delete `setup.py`, `scorer.py` (update README CLI section), stale
   `FUNCTION_INDEX.md` (after verifying).
5. `comfyui_image_scorer_old/`: **user deletes manually** — not part of this plan.

**Gate:** `pytest` green; `pyright` strict clean.

### Phase 2 — Dependency inversion (the 69 violations)

**2a. Ports (domain, new code is tiny):**
- `domain/loading/ports.py` (or extend `domain/loading/__init__.py`): protocols
  `ModelLoader`, `BatchSizer`, `MapsProvider`, `TrainingLoader` describing the
  existing infra singletons' surfaces.
- `domain/database/ports/repository_ports.py` — already covers repos; keep.

**2b. Infrastructure (add thin class wrappers, keep functions):**
- `infrastructure/persistence/images_repository.py` /
  `comparisons_repository.py`: add `SQLiteImagesRepository(ImageRepository)` /
  `SQLiteComparisonsRepository(ComparisonRepository)` delegating to the existing
  functions. Functions stay during transition; wrappers become the injected
  objects. Follow the existing re-export convention of
  `domain/database/ports/__init__.py`.
- `infrastructure/ml_models/model_loader.py`, `batch_sizer.py`,
  `infrastructure/loading/training_loader.py`, `maps_loader.py`: no change —
  existing classes/singletons already satisfy the ports.

**2c. Domain (8 imports, 7 files):**
- `domain/comparison/state.py:10` — functions gain a `repo: ImageRepository`
  parameter; callers (comparison algorithm/recorder) receive it from
  application services.
- `domain/vectors/{image_vector,embedding_vector,map_vector,person_map_vector}.py`
  — functions accept the loader/maps/batch-sizer as parameters instead of
  importing the singletons.
- `domain/training/plot.py:16` — accepts loaded training data (or the loader) as
  a parameter.
- `domain/graph/tests/test_chain_manager.py:11,13` — replace
  application/infrastructure imports with injected fakes (fix only, no new tests).

**2d. Application (20 imports, 7 files):**
- `services/scoring_service.py` — `__init__` gains protocol-typed params
  (`model_loader`, `training_loader`, `batch_sizer`, `model_trainer`) instead of
  importing the singletons; `verify_models_present()` moves from the node into
  the service.
- `services/graph_service.py` — delete `_LazyImageRepo`/`_LazyComparisonRepo`
  (and their inline infra imports); `CrystalGraph` takes injected repos.
- `services/vector_list.py`, `analysis/run_stats.py`,
  `data_transform/prepare_data.py`, `data_transform/config/maps.py`,
  `hyperparameters/hyperparameter_optimizer.py` — same pattern: repos/loaders
  become parameters; callers pass them.

**2e. Adapters — composition roots + cross-adapter (42 imports):**
- `server/main.py`: construct repos/services once, pass into
  `register_*_routes(app, deps)` for each endpoint module; `processor.py`
  receives services via constructor.
- `cli/main.py`: `main()` builds the deps and passes them into the command
  functions; `cli/commands/*` drop their infra imports.
- `adapters/comfyui/`: add a wiring module (e.g., `adapters/comfyui/services.py`)
  that builds `ScoringService` with infra singletons; the node imports the
  service from there (same adapter, no violation).
- **Cross-adapter:** extract the image-processing logic shared by
  `cli/commands/server.py` (server bootstrap) and `cli/commands/database.py`
  (`ImageProcessor`) into an application service; both CLI commands and server
  endpoints call that service. Flask-specific code stays in `adapters/server/`.

**Gate:** AST scan (§6) reports **zero** layer violations.

### Phase 3 — `core` purity

- **Mandatory:** remove `from folder_paths import ...` from
  `core/filesystem/paths.py:15`. `image_root` comes from `config`; the ComfyUI
  fallback moves to the adapter composition roots (they set it before services
  run).
- **Recommended:** relax the README `core` row from "(stdlib only)" to "no other
  layers, no ComfyUI" (the AST test never checked stdlib, only layers; `numpy`,
  `torch`, `tqdm`, `jsonlines`, `PIL` are project dependencies). Exact README
  spots to edit: line 49 (diagram box "stdlib only"), line 80 (full-layout tree
  `core ← imports: stdlib only`), line 199 (dependency table `(stdlib only)`
  row), line 245 ("`core` imports only stdlib" sentence in the violation-test
  note).
- **Alternative (only if strictness is preferred):** relocate
  `core/utilities/helpers.py` tensor/image functions to `domain`, keep pure
  filesystem helpers in core. `tqdm`/`jsonlines` stay (progress bars and JSONL
  are core utility concerns).

### Phase 4 — README fixes (see §2.4)

Update: `domain/` section (reword `loading/` to loader **port interfaces** per
§2.4 — the entry stays, Phase 2a makes it real), correct services list, comfyui
node groups, CLI commands, `scorer.py` reference, `core` dependency-table row
per Phase 3 decision, `adapters/comfyui/nodes/` list.

### Phase 5 — Verification (no new test files)

Run in the **ComfyUI venv**, in order:

```bash
pytest                                # existing tests pass
pyright                               # strict, zero errors
```

1. AST layer scan (§6) → zero violations.
2. Node registration smoke check (README "Node Import Verification" snippet) →
   `AestheticScore` loads.
3. When test authoring is allowed, create the README-documented
   `tests/test_architecture.py` (using the resolver-aware scan from §6, not the
   simplified snippet) and add it to the CI flow; until then the §6 script is
   the gate.

---

## 5. Test Folder Locations (for when tests are written)

| Code location | Tests location |
|---|---|
| `tests/` (root) | cross-layer tests (`test_architecture.py` per README) |
| `core/**/` | `core/<module>/tests/` |
| `domain/graph/`, `domain/vectors/` | exist already (`domain/graph/tests/`, `domain/vectors/tests/`) |
| `domain/analysis/`, `domain/comparison/`, `domain/training/`, `domain/data_transformation/`, `domain/database/`, `domain/loading/` | `domain/<module>/tests/` (v1 planned these; `database/tests/` exists as empty shell) |
| `application/services/` | `application/services/tests/` |
| `adapters/server/`, `adapters/comfyui/nodes/aesthetic_score/` | `adapters/.../tests/` (`adapters/server/tests/` exists as empty shell) |

Rule: a `tests/` directory lives **next to the module it tests**; tests may
import across layers, but the README architecture scan includes test files, so
tests must satisfy the dependency table too (use fakes, not real
infrastructure).

---

## 6. Violation Gate (run before finishing each phase)

```bash
python - <<'EOF'
import ast
from pathlib import Path

ROOT = Path(".")  # module root
LAYERS = ("core", "domain", "application", "adapters", "infrastructure")
ALLOWED = {
    "core": (),
    "domain": ("core",),
    "application": ("core", "domain"),
    "adapters": ("core", "domain", "application"),
    "infrastructure": ("core", "domain"),
}
bad = []
for layer, allowed in ALLOWED.items():
    for path in sorted((ROOT / layer).rglob("*.py")):
        if path.is_dir():
            continue
        base = list(path.relative_to(ROOT).parts[:-1])
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            def resolve(node):
                if isinstance(node, ast.ImportFrom):
                    if node.level > 0:
                        n = node.level - 1
                        if n > len(base):
                            return None
                        parts = base[:len(base) - n] + (node.module.split(".") if node.module else [])
                    elif node.module:
                        parts = node.module.split(".")
                    else:
                        return None
                elif isinstance(node, ast.Import):
                    parts = node.names[0].name.split(".")
                else:
                    return None
                if parts and parts[0] in LAYERS:
                    return parts[0]
                return None
            t = resolve(node)
            if t and t != layer and t not in allowed:
                bad.append(f"{path.relative_to(ROOT)}: {layer} -> {t} (L{node.lineno})")
print("\n".join(sorted(bad)) or "CLEAN")
EOF
```

Note: like the README test, this gate treats same-layer imports as legal, so the
two cross-adapter edges (§2.1) are not caught by the scan — they are tracked
manually in Phase 2e and re-checked by review.

---

## 7. Explicitly Out of Scope

- New ComfyUI nodes, new features, new dependencies.
- New test files (existing tests only).
- Anything inside `comfyui_image_scorer_old/` (read-only; user removes it).
- Rewriting infrastructure internals beyond the thin wrapper classes.
- Changing node names, public APIs, or workflow compatibility.
