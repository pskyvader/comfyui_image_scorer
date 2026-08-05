# Reorganization Plan — `comfyui_image_scorer` (v2, remediation)

**Status:** The original reorganization (v1 of this file) was **executed**: all file
moves from the v1 "Move Summary" are done. v2 is the plan for the remaining
remediation: the codebase currently violates its own documented architecture
(verified by AST scan, 146 files), contains broken-package artifacts, and
untracked files that break a fresh checkout.

This revision re-verified every violation count and defect against the current
tree (2026-08). Items marked **done** in §2.3 and §4 were resolved since v2 was
written; everything else is still pending. This file follows `AGENTS.md`, which
wins on any conflict.

`comfyui_image_scorer_old/` is **read-only reference material**. It is removed
manually by the user; this plan never creates, edits, or deletes anything inside it.

---

## 0. Ground Rules (non-negotiable, from README + AGENTS.md)

1. **Venv:** every command (pytest, pyright, import checks) runs in the **ComfyUI
   venv** (`& "E:\ComfyUI\.venv\Scripts\Activate.ps1"` first).
2. **Imports:** always **relative** (ComfyUI requirement); at **module scope**.
   Exception: the CLI command modules use lazy inline imports for heavy
   dependencies — that established pattern is allowed until the remaining work
   is fixed, but must not spread to new code.
3. **Typing:** full type hints on public APIs; **pyright strict** must pass
   (`"typeCheckingMode": "strict"` in `pyrightconfig.json` — the file is
   currently missing, see §2.3 item 9).
4. **No `try`/`except` blocks** anywhere — let failures surface with clear
   errors. The only exception is the batch size profiler, where it is part of
   the function's working.
5. **Tests:** do **not** create any test files in this effort. **Existing tests
   must keep passing** (`pytest`).
6. **Test locations:** colocated `tests/` subdirectory next to the tested module
   (e.g., `domain/graph/tests/`); cross-layer architecture test lives at
   `tests/test_architecture.py`. `pyproject.toml` testpaths:
   `["tests", "adapters", "domain", "core"]`.
7. **Dependency rule:** nothing imports `infrastructure`. Implementations reach
   callers via **dependency injection**; wiring happens at the **composition root**
   in `adapters/` (`adapters/server/main.py`, `adapters/cli/main.py`,
   `adapters/comfyui/`). Violations are fixed by moving code across the boundary —
   never by relaxing the rule.
8. **State:** no global mutable state in `core`/`domain`/`application`. Wiring
   state lives in `adapters` or `infrastructure`.
9. **Configuration** enters only via `core.configuration` — no scattered
   `os.getenv`/path resolution in domain/application code.
10. **No internet requests.** The only download path is the `files download models`
    CLI command; runtime loading is offline with a fail-fast hint.
11. **Compatibility:** preserve node names, APIs, workflow behavior, file layout.
12. **No new dependencies.**
13. **No defaults:** `.get(..., default)` is highly discouraged and strictly
    forbidden for config objects; avoid default function arguments; state
    ambiguous parameter values explicitly at every call site.
14. Keep changes **small and direct** — narrowest code path per fix.

---
 
## 0. Immediate: Delete Dead Code (first)
 
Before any structural changes, remove every symbol with zero callers across the
entire module (excluding `comfyui_image_scorer_old/` and `typings/`). This cleans
the baseline so subsequent gates (layer scan, unused-arguments, pyright) run on
actual code, and it shrinks the surface that those gates must check.
 
### 0.1 Dead top-level functions, classes, constants (verified by AST scan + grep)
 
| File | Symbol | Line | Note |
|---|---|---|---|
| `core/io/serialization.py` | `load_single_entry_mapping` | 182 | No callers anywhere |
| `core/observability/logger.py` | `TaskLogHandler` (class) | 328 | Never instantiated or referenced |
| `core/observability/logger.py` | `log_message` | 739 | No callers |
| `core/observability/logger.py` | `set_log_filter_hook` | 79 | No callers; also dead import in `adapters/server/main.py:19` |
| `core/utilities/utils.py` | `parse_custom_text` | 10 | Whole module dead (legacy feature moved into `_recursive_parse_json`) |
| `core/utilities/utils.py` | `first_present` | 20 | Whole module dead (replaced by `get_value_from_entry`) |
| `core/filesystem/paths.py` | `hyperparameters_statistics` | 24 | Constant, no callers (legacy HPO ledger dropped in rewrite) |
| `domain/comparison/algorithm/graph_helpers.py` | `get_chain_length` | 68 | Module-level helper, never imported |
| `domain/comparison/algorithm/graph_helpers.py` | `group_nodes_by_extreme` | 81 | Module-level helper, never imported |
| `domain/comparison/algorithm/graph_helpers.py` | `find_lowest_confidence_images` | 161 | Module-level helper, never imported |
| `domain/comparison/constants.py` | `PAIR_TYPE_BOOTSTRAP` | 3 | Constant, no callers |
| `domain/comparison/constants.py` | `PAIR_TYPE_INSERTION` | 4 | Constant, no callers |
| `domain/comparison/constants.py` | `PAIR_TYPE_REFINEMENT` | 5 | Constant, no callers |
| `domain/comparison/constants.py` | `PAIR_TYPE_FALLBACK` | 6 | Constant, no callers |
| `domain/comparison/constants.py` | `PAIR_TYPE_COLLAPSIBLE` | 7 | Constant, no callers |
| `infrastructure/persistence/comparisons_repository.py` | `get_recent_comparisons` | 143 | Not in `ComparisonRepository` protocol, no callers |
| `infrastructure/persistence/comparisons_repository.py` | `get_comparison_count` | 161 | Not in protocol, no callers |
| `infrastructure/persistence/comparisons_repository.py` | `delete_comparisons_for_image` | 222 | Not in protocol, no callers |
| `infrastructure/persistence/comparisons_repository.py` | `delete_comparison_by_id` | 232 | Not in protocol, no callers |
| `infrastructure/persistence/comparisons_repository.py` | `delete_comparison` | 239 | Not in protocol, no callers |
| `infrastructure/persistence/images_repository.py` | `update_image_score` | 105 | Not in `ImageRepository` protocol, no callers |
| `infrastructure/persistence/images_repository.py` | `get_scored_images` | 129 | Not in protocol, no callers |
| `infrastructure/persistence/images_repository.py` | `get_images_by_tier` | 146 | Not in protocol, no callers |
| `infrastructure/persistence/images_repository.py` | `delete_image` | 161 | Not in protocol, no callers |
| `infrastructure/persistence/database.py` | `get_meta_value` | 127 | No callers |
| `infrastructure/persistence/path_handler.py` | `append_comparison_history_to_json` | 232 | No callers; also has 3 unused args per §6b |
| `adapters/server/main.py` | `start_background_scanner` | 194 | Defined, never invoked |
 
### 0.2 Dead imports (ruff `F401` — 39 fixable)
 
Run `ruff check --select F401 --exclude comfyui_image_scorer_old --exclude typings --fix .`
to remove them all. Summary by file:
 
- `adapters/cli/commands/database.py` — `update_scores_after_comparison`
- `adapters/server/endpoints/analysis.py` — `get_all_comparisons`
- `adapters/server/endpoints/comparison.py` — `comparison_recorder`
- `adapters/server/endpoints/data_transform.py` — `config`
- `adapters/server/endpoints/maps.py` — `flask.request`
- `adapters/server/main.py` — `typing.Any`, `typing.Callable`, `logging`, `SharedLogger`, `set_log_filter_hook`, `output_dir`
- `adapters/server/processor.py` — `time`
- `application/analysis/run_matrix_analysis.py` — `write_single_jsonl`
- `application/analysis/run_stats.py` — `collections.defaultdict`
- `application/data_transform/config/maps.py` — `typing.Any`
- `domain/analysis/helpers.py` — `typing.Any`, `time`
- `domain/comparison/algorithm/merge_sort_ranker.py` — `collections.deque`
- `domain/comparison/algorithm/phase_order.py` — `time`, `MIN_CHAIN_THRESHOLD`
- `domain/comparison/comparison_recorder.py` — `time`, `Rating`
- `domain/comparison/state.py` — `collections.deque`, `config`, `get_image_count`
- `domain/graph/tests/test_chain_manager.py` — `get_images_with_only_wins`, `get_images_with_only_losses`
- `domain/training/parameter_analysis.py` — `pandas`, `matplotlib.colors.Normalize`
- `domain/training/plot.py` — `scipy.special.softmax`
- `domain/vectors/tests/test_terms.py` — `ExtractionResult`
- `infrastructure/loading/training_loader.py` — `typing.Iterator`, `index_file`
- `infrastructure/ml_models/training/model_trainer.py` — `os`
- `infrastructure/persistence/comparisons_repository.py` — `time`
- `infrastructure/persistence/database.py` — `time`
- `infrastructure/persistence/path_handler.py` — `json`, `time`
- `core/filesystem/paths.py` — `PROJECT_ROOT`
 
> **Scope note:** the scan covered all `.py` files except `comfyui_image_scorer_old/`
> and `typings/`. It excluded decorated functions (Flask route handlers), dunder
> methods, and `test_*` functions (pytest discovers them by name). Method-level
> dead code inside classes was not exhaustively scanned; the list above covers
> top-level symbols and imports. If any of the listed items turns out to be
> referenced via string/indirect access, keep it and update the gate.
 
### 0.3 Move `core/utilities/tasks.py` to `adapters/server/tasks.py` (server-specific)
 
The four background-task functions — `start_task`, `set_task_output`, `get_task_status`,
`cancel_task` — are **only** used by `adapters/server/endpoints/*.py` (database,
analysis, data_transform, training endpoints). They are Flask server orchestration
plumbing, not a shared primitive. Moving them to `adapters/server/tasks.py`:
- Keeps core restricted to truly generic utilities (settings, paths, serialization,
  concurrency, logging).
- Places server-specific state next to its only consumers.
- Requires updating ~8 import lines in `adapters/server/endpoints/` and removing
  `core/utilities/tasks.py`.
 
### 0.4 Move `domain/analysis/helpers.py:distribute` to `core/utilities/analysis.py` (stateless utility)
 
The `distribute(values, buckets)` function is a pure bucket-counting helper with
zero domain knowledge (no imports from domain/application, no domain types). It is
called only by `adapters/server/endpoints/analysis.py` (6 sites). Moving it to
`core/utilities/analysis.py` keeps domain for actual domain logic and puts the
stateless helper where generic utilities live.
 
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

### 2.1 Layer import violations — 66 statements across 26 files (re-verified 2026-08)

| Rule broken | Count | Files |
|---|---|---|
| `application → infrastructure` | 17 | `services/scoring_service.py:19-22`, `services/vector_list.py:20`, `services/graph_service.py:366,371,378,385` (inline), `analysis/run_stats.py:4-5`, `data_transform/prepare_data.py:26,30-31`, `data_transform/config/maps.py:13`, `hyperparameters/hyperparameter_optimizer.py:15-16` |
| `adapters → infrastructure` | 40 | `server/main.py:23-29`, `server/processor.py:29-53` (5), `server/endpoints/comparison.py:21-104` (9), `server/endpoints/database.py:9-17` (5), `server/endpoints/analysis.py:13-17`, `server/endpoints/gallery.py:11-12`, `server/endpoints/maps.py:8`, `cli/main.py:281-296`, `cli/commands/database.py:9-38` (5), `cli/commands/training.py:10-11`, `cli/commands/server.py:12`, `comfyui/nodes/aesthetic_score/node.py:4` |
| `domain → infrastructure` | 8 | `comparison/state.py:10`, `vectors/image_vector.py:14,18`, `vectors/embedding_vector.py:12`, `vectors/map_vector.py:3`, `vectors/person_map_vector.py:3`, `training/plot.py:16`, `graph/tests/test_chain_manager.py:13` |
| `domain → application` | 1 | `graph/tests/test_chain_manager.py:11` |
| **Subtotal (layer violations)** | **66** | **26 files** |
| cross-adapter (`adapters/*` → other `adapters/*`) | 2 | `cli/commands/server.py:15` → `server.main`; `cli/commands/database.py:21` → `server.processor` (same 2 files already counted above) |

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

### 2.3 Structural defects (status re-verified 2026-08)

1. `application/data_transform/__init__.py` and `application/hyperparameters/__init__.py`
   are **empty directories**, not files → those subpackages only import as
   namespace packages; the real `__init__.py` was never committed. **Still present.**
2. **Untracked but imported** (fresh checkout breaks):
   `application/data_transform/config/` (imported by `prepare_data.py`),
   `infrastructure/external_services/mediapipe_models.py` (imported by `cli/main.py`).
   **Done — both are git-tracked now.**
3. `core/observability/logger.py:728` — leftover debug `print(f"cleared:{_cleared}")`.
   **Still present.**
4. `comfyui_image_scorer_old/` — legacy copy of the whole codebase (gitignored).
   **Removed manually by the user**; may be read for reference only. **Still present.**
5. `setup.py` — legacy packaging (with `package_dir = {PKG: "."}` hack); the
   package is never pip-installed; `pyproject.toml` is the build config.
   **Done — deleted.**
6. `scorer.py` — **kept** (decision 2026-08): `python scorer.py <command>`
   stays the main CLI entry point (least text to run a command); the
   `pyproject.toml` console script remains as an equivalent. No longer flagged
   for deletion.
7. `FUNCTION_INDEX.md` — was stale. **Done — refreshed in this revision**
   (documentation-only): stale signatures replaced (see §4 note), the
   "not yet on disk" list updated.
8. `adapters/server/middleware/`, `adapters/server/tests/`,
   `application/dto/`, `application/ports/`, `domain/database/tests/` — empty
   shells (only `__init__.py`). **Still present.**
9. `pyrightconfig.json` — **missing on disk** (deleted in commit `7397304`,
   "structure change in progress"). The documented `pyright` strict gate
   (§0 rule 3, Phase 1 gate) cannot run as specified until it is recreated:
   `"typeCheckingMode": "strict"`, exclude `comfyui_image_scorer_old/`, and
   `extraPaths` pointing at the ComfyUI root so `folder_paths`/`comfy` resolve.
10. `requirements.txt` — **done**: regenerated via `uv pip compile
    pyproject.toml -o requirements.txt` (2026-08, 335 pinned lines, torch
    `2.13.0+cu130` from the `cu130` index). The `.github/workflows/
    check-deps.yml` diff check can now run. Regenerate + commit whenever
    `pyproject.toml` dependencies change; per `AGENTS.md` it is regenerated,
    never hand-edited.
11. `typings/` — stale stubs from the old structure (torch, matplotlib,
    scipy, sklearn, `shared`/`nodes` modules). When used as `stubPath` they
    shadow the real installed packages during pyright analysis and produce a
    misleading error baseline. Remove once `pyrightconfig.json` is recreated
    (item 9) so types resolve from the installed packages instead.

### 2.4 README mismatches — fixed in this revision (documentation-only, 2026-08)

- `domain/loading/` listed under domain (README line 133, "Model loaders") —
  does not exist. README line 190 already anticipates it: `ml_models/`
  implements `domain.loading` **ports**. Phase 2a creates `domain/loading/` with
  the port interfaces, so the fix is to reword line 133 to "loader port
  interfaces" (implementations live in `infrastructure/loading/`) — not to
  remove the entry. **Fixed.**
- `application/services` lists RankingService/GalleryService/MapService/... —
  actual: `graph_service.py`, `vector_list.py`, `scoring_service.py`. **Fixed.**
- `adapters/comfyui/nodes/` lists ranking/, gallery/, maps/ groups — only
  `aesthetic_score/` exists. **Fixed.**
- CLI commands list mentions `files`, `analyze`, `output.py` — actual commands:
  server, training, vectors, database; `files` and `analyze` are inline
  subparsers in `cli/main.py`, and `output.py` does not exist. **Fixed.**
- `python scorer.py --help` reference — obsolete if `scorer.py` is deleted;
  README now points at the `comfyui-scorer` console script. **Fixed.**
- `tests/test_architecture.py` is documented (lines 214-242) but the root
  `tests/` directory does not exist yet — README now marks it explicitly as
  not-yet-on-disk and names the §6 script as the current gate. **Fixed.**

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
- **Composition roots are the documented exception to "nothing imports
  infrastructure"** (`AGENTS.md`): the wiring modules in adapters
  (`adapters/server/main.py`, `adapters/cli/main.py`, `adapters/comfyui/`)
  construct the infra singletons once and inject them. The §6 gate flags those
  imports, so they are reviewed manually — the target is that they are the
  *only* adapters→infrastructure edges left.

---

## 4. Remediation Phases

### Phase 1 — Repo hygiene & importability (mechanical, no design change)

1. Replace the two `__init__.py` **directories** in `application/data_transform/`
   and `application/hyperparameters/` with real empty `__init__.py` files
   (delete dirs, `git add` the files). **Pending** (§2.3 item 1).
2. `git add application/data_transform/config/` and
   `infrastructure/external_services/mediapipe_models.py`. **Done.**
3. Remove the debug print at `core/observability/logger.py:728`. **Pending**
   (§2.3 item 3).
4. Delete `setup.py` — **done**. `scorer.py` — **kept** as the main CLI entry
   point (§2.3 item 6). Stale `FUNCTION_INDEX.md` —
   **refreshed instead of deleted** (this revision, documentation-only;
   stale signatures replaced, "not yet on disk" list updated).
5. `comfyui_image_scorer_old/`: **user deletes manually** — not part of this plan.
6. Restore the pyright gate: recreate `pyrightconfig.json` (strict, exclude
   `comfyui_image_scorer_old/`, `extraPaths` to the ComfyUI root) and remove the
   stale `typings/` directory (§2.3 items 9, 11).
7. `requirements.txt` — **done** (§2.3 item 10).

**Gate:** `pytest` green; `pyright` strict clean (requires item 6).

### Phase 2 — Dependency inversion (the 66 violations)

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

**2d. Application (17 imports, 7 files):**
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
  functions; `cli/commands/*` drop their infra imports (40 edges incl. the
  `files`/`analyze` inline imports in `main.py`).
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

**Done in this revision (documentation-only).** The §2.4 mismatches were fixed
in `README.md` on 2026-08: `domain/loading/` reworded to loader **port
interfaces**, services list corrected, comfyui node groups corrected (only
`aesthetic_score/`), CLI commands corrected (`files`/`analyze` are inline
subparsers, no `output.py`), `scorer.py` reference replaced by the
`comfyui-scorer` console script, and the `tests/test_architecture.py` snippet
marked as not-yet-on-disk with the §6 script named as the current gate.

The `core` dependency-table row stays per the Phase 3 decision (not yet made).

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
4. **Note:** the `pyright` gate is currently blocked by the missing
   `pyrightconfig.json` (Phase 1 item 6). Run it with a local strict config
   until item 6 is done.

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

## 6b. Unused-Arguments Gate

**Rule:** no unused function/method arguments. Remove the argument from the
signature and fix all callers. Framework callbacks that must keep a positional
slot (Flask error handlers, monkey-patched stdlib hooks) keep the slot with an
underscore-prefixed name (`_e`).

```bash
ruff check --select ARG --target-version py313 \
  --exclude comfyui_image_scorer_old --exclude typings .
```

**Baseline (2026-08): 27 findings** (line numbers are for the current working
tree):

| File | Arg(s) | Note |
|---|---|---|
| `adapters/cli/commands/database.py:8,20,30` | `**kwargs` (3) | `cleanup` / `rebuild` / `recalculate` |
| `adapters/cli/commands/vectors.py:62,71,80` | `**kwargs` (3) | `run_full_vectors` / `run_scores` / `run_all` |
| `adapters/server/main.py:166` | `e` | `not_found` Flask handler → `_e` |
| `core/observability/logger.py:33,35` | `self`, `stacklevel` | `_custom_find_caller` → `_self`, `_stacklevel` |
| `domain/analysis/image_analysis.py:71` | `batch_sizer` | `ImageAnalysis.__init__` |
| `domain/comparison/algorithm/pair_active.py:148,215,307,344,439,525-526` | `comparison_repo`, `pair_set`, `cg` (7) | phase functions carrying unused protocol deps |
| `domain/comparison/comparison_recorder.py:65-69` | `winner_filename`, `loser_filename`, `impact_factor` | `update_scores_after_comparison` |
| `domain/data_transformation/data_transformer.py:122` | `verbose` | `filter_unused_features` |
| `domain/graph/component_proxy.py:36` | `minimal_required` | `ComponentProxy.get_chains` |
| `domain/training/plot.py:862,911` | `alpha`, `n` | `plot_positional_bbox`, `plot_detection_presence` |
| `infrastructure/ml_models/training/model_trainer.py:363` | `status_bar`, `enable_plotting` | `create_callbacks` |
| `infrastructure/persistence/path_handler.py:234` | `comparison_data` | `append_comparison_history_to_json` |

---

## 6c. Installable-Module Gate

**Rule:** the module itself is never pip-installed — no `setup.py`, no
`pip install .`, no `pip install -e .`. Only its dependencies are installed
(`pip install -r requirements.txt`, generated from `pyproject.toml`).
`setup.py` was deleted (2026-08); this gate keeps it that way.

```bash
grep -rniE "pip install (-e )?\.|setup\.py" \
  --exclude-dir=comfyui_image_scorer_old --exclude-dir=typings .
```

**Baseline:** clean (no matches).

---

## 7. Explicitly Out of Scope

- New ComfyUI nodes, new features, new dependencies.
- New test files (existing tests only).
- Anything inside `comfyui_image_scorer_old/` (read-only; user removes it).
- Rewriting infrastructure internals beyond the thin wrapper classes.
- Changing node names, public APIs, or workflow compatibility.
