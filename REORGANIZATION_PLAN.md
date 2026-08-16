# Reorganization Plan — `comfyui_image_scorer` (v4)

**Status (2026-08):** v2 is complete (verified against the live tree: 28
adapter-wiring statements in the three composition roots, pytest 30 passed,
ruff ARG/F401 clean, pyright 701-error baseline with zero new, node smoke OK).
v3 (CLI-parity remediation) is superseded by this revision, which extends it:
**strict CLI parity, a full rename cascade to CLI command names, and the
complete removal of the server task system.** Every command endpoint becomes
a single direct call to its CLI command's function — no reimplementation
(§1.1). The CLI (`adapters/cli/`) is the source of truth and is **not
modified**.

**Scope:** `adapters/server/` (endpoints, `main.py`, `deps.py`),
`adapters/*/frontend/` folders, `adapters/server/frontend/`, the docs that
describe the module state (`AGENTS.md`, `README.md`, `FUNCTION_INDEX.md`),
and the frontend `index.html`/`index.js`. Nothing else in the module is
touched.

**Strict parity rule:** every command endpoint maps to a CLI command; every
endpoint with no CLI counterpart is removed (with its frontend
buttons/actions). Exceptions — not commands, kept as server infrastructure:
- Static/asset routes in `adapters/server/main.py` (`/`, `/css/`, `/js/`,
  `/static/<section>/...`, `/images/...`, `/image/...`, `/output/ranked/...`,
  the `/api/*` 404 catch, error handlers): these *are* the `server` command.
- Out of scope entirely: `comparison_bp`, `gallery_bp`, `maps_bp` and their
  frontends (server-only features, per user decision).

`comfyui_image_scorer_old/` is read-only reference material, removed manually
by the user. This plan never creates, edits, or deletes anything inside it.

---

## 0. Ground Rules (from README + module AGENTS.md, abbreviated)

1. Every command runs in the ComfyUI venv (`& "E:\ComfyUI\.venv\Scripts\Activate.ps1"` first).
2. Relative imports at module scope, at the top of each file. No inline
   imports anywhere in the module except `adapters/cli/main.py` (the one
   established lazy dispatch pattern).
3. pyright strict must pass (`pyrightconfig.json`).
4. No `try`/`except` blocks — failures surface with clear errors.
5. No new test files. Existing tests must keep passing.
6. No global mutable state in `core`/`domain`/`application`.
7. Nothing imports `infrastructure` except the three composition roots
   (`adapters/server/main.py`, `adapters/cli/deps.py`, `adapters/comfyui/services.py`).
   Endpoints receive everything through `ServerDeps`.
8. No defaults: config objects and function args avoid default values; state
   ambiguous parameter values explicitly at every call site.
9. No internet requests unless explicitly user-initiated: the only download
   path is `files download models` and its matching server endpoint, triggered
   by a button click (never background activity).
10. Compatibility rule is **suspended for this revision where it conflicts
    with the user decisions**: section URLs, blueprint prefixes, and frontend
    folder/file names change to match CLI command names (full rename cascade).
    Node names and workflow behavior remain untouched.
11. No new dependencies.
12. Small, direct changes; narrowest code path per fix.
13. Command endpoints call the CLI command functions directly
    (`adapters/cli/commands/*`, or the exact body CLI `main.py` runs for
    `files`/`analyze`): endpoint body = one call + response wrapping. No
    endpoint reimplements command logic. Endpoints may import
    `adapters/cli/commands/*` (adapters→adapters; adds zero infrastructure
    import statements to endpoints — the §4 AST gate holds).

---

## 1. Source of Truth — CLI command table

| Section | Command | Behavior (from `adapters/cli/`) |
|---|---|---|
| `server` | `server` | runs this Flask server |
| `training` | `train-model` | load training data → train `config["training"]["top1"]` → save model + plots (`commands/training.py:14`) |
| `training` | `hpo` | `run_hpo_cycles` with `--cycles/--optimization-steps/--max-combos`, `None` → config defaults |
| `build` | `split-vectors` | `build_split_files` with `--limit/--batch` loop, then `remove_derived_caches` (`commands/vectors.py:18`) |
| `build` | `full-vectors` | `build_full_files` from existing splits (`commands/vectors.py:69`) |
| `build` | `scores` | `run_rebuild_scores_only` (`commands/vectors.py:82`) |
| `build` | `all` | split → full → scores (`commands/vectors.py:91`) |
| `database` | `cleanup` | `comparison_repo.clean_comparisons()` + `vacuum_database()` (`commands/database.py:9`) |
| `database` | `rebuild` | `processor.rebuild_database_from_ranked()` (`commands/database.py:18`) |
| `database` | `recalculate` | reset all ratings → `replay_ratings` → update each image (`commands/database.py:24`) |
| `files` | `remove vectors` | `delete_full_vectors()` |
| `files` | `remove models` | `remove_models()` |
| `files` | `remove maps` | `remove_directory(maps_dir)` |
| `files` | `remove downloaded-models` | `remove_directory(mediapipe_models_dir)` |
| `files` | `download models` | `download_configured_models()` + `download_mediapipe_models()` (user-initiated) |
| `files` | `cleanup` | `deduplicate_scored(root=None, dry_run, limit)` + `cleanup_orphans(root=None, dry_run)` |
| `analyze` | `parameters` | `run_parameter_analysis()` |
| `analyze` | `matrix` | `run_matrix_analysis()` |
| `analyze` | `stats` | `run_stats(image_repo, comparison_repo)` |

---

## 1.1 Endpoint → CLI function parity contract

Every command endpoint's body is **one call to the function its CLI command
runs** — the `adapters/cli/commands/*.py` wrappers, or the exact body CLI
`main.py` executes for `files`/`analyze` — wrapped in the §3.2 response
shape. No endpoint reimplements command logic.

| Endpoint (after §3.3 cascade) | CLI command | Function(s) called |
|---|---|---|
| `POST /api/training/train` | `training train-model` | `train_model(deps)` |
| `POST /api/training/hpo` | `training hpo` | `run_hpo(deps, cycles, optimization_steps, max_combos)` — body params, `None` → config defaults |
| `POST /api/build/prepare` — `mode=split` | `build split-vectors` | `run_split_vectors(limit, batch, deps)` |
| `POST /api/build/prepare` — `mode=full` | `build full-vectors` | `run_full_vectors(deps)` |
| `POST /api/build/prepare` — default | `build all` | `run_all(limit, batch, deps)` |
| `POST /api/build/delete-vectors` | `files remove vectors` | `delete_full_vectors()` |
| `POST /api/database/rebuild-db` | `database rebuild` | `rebuild(deps)` |
| `POST /api/database/recalculate` | `database recalculate` | `recalculate(deps)` |
| `POST /api/database/cleanup` | `database cleanup` | `cleanup(deps)` |
| `POST /api/files/remove-models` | `files remove models` | `remove_models()` |
| `POST /api/files/remove-maps` | `files remove maps` | `remove_directory(Path(maps_dir))` |
| `POST /api/files/remove-downloaded-models` | `files remove downloaded-models` | `remove_directory(Path(mediapipe_models_dir))` |
| `POST /api/files/download-models` | `files download models` | `os.environ["HF_HUB_OFFLINE"] = "0"`; `deps.download_configured_models()`; `deps.download_mediapipe_models()` |
| `POST /api/files/cleanup` | `files cleanup` | `deps.deduplicate_scored(root=None, dry_run, limit)`; `deps.cleanup_orphans(root=None, dry_run, delete_enabled=not dry_run)` |
| `GET /api/analyze/stats` | `analyze stats` | `run_stats(image_repo=deps.image_repo, comparison_repo=deps.comparison_repo)` |
| `POST /api/analyze/analyze-parameters` | `analyze parameters` | `run_parameter_analysis()` |
| `POST /api/analyze/analyze-matrix` | `analyze matrix` | `run_matrix_analysis()` |

Mechanics:
- Endpoints import the command functions from `adapters/cli/commands/*`
  (adapters→adapters; the endpoints gain zero infrastructure import
  statements, so the §4 AST gate holds). `analyze`/`files` call the same
  application/core functions CLI `main.py` calls, with the same arguments.
- `ServerDeps` grows to a superset of `CLIDeps` and gains a `to_cli_deps()`
  helper in `adapters/server/deps.py`; endpoints pass its result to the
  command functions. New fields: `vacuum_database`,
  `download_configured_models`, `download_mediapipe_models` (§3.7 #28).
- Response: `{"status": "done", "result": <command return value>, "log":
  <captured output>}` (§3.2).
- Server startup sets the matplotlib Agg backend so the CLI's `plt.show()`
  calls (`train_model`) are no-ops in server context.

---

## 2. Section → endpoint file mapping (after rename cascade)

| CLI section | Endpoint file | Blueprint prefix | Frontend folder | Section name |
|---|---|---|---|---|
| `server` | the server itself | — | `adapters/server/frontend/` | — |
| `training` | `endpoints/training.py` | `/api/training` | `adapters/training/frontend/` (renamed from `training_hyperparameters/`) | `training` |
| `build` | `endpoints/build.py` (renamed from `data_transform.py`) | `/api/build` (was `/api/data`) | `adapters/build/frontend/` (renamed from `data_transform/`) | `build` (was `data`) |
| `database` | `endpoints/database.py` | `/api/database` | `adapters/database/frontend/` (renamed from `database_structure/`) | `database` |
| `files` | `endpoints/files.py` (new) | `/api/files` | (buttons live in the database view) | — |
| `analyze` | `endpoints/analyze.py` (renamed from `analysis.py`) | `/api/analyze` (was `/api/analysis`) | `adapters/analyze/frontend/` (renamed from `analysis/`) | `analyze` (was `analysis`) |

`comparison`, `gallery`, `maps`, `maps2` frontends and their blueprints are
server-only features — out of scope, unchanged.

---

## 3. Tasks

### 3.1 Remove the task system entirely

1. **Delete `adapters/server/tasks.py`** (`start_task`, `get_task_status`,
   `set_task_output`, `cancel_task`, `TaskOutput`, `CaptureStream`, task
   stores/locks) and remove every import of it.
2. **Delete `adapters/server/frontend/js/task_poller.js`** (incl. the dead
   SSE EventSource logic) and its `<script>` tag in `index.html`.
3. **All command endpoints become synchronous:** one call to the CLI command
   function (§1.1), capture logs, and return
   `{"status": "done", "result": <command return value>, "log": ...}`
   (long commands block the request — accepted design decision).
4. **Delete every `GET /<bp>/task/<task_id>` route** (and the
   `/task/<task_id>/cancel` route in the old analysis bp). No task routes
   remain anywhere.

### 3.2 Backend logger rework + frontend log display

5. **`core/observability/logger.py` needs a synchronous log-capture helper**
   (the "backend logger work"): a context manager / capture function that
   collects log output (stdout/stderr + package log records) during an
   endpoint's execution, so the response can carry the command's log text.
   Small, single helper — no new dependencies.
6. **Frontend command views keep their log areas** but they are now fed
   **one-shot**: on button click the view awaits the command response and
   renders the returned `log` text + `result` into the log area / result
   panel. No polling, no streaming.

### 3.3 Rename cascade (files, folders, prefixes, sections)

7. **Frontend folders** (`git mv`, tracked):
   - `adapters/data_transform/frontend` → `adapters/build/frontend`, files
     `transform.css/html/js` → `build.css/html/js` (class `BuildView`,
     section `build`)
   - `adapters/analysis/frontend` → `adapters/analyze/frontend`, files
     `analysis.css/html/js` → `analyze.css/html/js` (class `AnalyzeView`,
     section `analyze`)
   - `adapters/database_structure/frontend` → `adapters/database/frontend`,
     files `db.css/html/js` → `database.css/html/js` (class `DatabaseView`)
   - `adapters/training_hyperparameters/frontend` → `adapters/training/frontend`
     (files already `training.*`, class `TrainingView`)
   - The package dirs `adapters/data_transform/` and `adapters/analysis/`
     (containing only `__init__.py`) are renamed to `adapters/build/` and
     `adapters/analyze/`. Nothing imports them (verified).
8. **Endpoint files** (`git mv`): `endpoints/data_transform.py` →
   `endpoints/build.py`; `endpoints/analysis.py` → `endpoints/analyze.py`.
9. **Blueprint renames:** `data_bp` → `build_bp` (`/api/data` →
   `/api/build`); `analysis_bp` → `analyze_bp` (`/api/analysis` →
   `/api/analyze`). `training_bp`, `database_bp` unchanged.
10. **`SECTION_FRONTENDS` + `adapters/server/main.py`:** update section keys
    and folder paths (`build`, `analyze`, `database`, `training`), update
    route registrations to the renamed modules.
11. **Frontend index files:** `index.html` (script/style links),
    `index.js` (route names/sections: `data` → `build`, `analysis` →
    `analyze`; `db`/`tools` → `database`), nav links in `index.html`.

### 3.4 `training` — `endpoints/training.py` + `adapters/training/frontend/`

12. **Add `POST /api/training/train`** — body is one call to the CLI command:
    `train_model(deps)` (`adapters/cli/commands/training.py`). The command
    loads the training data, trains `config["training"]["top1"]`, and saves
    the model + plots itself. Server startup sets the matplotlib Agg backend
    so the command's `plt.show()` is a no-op in server context.
13. **`/hpo` is one call to `run_hpo(deps, cycles, optimization_steps,
    max_combos)`** — the request body's `cycles`, `optimization_steps`,
    `max_combos` are passed through; absent/`None` → config defaults (exactly
    like the CLI's `--cycles`/`--optimization-steps`/`--max-combos`).
14. **Remove `POST /api/training/reset`** and **`GET/POST
    /api/training/config`** — no CLI counterpart; move **`POST
    /api/training/remove-models`** to `endpoints/files.py` (§3.7 #27).
15. **Frontend:** remove the "Optimize Hyperparameters" (`optimize-hpo`),
    "View Config" (`get-training-config`), "Reset Training objects"
    (`reset-config`) buttons/actions, and the "Remove Models"
    (`remove-models`) action (its route moves to §3.7). Keep `train-top` →
    `/training/train` and `hpo-cycle` → `/training/hpo`.

### 3.5 `build` — `endpoints/build.py` + `adapters/build/frontend/`

16. **`POST /api/build/prepare` — `mode=split` is one call to
    `run_split_vectors(limit, batch, deps)`** (`adapters/cli/commands/
    vectors.py`): the `batch` loop and the `remove_derived_caches` side
    effect are the command's own (both currently missing from the endpoint).
17. **`mode=full` is one call to `run_full_vectors(deps)`**.
18. **Default branch (`mode=all`) is one call to `run_all(limit, batch,
    deps)`** — split + full + scores, honoring `batch`.
19. Request body carries the CLI's parameters: `mode` (`"split"` | `"full"` |
    `"all"`, default `"all"`), `limit` (0), `batch` (false). **Delete the
    `rebuild_missing_vectors` and `text_only` branches** — they call
    `run_rebuild_missing_vectors()` / `run_text_only()`, which do not exist
    in `application/data_transform/prepare_data.py` and have no CLI
    counterpart. Drop the unused `test_run` flag.
20. **Remove `POST /api/build/scan-import`** — no CLI counterpart.
21. **Frontend:** remove the "Rebuild Missing" and "Text-Only"
    buttons/actions; the prepare view offers Split / Full / All.
22. **Note — `POST /api/build/delete-vectors` (`files remove vectors`):**
    verified 2026-08 — body is one call to `delete_full_vectors()`
    (`core/utilities/helpers.py`), the exact function CLI `files remove
    vectors` runs; it unlinks **only** `vectors_file`, `scores_file`,
    `index_file`, `text_data_file`, `comparisons_file` and **never touches
    the `split/` directory** ("keep the split/ directory intact"). Keep the
    endpoint exactly as-is behaviorally; keep the frontend confirmation
    dialog. (Parity by construction.)

### 3.6 `database` — `endpoints/database.py` + `adapters/database/frontend/`

23. **Add `POST /api/database/recalculate`** — body is one call to
    `recalculate(deps)` (`adapters/cli/commands/database.py`): reset ratings
    → replay → update each image's score/rating/count. The command owns the
    sequence.
24. **Add `POST /api/database/cleanup`** — body is one call to `cleanup(deps)`
    (clean comparisons + `vacuum_database`). Requires adding
    `vacuum_database` to `ServerDeps` (§3.7 #28).
25. **`/rebuild-db` becomes one call to `rebuild(deps)`** — the CLI command
    runs only `processor.rebuild_database_from_ranked()`; drop the
    endpoint's extra `deps.graph.rebuild_from_database()` call.
26. **Remove `GET /api/database/status`**, **`POST /api/database/sync-all`**,
    **`POST /api/database/normalize-comparisons`**, **`POST
    /api/database/deduplicate`**, **`POST /api/database/cleanup-orphans`** —
    no CLI counterpart (dedup + orphans move to the single
    `/api/files/cleanup` route, §3.7 #27).
27. **Frontend:** remove "Sync All → JSON" (`sync-all`), "Normalize
    Comparisons" (`normalize-comparisons`), "Deduplicate"
    (`deduplicate`/`deduplicate-dry`), and "Cleanup Orphans"
    (`cleanup-orphans`/`cleanup-orphans-dry`) buttons/actions, and the dead
    `reset-ratings` action; the dedup/orphan buttons are replaced by the
    single Files Cleanup action (§3.7 #30).

### 3.7 `files` — new `adapters/server/endpoints/files.py`

27. **Create `endpoints/files.py`** (`files_bp`, `/api/files`). Every route
    body is the exact body CLI `main.py` runs for the matching `files`
    command — one call per function, no extra logic:
    - `POST /remove-models` → `remove_models()` (moved from
      `endpoints/training.py`; matches `files remove models`);
    - `POST /remove-maps` → `remove_directory(Path(maps_dir))`;
    - `POST /remove-downloaded-models` →
      `remove_directory(Path(mediapipe_models_dir))`;
    - `POST /download-models` → `os.environ["HF_HUB_OFFLINE"] = "0"`;
      `deps.download_configured_models()`; `deps.download_mediapipe_models()`
      (**user-initiated only** — button click; no background downloads);
    - `POST /cleanup` → `deps.deduplicate_scored(root=None, dry_run, limit)`;
      `deps.cleanup_orphans(root=None, dry_run, delete_enabled=not dry_run)`
      — the whole `files cleanup` command, replacing the old split
      `/api/database/deduplicate` + `/api/database/cleanup-orphans` routes.
      `root=None` everywhere, exactly like the CLI (the old
      `Path(image_root_processed)` argument is gone).
28. **Wire in `adapters/server/deps.py`:** add `vacuum_database`,
    `download_configured_models`, `download_mediapipe_models`, and the
    maps/mediapipe directory removers to `ServerDeps` (making it a superset
    of `CLIDeps`), plus a `to_cli_deps()` helper that builds the `CLIDeps`
    the command functions receive. **No infrastructure imports in the
    endpoint file.**
29. **Register** `register_files_routes(app, deps)` in
    `adapters/server/main.py`.
30. **Frontend (database view):** add "Remove Maps", "Remove Downloaded
    Models", "Download Models", and a single "Files Cleanup" button (with a
    dry-run toggle) — the dedup/orphan buttons it replaces are removed
    (§3.6 #27); the "Remove Models" button moves here from the training view.
    Render the returned log.

### 3.8 `analyze` — `endpoints/analyze.py` + `adapters/analyze/frontend/`

31. **All three command routes become one call to the function CLI `main.py`
    runs for that command** — delete the inline reimplementations:
    - `GET /api/analyze/stats` → `run_stats(image_repo=deps.image_repo,
      comparison_repo=deps.comparison_repo)` — the endpoint's bucket/top/
      bottom computation is deleted; the command's printed report is captured
      into `log` (it is the command's output, per §3.10 #38).
    - `POST /api/analyze/analyze-parameters` → `run_parameter_analysis()` —
      the inline `ParameterAnalyzer` use is deleted. Behavior moves to the
      CLI's: reports land in `output/analysis/`, and empty vectors/text_data
      fail with the command's clear error.
    - `POST /api/analyze/analyze-matrix` → `run_matrix_analysis()` — the
      inline `MatrixAnalyzer` use is deleted; output moves to
      `output/maps/matrix_analysis.json` (the CLI's path).
32. **Remove `GET /api/analyze/report-file`** — no CLI counterpart (frontend
    never calls it). **Frontend:** the stats and analyze views render the
    returned `log` text instead of the old structured JSON.

### 3.9 Docs — align with the final state and this plan

33. **`AGENTS.md`: rules only.** Remove every structural reference
    (architecture section, layer/dependency table, ports, composition roots,
    layout, "Why Things Are Not Always Correct" violations text). Keep only
    rules: venv, commands, imports, typing, no try/except, no tests, state,
    config, internet, deps, style, nodes, commits. Structure belongs to the
    README — AGENTS.md must not mention it.
34. **`README.md`:** the module's structure owner. Update the layout tree
    (renamed folders), dependency table, section/blueprint mapping
    (commands ↔ endpoints), removed routes, removed task system, and the
    "Node Import Verification" snippet if it references old paths.
35. **`FUNCTION_INDEX.md`:** regenerate against the final tree (renamed
    files/classes/actions; dropped task-system symbols).
36. **`REORGANIZATION_PLAN.md`:** mark v4 complete when all gates pass.

### 3.10 Rules audit — compliance tasks (2026-08)

AST scan of the current tree (all layers, excluding
`comfyui_image_scorer_old/`) against the module rules. The same clusters
exist at `21570f4` / `c231460` / `003449d` — each commit reduced them
(try/except 55→56→51, inline imports 35→35→25→26 under the current scan
with only `cli/main.py` exempt, defaults 131→134→115);
none of them introduced a rule. Fix per the rules — never by relaxing one.
`comfyui_image_scorer_old/` stays read-only reference material.

37. **No `try`/`except` — 51 blocks.** Only sanctioned exception: the batch
    sizer profiler (`infrastructure/ml_models/batch_sizer.py`), clean.
    - `infrastructure` (26): `training_loader.py` 6, `model_loader.py` 6,
      `images_repository.py` 5, `path_handler.py` 4, `model_trainer.py` 3,
      `folder_organizer.py` 1, `mediapipe_models.py` 1 (partial-download
      cleanup must stay, but surface the error clearly).
    - `domain` (13): `plot.py` 5, `parameter_analysis.py` 3, one each in
      `image_analysis.py`, `data_transformer.py`, `matrix_analysis.py`,
      `image_vector.py`, `chain_manager.py` (try/finally).
    - `adapters` (9): `analysis.py` 3, `database.py` 3, `data_transform.py` 1,
      `maps.py` 1, `tasks.py` 1 (try/finally — delete with §3.1).
    - `application` (2): `hyperparameter_optimizer.py` 1 (try/finally),
      `scoring_service.py` 1.
    - `core` (1): `utilities/helpers.py`.
38. **No `print()` — 97 calls.** Replace with `get_logger(__name__)`
    (`core/observability/logger.py`): `run_stats.py` 25, `parameter_analysis.py`
    22, `plot.py` 14, `matrix_analysis.py` 13, `data_transformer.py` 11,
    `model_loader.py` 5, `endpoints/database.py` 3, `training_loader.py` 2,
    `model_trainer.py` 1, `logger.py:728` debug leftover (also remove the
    commented-out debug prints at `logger.py:394-397, 554-564`). `run_stats.py`
    prints the CLI report table — that is the command's output; keep it as
    report output and document the choice.
39. **Module-scope imports — 26 imports to move to the top of their files
    across 15 files.** The **only file allowed to keep inline imports is
    `adapters/cli/main.py`** (its lazy command dispatch is the one
    established exception). This overrides the old allowances for `scorer.py`,
    `plot.py`, and `application/analysis/run_*_analysis.py`.
    - `adapters/cli/` — `commands/training.py` 2 (`load_training_data`,
      `run_hpo_cycles`), `commands/vectors.py` 3 (`build_split_files`,
      `build_full_files`, `run_rebuild_scores_only`), `deps.py` 3 (inside
      `build_cli_deps`: `training_loader`, `model_trainer`, `maps_list`).
    - server endpoints — `endpoints/comparison.py` 1 (`ComparisonRecorder`),
      `endpoints/data_transform.py` 1, `endpoints/training.py` 2.
    - module root `__init__.py` 2 — the PEP 562 `__getattr__` node mappings
      become an eager module-scope import of `adapters.comfyui`.
    - `application/` — `analysis/run_parameter_analysis.py` 1
      (`ParameterAnalyzer`), `analysis/run_matrix_analysis.py` 1
      (`MatrixAnalyzer`).
    - `domain/` — `comparison/algorithm/view.py` 2 (`graph_helpers`,
      `MIN_CHAIN_THRESHOLD`), `data_transformation/data_transformer.py` 1
      (`maps_dir`), `training/plot.py` 3 (`Rectangle`, `Normalize`,
      `mannwhitneyu`).
    - `infrastructure/persistence/deduplicate_scored.py` 1
      (`image_root_processed`), `core/observability/logger.py` 1
      (`traceback`).
    - `scorer.py` 2 — the `__main__` guard imports (`sys`, `cli.main`) move
      to module scope; the script entry point still works.
    Already module-scope conditionals at the top of their files — leave
    as-is: the `folder_paths` config guard (`adapters/cli/deps.py:35`,
    `adapters/server/main.py:23`, `adapters/comfyui/services.py:7`) and the
    `if TYPE_CHECKING:` cycle-breaker imports in `domain/graph/` (9).
40. **Function-arg defaults — 115** ("always try to avoid"): 93 in
    core/domain/application, 22 in infrastructure/adapters. `plot.py` 44
    display params dominate (`show`, `cols`, `title` etc.), then
    `comparisons_repository.py` 8, `images_repository.py` 7, `logger.py` 6,
    `repository_ports.py` 5. Remove defaults where all call sites pass the
    value; keep only defaults that are semantically required, with a comment.
41. **Global mutable state — 7 module-level containers** in
    core/domain/application, all constant tables that are never mutated:
    `AGE_LABELS`/`GENDER_LABELS`/`RACE_LABELS`
    (`domain/analysis/attribute_analysis.py`), `POSE_LANDMARK_NAMES`
    (`domain/analysis/mediapipe_analysis.py`), `_PROGRESS_INDICATORS`
    (`core/observability/logger.py`), two `__all__`
    (`domain/database/ports/__init__.py`, `domain/loading/__init__.py`).
    Convert to tuples/frozensets.

---

## 4. Verification (in order, ComfyUI venv)

```powershell
pytest -q                          # 30 passed, no regressions
ruff check --select ARG,F401 --target-version py313 --exclude comfyui_image_scorer_old .
pyright                            # 701-error baseline; zero new errors
```

1. AST layer scan (§6 script of v2) → **28 statements, all in the three
   composition roots** — `endpoints/files.py` adds **zero** new infra imports.
2. Node registration smoke check (README "Node Import Verification" snippet) →
   `AestheticScore` loads.
3. Route smoke check: new routes respond — `/api/training/train`,
   `/api/database/recalculate`, `/api/database/cleanup`, `/api/files/*`
   (`/remove-models`, `/remove-maps`, `/remove-downloaded-models`,
   `/download-models`, `/cleanup`), `/api/build/prepare` (split/full/all
   modes), `/api/training/hpo` body params; removed routes 404 —
   `/api/training/reset`, `/api/training/config`,
   `/api/training/remove-models`, `/api/build/scan-import`,
   `/api/database/status`, `/api/database/sync-all`,
   `/api/database/normalize-comparisons`, `/api/database/deduplicate`,
   `/api/database/cleanup-orphans`, `/api/analyze/report-file`, and every
   `/task/<task_id>` route.
   Parity check: every command endpoint body is exactly one call to its CLI
   function — grep `adapters/server/endpoints/` for `cli.commands` imports
   and the `files`-command bodies; no inline command logic remains
   (`build_split_files`, `run_hpo_cycles`, `ParameterAnalyzer`,
   `MatrixAnalyzer`, `distribute`, bucket computation) in endpoints.
4. Frontend smoke: every section loads (`build`, `analyze`, `database`,
   `training`, `compare`, `gallery`, `chains`), no 404 on static assets, no
   TaskPoller references, and no old `deduplicate`/`cleanup-orphans`/
   `remove-models` actions remain.
5. Inline-import scan: AST walk of every `.py` file (excluding
   `comfyui_image_scorer_old/`) — no `Import`/`ImportFrom` nodes inside
   function bodies or the `__main__` guard anywhere except
   `adapters/cli/main.py`.

---

## 5. Explicitly Out of Scope

- CLI changes (`adapters/cli/`) — source of truth, not modified (including
  the unused `--steps` on `train-model` and unused `--limit` on
  `database cleanup`). Endpoints import and call the CLI command functions
  (§1.1); the CLI's parsers, `main.py`, and `deps.py` are untouched.
- `comparison.py`, `gallery.py`, `maps.py` blueprints and their frontends.
- The `maps` (v1) frontend folder — dead but harmless.
- `core`/`domain`/`application`/`infrastructure` behavior (the logger helper
  in §3.2 #5 is the only non-`adapters` change, and it is additive).
- New ComfyUI nodes, new features, new dependencies, new test files.
- Node names and workflow compatibility.
