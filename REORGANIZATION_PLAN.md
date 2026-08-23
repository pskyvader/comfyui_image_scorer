# Reorganization Plan — `comfyui_image_scorer` (v4)

**Status (2026-08-18):** §3.10 audit complete. Verified gates: **pytest 34
passed**, **ruff ARG/F401 clean** except the untouched `pair_active.py`
ARG001, **pyright 604** (baseline 633 — the +3 was `model_loader.py`'s four
`logger.info` conversions flagged by strict mode and
`parameter_analysis.py`'s term-stats info-args error; fixed by typing the
config dicts and `term_stats`, which also cleared ~27 pre-existing
unknown-variable errors). Tasks 37–39 complete (try/except 51->13 live
sanctioned; prints 97->25 all in the `run_stats.py` report; inline imports
moved to module scope, 26 sanctioned remain). Task 40 (function-arg
defaults) complete:
48 defaults removed across 18 functions (audit 183->135); all gates green
after the change (pyright 604, pytest 34, ruff 1). Task 41 (global mutable
state) complete: the 7 listed containers were already immutable; 5 more
constant tables converted to tuples/frozensets/MappingProxyType; runtime
caches documented as out of scope. §3.10 fully done.
**v4 §3.1–§3.9 are complete** (two execution batches, 2026-08-17 — see the
Progress notes below): task system deleted, rename cascade done, all command
endpoints synchronous CLI calls, docs aligned. Verified baselines: **pytest 34 passed**, **ruff
ARG/F401: 10 errors** at `747b2bc` — all in files this revision deletes or
rewrites (`tasks.py` 3 F401, `endpoints/analysis.py` 1 ARG,
`core/observability/logger.py` 6: F401×3 + ARG001×2 + ARG003×1) — now clean
except the untouched `pair_active.py` ARG001, **pyright 724 errors** at
`747b2bc` (now 604). The §3.10 cluster counts were re-run against the live
tree and match the table below exactly: try/except 51, prints 97, inline
imports 26 statements across 15 files, module-level containers 7. One
**uncommitted user edit** exists in
`domain/comparison/algorithm/pair_active.py` (commented debug line +
reformat) — preserved, out of scope, never touched. During batch-2 route
testing `output/models/` was deleted by a misdirected test stub — it is
regeneratable via `python scorer.py files download models` (user-initiated);
nothing tracked was lost. Restored by the user (2026-08-18) via
`python scorer.py training train-model`.

**v5 scope amendment (user-authorized, 2026-08-18):** the CLI is now modified
beyond the §5 "no CLI changes" rule, with the matching endpoints and
frontend:
- `files remove models` → `files remove generated-models`
  (`POST /api/files/remove-generated-models`)
- `files remove maps` → `files remove vector-maps`
  (`POST /api/files/remove-vector-maps`) — also deletes `split/map/`
  (data-driven map splits are invalidated once the maps tables are gone)
- `files remove vectors` (`POST /api/build/delete-vectors`) now deletes all
  split categories **except `split/image/`** (CLIP embeddings are the only
  at-all-costs folder; recovery requires re-analysis)
- `files cleanup` / `POST /api/files/cleanup` dropped the preview flag and
  the toggle parameters (`delete_enabled` / `--no-delete`) — the command
  always applies changes (`deduplicate_scored(root, limit)` +
  `cleanup_orphans(root)`)
The general test `tests/test_general.py` covers the
resulting contract.

**v5.1 plan amendment (2026-08-22):** comparison/gallery/maps blueprints and
frontends are brought into scope (all "out of scope" references to them below
are removed); the proxy-entry check moves into a `get_db_connection()`
choke point inside `infrastructure/persistence/database.py`;
`/download-models` must restore `HF_HUB_OFFLINE` to its prior value before
returning (no try/catch); ground rule 5 amended to permit new test files;
§3.10 #37 refined into an explicit try/except taxonomy (finally-only cleanup,
translate-and-reraise handlers, OOM-adaptive batching); Pydantic retained in
§3.14 as a user-approved necessary dependency under rule 11;
`adapters/cli/deps.py`'s three lazy infrastructure imports hoist to module
scope (`main.py` dispatch stays lazy); the general suite is renamed to
`tests/test_general.py` and runs only on explicit user prompt — colocated
suites are the default verification.

** §3.1–§3.8
backend + frontend rewrites complete. `tasks.py` and `task_poller.js`
deleted; all command endpoints are synchronous, one call to the CLI command
function, returning `{"status": "done", "result", "log"}` via the new
`capture_log_output()` helper; the rename cascade ran (`build`/`analyze`/
`database`/`training` folders + `endpoints/build.py`/`analyze.py`,
`/api/build`/`/api/analyze` prefixes, `data_bp`/`analysis_bp` →
`build_bp`/`analyze_bp`); `training` exposes only `/train` + `/hpo`;
`build` exposes only `/prepare` (mode split/full/all) + `/delete-vectors`;
`database` exposes `/rebuild-db`/`/recalculate`/`/cleanup` (tasks 23–26 done
ahead of schedule — forced by the `tasks.py` deletion); `analyze` exposes
`/stats`/`/analyze-parameters`/`/analyze-matrix` (tasks 31–32 done ahead of
schedule — the parity rule requires them); `endpoints/files.py` exists with
`/remove-generated-models` only (task 27's remaining routes pending). `ServerDeps` is
now a `CLIDeps` superset with `to_cli_deps()`; matplotlib Agg set at server
startup; frontend views are one-shot log renderers. §3.9 docs and §3.10
rules audit (#37–#41) still pending. Verified: pytest 34 passed, ruff
ARG/F401 clean (only the untouched `pair_active.py` ARG001 remains), pyright
668 errors (baseline 724, zero new), route map matches §1.1 exactly, node
registration OK.

**Progress (2026-08-17, second execution batch — tasks 21–36 done, §3.1–§3.9
complete):** `endpoints/files.py` now has all five routes — `/remove-generated-models`,
`/remove-vector-maps`, `/remove-downloaded-models`, `/download-models`
(user-initiated only, sets `HF_HUB_OFFLINE=0`), `/cleanup` (`limit` body
param) — each body identical to the `files` CLI dispatch in
`cli/main.py`; the database view gained the File Management card (Remove
Generated Models/Vector Maps/Downloaded Models, Download Models, Files
Cleanup with limit input). Docs aligned: `AGENTS.md` was already rules-only (verified,
no edits); `README.md` updated (v4-complete paragraph, renamed layout tree,
commands↔endpoints parity table, dependency-table exception for CLI parity,
30 infra-wiring statements, removed `routing/` — it was an empty dead
package, deleted); `FUNCTION_INDEX.md` regenerated (renamed adapters/
endpoints/frontend sections, `files.py`, `capture_log_output`, dropped
task-system symbols `_TaskOutput`/`CaptureStream`/`SSELogBroadcaster`/
`TaskLogHandler`/`set_log_filter_hook`/`_is_progress_line` and the
`tasks.py`/`routing/` sections; renamed `__init__.py` docstrings refreshed).
Re-check of batch 1 found and fixed one real bug: the renamed CSS files
still targeted the old container IDs (`#transform-container` etc.) — now
`#build-container`/`#analyze-container`/`#database-container`. Pyright:
640 errors (724 baseline — zero new; partial-unknown body-parsing errors
fixed with `dict[str, Any]` + `app: Flask` register signatures on the four
rewritten endpoints). Live smoke: server starts, `/` and `/api/analyze/stats`
respond 200; `/api/files/cleanup` returns 200 with
`{"duplicates_removed", "orphans_cleaned"}` (dedup scan is slow by nature —
~100s on this dataset; faithful CLI semantics). Full gates: pytest 34
passed, ruff ARG/F401 clean (only `pair_active.py`), AST scan 30 infra
statements all in the three composition roots (zero in endpoints), route map
exact, no `/task` routes, no TaskPoller references, no stale frontend
actions, `AestheticScore` loads. **Outstanding:** §3.10 (#37–#41) rules
audit, still pending. **Note:** during route testing `output/models/` was
deleted (test stub misdirected) — it is regeneratable via
`python scorer.py files download models` (user-initiated); nothing tracked
was lost.

**Scope decision (2026-08-17):** execute the full plan **including the §3.10
rules audit** (§3.1–§3.9 + §3.10 #37–#41). Carve-outs honored from §5: the
CLI is not behaviorally modified — `adapters/cli/main.py` **and**
`adapters/cli/deps.py` keep their lazy imports (§5 names the CLI's parsers,
`main.py`, and `deps.py` as untouched; `deps.py` is additionally the
composition root the endpoints consume). Superseded 2026-08-22 (v5.1
amendment): `deps.py`'s three infrastructure imports hoist to module scope;
only `main.py` keeps lazy dispatch; `batch_sizer.py` keeps its
sanctioned try/except (#37); `run_stats.py` keeps its report prints (#38).
Superseded 2026-08-22 (v5.1 amendment): all blueprints are in scope;
`endpoints/maps.py`'s broad except is scheduled for removal under #37.
v3 (CLI-parity remediation) is superseded by this revision, which extends it:
**strict CLI parity, a full rename cascade to CLI command names, and the
complete removal of the server task system.** Every command endpoint becomes
a single direct call to its CLI command's function — no reimplementation
(§1.1). The CLI (`adapters/cli/`) is the source of truth and is **not
behaviorally modified**.

**Scope:** `adapters/server/` (endpoints, `main.py`, `deps.py`),
`adapters/*/frontend/` folders, `adapters/server/frontend/`, the docs that
describe the module state (`AGENTS.md`, `README.md`, `FUNCTION_INDEX.md`),
the frontend `index.html`/`index.js`, and — per the 2026-08-17 scope
decision — the §3.10 rules audit across all layers. The CLI is **not
behaviorally modified** (`cli/main.py` keeps its lazy parser dispatch;
`cli/deps.py`'s three infra imports hoist to module scope per the v5.1
amendment).

**Strict parity rule:** every command endpoint maps to a CLI command; every
endpoint with no CLI counterpart is removed (with its frontend
buttons/actions). Exceptions — not commands, kept as server infrastructure:
- Static/asset routes in `adapters/server/main.py` (`/`, `/css/`, `/js/`,
  `/static/<section>/...`, `/images/...`, `/image/...`, `/output/ranked/...`,
   the `/api/*` 404 catch, error handlers): these *are* the `server` command.

`comfyui_image_scorer_old/` is read-only reference material, removed manually
by the user. This plan never creates, edits, or deletes anything inside it.

---

## 0. Ground Rules (from README + module AGENTS.md, abbreviated)

1. Every command runs in the ComfyUI venv (`& "E:\ComfyUI\.venv\Scripts\Activate.ps1"` first).
2. Relative imports at module scope, at the top of each file. No inline
   imports anywhere in the module except `adapters/cli/main.py` (the one
   established lazy parser-dispatch pattern; v5.1 amendment 2026-08-22
   removed the `adapters/cli/deps.py` exception). Top-of-file conditional
   guards (`folder_paths` availability, `TYPE_CHECKING` cycle-breakers)
   are not inline imports.
3. pyright strict must pass (`pyrightconfig.json`).
4. No `try`/`except` blocks — failures surface with clear errors. Refined
   2026-08-22: finally-only cleanup, translate-and-reraise handlers, and
   OOM-adaptive batching are permitted — see §3.10 #37.
5. New test files are permitted (decision 2026-08-22). Existing tests must
   keep passing.
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
| `files` | `remove vectors` | `delete_full_vectors()` (deletes all splits except `image/`) |
| `files` | `remove generated-models` | `remove_models()` |
| `files` | `remove vector-maps` | `remove_directory(maps_dir)` + `remove_directory(split_dir/"map")` |
| `files` | `remove downloaded-models` | `remove_directory(mediapipe_models_dir)` |
| `files` | `download models` | `download_configured_models()` + `download_mediapipe_models()` (user-initiated) |
| `files` | `cleanup` | `deduplicate_scored(root=None, limit)` + `cleanup_orphans(root=None)` |
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
| `POST /api/files/remove-generated-models` | `files remove generated-models` | `remove_models()` |
| `POST /api/files/remove-vector-maps` | `files remove vector-maps` | `remove_directory(Path(maps_dir))`; `remove_directory(Path(split_dir) / "map")` |
| `POST /api/files/remove-downloaded-models` | `files remove downloaded-models` | `remove_directory(Path(mediapipe_models_dir))` |
| `POST /api/files/download-models` | `files download models` | save the prior `HF_HUB_OFFLINE` value; set `"0"`; `deps.download_configured_models()`; `deps.download_mediapipe_models()`; restore the prior value immediately before returning (delete the key if it was absent) — no try/catch |
| `POST /api/files/cleanup` | `files cleanup` | `deps.deduplicate_scored(root=None, limit)`; `deps.cleanup_orphans(root=None)` |
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
    /api/training/config`** — no CLI counterpart; the training "remove
    models" route moves to `endpoints/files.py` (§3.7 #27) as
    `POST /api/files/remove-generated-models`.
15. **Frontend:** remove the "Optimize Hyperparameters" (`optimize-hpo`),
    "View Config" (`get-training-config`), "Reset Training objects"
    (`reset-config`) buttons/actions, and the "Remove Generated Models"
    (`remove-generated-models`) action (its route moves to §3.7). Keep `train-top` →
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
    - `POST /remove-generated-models` → `remove_models()` (moved from
      `endpoints/training.py`; matches `files remove generated-models`);
    - `POST /remove-vector-maps` → `remove_directory(Path(maps_dir))`;
      `remove_directory(Path(split_dir) / "map")`;
    - `POST /remove-downloaded-models` →
      `remove_directory(Path(mediapipe_models_dir))`;
    - `POST /download-models` → save the prior `HF_HUB_OFFLINE` value;
      `os.environ["HF_HUB_OFFLINE"] = "0"`;
      `deps.download_configured_models()`; `deps.download_mediapipe_models()`;
      restore the prior value immediately before returning (delete the key if
      it was absent). No `try`/`finally`: if a download raises, the variable
      stays `"0"` until process restart (user decision 2026-08-22)
      (**user-initiated only** — button click; no background downloads);
    - `POST /cleanup` → `deps.deduplicate_scored(root=None, limit)`;
      `deps.cleanup_orphans(root=None)`
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
30. **Frontend (database view):** add "Remove Vector Maps", "Remove
    Downloaded Models", "Download Models", and a single "Files Cleanup"
    button (with a limit input) — the dedup/orphan buttons it replaces are
    removed (§3.6 #27); the "Remove Generated Models" button moves here from
    the training view.
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

**In scope for this revision** (scope decision 2026-08-17 — see status
note). AST scan of the live tree (all layers, excluding
`comfyui_image_scorer_old/`): the counts below were re-verified against
commit `747b2bc` and match exactly. The clusters have existed since
`21570f4` / `c231460` / `003449d` — those commits each reduced them
(try/except 55→56→51, inline imports 35→35→25→26 under the current scan
with only `cli/main.py` exempt, defaults 131→134→115) and none of them
introduced a rule. Fix per the rules — never by relaxing one.
`comfyui_image_scorer_old/` stays read-only reference material. Carve-outs
that apply here: `cli/main.py` keeps its lazy parser dispatch (v5.1
amendment removes the `cli/deps.py` allowance); `batch_sizer.py` keeps its
sanctioned try/except (#37);
`run_stats.py` keeps its report prints (#38). Superseded 2026-08-22 (v5.1
amendment): comparison/gallery/maps blueprints are in scope;
`endpoints/maps.py`'s broad except is scheduled for removal under #37.

37. **No `try`/`except` — 51 blocks.** Amended taxonomy (2026-08-22):
    bare error-swallowing `except` blocks are banned; exactly three forms
    are permitted, each carrying a comment stating its purpose:
    - **`try/finally` with no `except` clause** — guaranteed resource/state
      restoration only (mediapipe `.part` temp-file cleanup, recursionlimit
      restore, `_hpo_running` guard, log-capture handler detach).
    - **`except` solely to translate-and-reraise** (`raise ClearError(...)
      from e`, never suppressed) — the `model_loader.py` download-path
      guards producing the missing-model hint.
    - **`except torch.cuda.OutOfMemoryError` as the working of adaptive CUDA
      batching** — the `batch_sizer.py` probe and the `image_vector.py`
      shrink-and-retry loop.
    Everything else fails fast with clear errors.
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
    - `core` (1): `utilities/helpers.py`    .: 51 -> 13 live try blocks at execution (AST-verified; 38 removed). The
    v5.1 amendment (2026-08-22) removes the 13th — the broad
    `except Exception -> 500` in `endpoints/maps.py` — leaving **12**, all
    covered by the three permitted forms above: `batch_sizer.py` probe and
    `image_vector.py` shrink-and-retry (OOM-adaptive batching),
    `model_loader.py` ×6 translate-and-reraise guards (`132`, `188`, `227`,
    `267`, `279`, `290`), and four finally-only cleanups
    (`mediapipe_models.py` partial-download cleanup, `chain_manager.py`
    recursionlimit reset, `hyperparameter_optimizer.py` `_hpo_running`,
    `logger.py` capture-handler detach).
38. **No `print()` — 97 calls.** Replace with `get_logger(__name__)`
    (`core/observability/logger.py`): `run_stats.py` 25, `parameter_analysis.py`
    22, `plot.py` 14, `matrix_analysis.py` 13, `data_transformer.py` 11,
    `model_loader.py` 5, `endpoints/database.py` 3, `training_loader.py` 2,
    `model_trainer.py` 1, `logger.py:548` debug leftover (also remove the
    commented-out debug prints at `logger.py:213, 216, 374, 380-387` and the
    commented-out `frontend_enabled` task-write block at `logger.py:394-397`). `run_stats.py`
    prints the CLI report table — that is the command's output; keep it as
    report output and document the choice.: 97 -> 25 (AST-verified; 72 removed). The remaining 25
    are all in `application/analysis/run_stats.py` — the CLI report table is
    the command's output, kept as documented.
39. **Module-scope imports — 26 imports to move to the top of their files
    across 15 files.** The **only file allowed to keep inline imports is
    `adapters/cli/main.py`** (its lazy parser dispatch is the one
    established exception; v5.1 amendment 2026-08-22 removed the
    `adapters/cli/deps.py` allowance). This overrides the old
    allowances for `scorer.py`, `plot.py`, and
    `application/analysis/run_*_analysis.py`.
    - `adapters/cli/` — `commands/training.py` 2 (`load_training_data`,
      `run_hpo_cycles`), `commands/vectors.py` 3 (`build_split_files`,
      `build_full_files`, `run_rebuild_scores_only`). v5.1 amendment:
      `deps.py`'s 3 lazy imports inside `build_cli_deps`
      (`training_loader`, `model_trainer`, `maps_list`) hoist to the
      module scope of `deps.py` — zero added server-startup weight since
      the server composition root already imports all three at module
      scope (`server/main.py:64–66`); CLI paths import `deps.py` only
      when a command builds deps.
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
    `if TYPE_CHECKING:` cycle-breaker imports in `domain/graph/` (9).: all 26 movable inline imports moved to module scope
    (AST-verified). The v5.1 amendments (2026-08-22):
    `endpoints/comparison.py`'s inline `ComparisonRecorder` import moves to
    module scope, and `build_cli_deps()`'s three infrastructure imports
    hoist to module scope of `deps.py`. Tests are exempt from this rule
    (function-local imports serve per-test isolation). Remaining **22**
    sanctioned exceptions: `cli/main.py` ×10 lazy parser dispatch, the 3
    folder_paths guards, and the `domain/graph/` TYPE_CHECKING
    cycle-breakers (9).
 40. **Function-arg defaults — 115** ("always try to avoid"): 93 in
    core/domain/application, 22 in infrastructure/adapters. `plot.py` 44
    display params dominate (`show`, `cols`, `title` etc.), then
    `comparisons_repository.py` 8, `images_repository.py` 7, `logger.py` 6,
    `repository_ports.py` 5. Remove defaults where all call sites pass the
    value; keep only defaults that are semantically required, with a comment.: removed 48 defaults across 18 functions (audit: 183
    defaulted params in 82 functions -> 135 in 64). Call-site analysis
    (`audit_defaults.py`/`audit_calls.py` in temp) confirmed every removed
    param is passed by all callers. Kept as semantically required:
    `build_score_calibration(num_points=257)`, `calculate_statistics(min_count)`,
    `get_batch_size(bound=None)`, `build(all_filenames=None)`,
    `get_links(better_than/worse_than)`, `get_all_chains(min_length,
    sort_order)`, `get_component(...)`, `get_all_comparisons(weight=None)`,
    `load_single_jsonl(skip_invalid=True)`, `cleanup_orphans` /
    `deduplicate_scored` (`files.py` endpoint calls them with `root=None`),
    `update_image_rating_state(last_compared_at=None)`, display labels in
    `plot.py`, constructor injection params. Verified: pyright 604 (no new
    errors), pytest 34, ruff 1 (sanctioned pair_active).
41. **Global mutable state — 7 module-level containers** in
    core/domain/application, all constant tables that are never mutated:
    `AGE_LABELS`/`GENDER_LABELS`/`RACE_LABELS`
    (`domain/analysis/attribute_analysis.py`), `POSE_LANDMARK_NAMES`
    (`domain/analysis/mediapipe_analysis.py`), `_PROGRESS_INDICATORS`
    (`core/observability/logger.py`), two `__all__`
    (`domain/database/ports/__init__.py`, `domain/loading/__init__.py`).
    Convert to tuples/frozensets.: the 7 listed containers were already immutable
    (`AGE_LABELS`/`GENDER_LABELS`/`RACE_LABELS`, `POSE_LANDMARK_NAMES`, both
    `__all__` are tuples; `_PROGRESS_INDICATORS` deleted with the logger
    cleanup). An AST scan of `core`/`domain`/`application` found 5 additional
    constant tables never mutated, converted now: `SUB_CONFIG_MAPPING` and
    `grid_base` -> `MappingProxyType`, `REQUIRED_ANALYSIS_FIELDS` ->
    `frozenset`, `METRIC_KEYS` and `PHASES` -> tuples. Deliberate runtime
    caches (mutated, not constant tables) stay as-is, out of scope:
    `processed_cache` (image_analysis), `_images_cache` (state),
    `cache_split_data` (vector_list), `_existing_pairs`/`_last_chains_index`
    (phase_order/pair_active — pair_active never touched). Verified: pyright
    604 (no new errors), pytest 34, ruff 1 (sanctioned pair_active).

---

## 4. Verification



## 5. Explicitly Out of Scope

- CLI changes (`adapters/cli/`) — source of truth, not modified behaviorally
  (including the unused `--steps` on `train-model` and unused `--limit` on
  `database cleanup`). Endpoints import and call the CLI command functions
  (§1.1); the CLI's parsers and `main.py` are untouched. Sole exceptions
  (import hygiene only — zero behavior change): the §3.10 #39 module-scope
  import moves in `commands/training.py` and `commands/vectors.py`, and the
  v5.1 hoist of `deps.py`'s three infrastructure imports to module scope.
- `core`/`domain`/`application`/`infrastructure` behavior: **no behavioral
  changes** — the §3.10 fixes (#37–#41) are mechanical rule compliance
  (fail-fast try/except removal, prints → logger, module-scope imports,
  defaults, container types) and the logger helper in §3.2 #5 is additive.
  `domain/comparison/algorithm/pair_active.py` carries an uncommitted user
  edit — never touched.
- New ComfyUI nodes, new features, new dependencies.
- Node names and workflow compatibility.

> Amended 2026-08-22 (v5.1): the comparison/gallery/maps carve-outs above
> were removed — those blueprints and frontends are in scope. New test files
> are permitted (rule 5), and Pydantic is a user-approved necessary
> dependency for §3.14 validation (rule 11's necessity clause).

### 5.1 Proxy-Entry Enforcement (v5 — new)

**Task 3.11 — Proxy-entry enforcement in database functions**

- **Create `_check_proxy_entry()`** inside
  **`infrastructure/persistence/database.py`** and call it once from
  `get_db_connection()` — the single choke point every repository query
  funnels through. No endpoint or CLI command calls it.
- **Mechanism:** inspects the immediate caller via
  `inspect.currentframe().f_back.f_code.co_filename`; path-normalized
  (`os.path.normcase`) whitelist match against the
  **`domain/graph/` directory only** (`node_proxy.py`, `chain_proxy.py`,
  `component_proxy.py`, `chain_manager.py`) — no persistence
  self-whitelist, no other exceptions.
- **Any caller outside this whitelist:** logs warning
  `"DB function called from non-proxy file: {caller_file}. Direct repository
  access detected. This will become an error in v6."`
- **Whitelisted callers:** execution continues unchanged.
- **Warning → error progression:**
  - v5: Warning in logs only (no crash, visible in server output)
  - v6: Will become `RuntimeError` if called from non-whitelisted file
- **Documented consequence (intentional):** infrastructure-internal callers
  are not whitelisted — module-level `init_database()` at import time, the
  SQLite repositories themselves, application services, CLI database
  commands, and endpoints all log warnings in v5. The warnings enumerate
  every bypass route that v6 must route through the `domain/graph/` proxies.
- **Rationale:** Enforces that all database access flows through
  `domain/graph/` proxy classes (`NodeProxy`, `ChainProxy`,
  `ComponentProxy`, `CrystalGraph`), never directly through
  `ImageRepository`/`ComparisonRepository` from endpoints

### 5.2 Comparison Prediction Accuracy Tracking (v5 — frontend-only, session-reset on reload)

- **Purely frontend** — NO backend changes, no API endpoints, no persistent storage
- **2 session-only counters** in JavaScript, initialized to 0 on page load:
  - `prediction_correct` — incremented when user's choice matches the actual
    winner displayed for the current comparison pair
  - `prediction_incorrect` — incremented when user's choice mismatches the
    actual winner
- **Accuracy percentage**: calculated client-side as
  `accuracy_pct = prediction_correct / (prediction_correct +
  prediction_incorrect) × 100`, displayed in the debug/feedback section
- **Tracking flow (frontend only):**
  1. `GET /api/ranking/next-pair` returns a pair with probable winner estimation
     — the frontend shows which image is the "probable winner"
  2. User makes a choice (clicks "Win" or "Lose" for the shown image)
  3. `POST /api/ranking/submit-comparison` records the comparison in the database
  4. **Immediately after**: frontend increments either
     `prediction_correct` or `prediction_incorrect` based on whether the user's
     choice matched the probable winner shown
  5. Debug/feedback section displays current session stats:
     `{prediction_correct, prediction_incorrect, accuracy_pct}`
  5. **On page reload**: both counters reset to 0 (session-only, no persistence)
- **Where to add in frontend** (JS files, not Python):
  - `adapters/server/endpoints/comparison.py` — NO changes, endpoint unchanged
  - `adapters/compare/*.js` or `adapters/gallery/*.js` — add counter variables
    at top of comparison view script, initialize to 0 on `document.addEventListener('DOMContentLoaded')`
  - After `submit-comparison` success: increment correct/incorrect based on
    whether user choice matched the probable winner from the pair data
  - Display in debug section: e.g., `<div>Acc: {accuracy_pct}% ({correct}/{total})</div>`
- **No backend modifications needed** — the counters live entirely in browser
  memory. No API routes, no database columns, no persistence beyond the current
  session. Accuracy is informational only, resets on each page load.

### 5.3 maps3/ik Functionality (v5 — new)

- **Same data as maps2** — reuse the same graph data retrieval pipeline
  (`deps.graph` methods, same comparison/repo access)
- **Frontend visualization differences:**
  - **Nodes sorted top-to-bottom by score** (1.0 at top, 0.0 at bottom)
  - **Horizontal redistribution for equal scores:** When adjacent nodes have
    within-ε same score, spread horizontally with offset based on rank within
    the score group
  - **Diamond shape per component:** Each component forms a horizontal band
    (score range), with same-score nodes grouped horizontally like a diamond
    silhouette
  - **Physics constraint:** Vertical spring forces set to near-zero/very low;
    only horizontal repulsion/attraction active
  - **Visual style:** Distinct from maps2 (different colors, linking style,
    no/minimal vertical movement)
- **Frontend implementation** (design only):
  - New `adapters/maps3/` directory parallel to `adapters/maps2/`
  - `main.js` adapted `ChainMapUI` class with score-based vertical positioning
  - Horizontal clustering for equal-score nodes
  - Physics: `nodeBaseSize`, horizontal `linkStrength`, `repulsionStrength`
    configured for horizontal-only grouping
  - API endpoint: reuse existing `/api/maps/graph-data` or add
    `/api/maps3/graph-data` returning same data with sort indication
- **Purpose:** Provides an alternative visualization that emphasizes score
  ranking (high→low) with natural grouping of similarly-scored images,
  useful for browsing large collections where score ordering matters more than
  chain structure

---

### 3.12 Structural Corrections (v6 — Proposed)

**File I/O and Path Manipulation Layer Violations:**
The `domain` and `application` layers currently handle direct filesystem operations, which violates clean architecture principles. This logic must be moved to the `infrastructure` layer and injected via interfaces.
- **`domain/analysis/image_analysis.py`**: Uses `atomic_write_json` and `os.path.exists`. Move caching/storage logic to an infrastructure repository.
- **`domain/analysis/mediapipe_analysis.py`**: Constructs paths. Path resolution belongs in `infrastructure/filesystem/path_handler.py`.
- **`domain/data_transformation/data_transformer.py`**: Performs direct file I/O.
- **`domain/vectors/image_vector.py`**: Performs direct file I/O.
- **`application/services/image_processor.py`**: Contains deep path manipulation, JSON cleaning, and `shutil` operations. These are infrastructure concerns.
- **`application/data_transform/prepare_data.py`** and **`application/services/vector_list.py`**: Both contain direct path operations.

**Global Mutable State Violations:**
Global state is used across layers, violating architectural rules. This must be refactored into instance-level state managed by the application layer or passed explicitly.
- **`domain/comparison/state.py`**: `_images_cache` is a mutable global variable.
- **`domain/analysis/image_analysis.py`**: Uses a global `processed_cache`.
- **`application/services/image_processor.py`**, **`application/services/vector_list.py`**, and **`application/hyperparameters/hyperparameter_optimizer.py`**: All use the `global` keyword.

**Semantic Misplacements:**
Several functions are placed in layers that don't match their responsibilities. They should be pushed to the lowest possible level (Infrastructure) or moved up to Application if they orchestrate.
- **`core/utilities/helpers.py`**: Functions like `export_image_batch` contain heavy IO/side-effects. The `core` layer must be pure. Move this to `infrastructure` or `adapters`.
- **`domain/training/parameter_analysis.py`**: Contains heavy IO (`load_single_jsonl`, `Path().mkdir`) and plotting logic (`matplotlib`). Plotting and report generation are not domain logic; they belong in `application` or `infrastructure`.
- **`application/services/image_processor.py`**: Should not contain database/JSON cleaning logic. Its responsibility is orchestration, not raw data manipulation.

**Unified Cache Architecture Proposal:**
Currently, caching logic is scattered across several files as module-level global state, leading to untracked lifecycle management and testability issues:
- `_images_cache` (`domain/comparison/state.py`): Caches the images data structure with a timestamp for expiration.
- `processed_cache` (`domain/analysis/image_analysis.py`): Memorizes processed inputs for analysis steps.
- `cache_split_data` (`application/services/vector_list.py`): Caches split mappings for vectors.
- `_existing_pairs` & `_last_chains_index` (`domain/comparison/algorithm/phase_order.py` / `pair_active.py`): Caches algorithm states during pairing.
- `image_cache` (`adapters/server/compressed_image.py`): An in-memory cache for WebP encoded images.
- `_folder_listdir_cache` (`infrastructure/persistence/path_handler.py`): Caches `os.listdir` results during tier sorting.

**Solution:**
1. **Centralize the Interface:** Define a `CacheProvider` interface in `domain/ports/cache.py` (or `core/ports/cache.py`).
2. **Implement in Infrastructure:** Create an `InMemoryCache` class inside `infrastructure/cache/memory_cache.py` that handles setting, getting, invalidation, and TTL (for cases like `IMAGES_CACHE_TTL`).
3. **Dependency Injection:** Instantiate `InMemoryCache` in the composition roots (`adapters/server/deps.py`, `adapters/cli/deps.py`) and pass it as a dependency down the call stack to `ImageAnalysis`, `VectorList`, and the comparison algorithms.
4. **Remove Globals:** Delete `state.py` and strip all `global` keyword usage across `domain` and `application`.

**Hard Dependency Inversion (DIP) Violations — ML Libraries in Domain:**
The `domain` layer is heavily polluted with direct imports and instantiations of external ML/Data infrastructure libraries (`torch`, `mediapipe`, `sklearn`, `lightgbm`). The domain layer should contain pure business logic and depend on abstractions (ports), not concrete ML frameworks. These must be decoupled:
- **`domain/analysis/mediapipe_analysis.py`**: Instantiates and runs `mediapipe` models directly. Extract into an `infrastructure/ml_models/mediapipe_provider.py` implementing a `MediaPipePort`.
- **`domain/vectors/image_vector.py`**: Imports `torch` and `torchvision`. Tensor manipulation should be pushed to `infrastructure`.
- **`domain/analysis/attribute_analysis.py`**: Imports `torch`. 
- **`domain/data_transformation/data_transformer.py`**: Imports `sklearn` and `lightgbm` directly for feature processing. 
- **`domain/training/plot.py`** and **`domain/training/parameter_analysis.py`**: Depend on `sklearn` directly.

**Solution:** Define interfaces in `domain/ports/ml_providers.py` and move the actual implementations using `torch`, `mediapipe`, and `lightgbm` to the `infrastructure` layer.

**Wiring:** the composition roots (`adapters/server/deps.py`, `adapters/cli/deps.py`) instantiate the new infrastructure providers (`mediapipe_provider.py`, tensor/vector providers, etc.) and thread them through the application layer into the domain constructors. Domain receives ports only; no domain file imports an ML library after this refactor.

### 3.13 Docstring/Description Completion (v6 — Proposed)

**Task:** Ensure every class and function has at least a single-line description explaining what it does. Currently, many classes and methods are missing docstrings.

The following files contain functions or classes missing a description. These must be updated:
- **`adapters/cli/commands/database.py`**: `rebuild`, `recalculate`, `cleanup`
- **`adapters/cli/commands/training.py`**: `load_training_data`, `train_model`, `run_hpo_cycles`, `run_hpo`
- **`adapters/cli/commands/vectors.py`**: `build_split_files`, `build_full_files`, `run_rebuild_scores_only`, `run_split_vectors`, `run_full_vectors`, `run_all`
- **`adapters/cli/main.py`**: `get_cli_parser`, `main`
- **`adapters/comfyui/services.py`**: `get_comfyui_deps`
- **`adapters/server/compressed_image.py`**: `_InMemoryImageCache`, `__init__`, `get`, `put`, `clear`
- **`adapters/server/deps.py`**: `ServerDeps`, `to_cli_deps`, `get_deps`, `build_server_deps`
- **`adapters/server/endpoints/analyze.py`**: `register_analyze_routes`
- **`adapters/server/endpoints/build.py`**: `register_build_routes`
- **`adapters/server/endpoints/database.py`**: `register_database_routes`
- **`adapters/server/endpoints/files.py`**: `register_files_routes`
- **`adapters/server/endpoints/training.py`**: `register_training_routes`
- **`application/hyperparameters/hyperparameter_optimizer.py`**: `run_hpo_cycles`
- **`application/services/graph_service.py`**: `GraphService`, `__init__`, `rebuild_from_database`
- **`application/services/scoring_service.py`**: `__init__`, `_predict_scores`
- **`core/configuration/settings.py`**: `ConfigDict`, `_load_config`, `_normalize_section`, `_ensure_directories`, `_get_project_root`
- **`core/filesystem/__init__.py`**: `find_project_root`
- **`core/observability/logger.py`**: `__init__`, `_format_time`, `_should_log`, `flush`, `debug`, `info`, `warning`, `error`, `exception`, `get_logger`, `capture_log_output`
- **`core/utilities/helpers.py`**: `remove_directory`, `delete_full_vectors`, `remove_models`
- **`domain/analysis/attribute_analysis.py`**: `AttributeAnalyzer`, `__init__`, `analyze`
- **`domain/analysis/image_analysis.py`**: `__init__`, `prepare_image_batch`, `_is_excluded_image`, `_load_mediapipe_models`, `analyze_image_batch`, `_save_entry_sidecar`
- **`domain/analysis/mediapipe_analysis.py`**: `MediaPipeAnalyzer`, `__init__`, `_ensure_models_loaded`, `get_models`, `analyze`, `_process_face_landmarks`, `_process_face_detector`, `_process_pose_landmarks`, `_analyze_faces`, `_analyze_pose`, `_process_object_detector`, `_process_image_classification`
- **`domain/analysis/run_matrix_analysis.py`**: `run_matrix_analysis`
- **`domain/analysis/run_parameter_analysis.py`**: `run_parameter_analysis`
- **`domain/analysis/run_stats.py`**: `run_stats`, `_format_number`
- **`domain/comparison/algorithm/merge_sort_ranker.py`**: `MergeSortRanker`, `__init__`, `_compare`, `_merge`, `_sort_indices`
- **`domain/comparison/algorithm/pair_active.py`**: `get_active_pairs`
- **`domain/comparison/algorithm/phase_order.py`**: `_init_phase_pairs`, `_get_chain_root`, `get_ordered_pairs`
- **`domain/comparison/algorithm/view.py`**: `get_graph_data`
- **`domain/comparison/constants.py`**: `__getattr__`
- **`domain/data_transformation/data_transformer.py`**: `__init__`, `_expand_interaction`, `_create_feature_mapping`, `get_feature_mapping_from_config`, `apply_interaction_features`
- **`domain/database/ports.py`**: `ImagesRepository`, `ComparisonsRepository`, `add_historical_comparison`, `get_image`, `get_all_images`, `get_image_count`, `add_image`, `update_image_rating_state`, `update_image_tags`, `clear_all_images`, `reset_all_image_ratings`, `comparison_exists_for_pair`, `get_all_comparisons`, `get_total_comparisons`, `get_skipped_comparison_count`, `add_comparison`, `clean_comparisons`, `get_images_with_only_wins`, `get_images_with_only_losses`, `clear_all_comparisons`
- **`domain/graph/chain_manager.py`**: `parse_comparison`, `add_directed_edge`, `add_undirected_edge`, `process_one_comparison`, `has_no_predecessors`, `has_no_successors`, `find_top_nodes`, `find_bottom_nodes`, `bfs_one_component`, `index_component`, `build_components`, `same_component`, `find_common_chain_id`, `tarjan_scc`, `ChainManager`, `strongconnect`, `__init__`, `get_all_filenames`, `get_top_nodes`, `get_bottom_nodes`, `get_better_than`, `get_worse_than`, `get_all_edges`, `is_top`, `is_bottom`, `get_component_id`, `get_component_members`, `get_component_count`, `get_built_at`, `set_built_at`, `get_db_comparison_count`, `set_db_comparison_count`, `build`, `_reset_adjacency`, `_build_from_comparisons`, `apply_comparison`, `_remove_from_bottom_if_not_anymore`, `_remove_from_top_if_not_anymore`, `_add_to_bottom_if_needed`, `_add_to_top_if_needed`, `_update_top_bottom_for_edge`, `_component_of`, `_both_have_components_and_different`, `_neither_has_component`, `_winner_lacks_component`, `_loser_lacks_component`, `_create_new_component`, `_add_winner_to_loser_component`, `_add_loser_to_winner_component`, `_merge_node_components`, `_ensure_larger_component_kept`, `_reassign_nodes`, `_absorb_removed_component`, `_merge_components`, `_identify_top_bottom`, `_build_components`, `_dedup_path`, `_build_chains`, `get_chains`, `get_node_chains`, `get_node_main_chain`, `get_min_chain_count`, `_quick_reject`, `_bfs_search`, `_can_reach`, `_check_same_chain`
- **`domain/graph/chain_proxy.py`**: `__init__`, `id`, `nodes`, `length`, `is_main`, `first`, `last`, `get_nodes`, `node_position`, `get_component`, `__repr__`
- **`domain/graph/component_proxy.py`**: `__init__`, `id`, `nodes`, `size`, `get_chains`, `__repr__`
- **`domain/graph/node_proxy.py`**: `__init__`, `id`, `filename`, `score`, `mu_skill`, `sigma_uncertainty`, `trueskill_score`, `comparison_count`, `chain_count`, `main_chain_in_chains`, `prompt_tags`, `last_compared_at`, `is_top`, `is_bottom`, `get_links`, `get_chain`, `get_position_in_chain`, `get_component`, `__repr__`
- **`domain/loading/ports.py`**: `ModelLoader`, `BatchSizer`, `MapsProvider`, `TrainingLoader`, `load_vision_model`, `get_model_info`, `load_embedding_model`, `get`, `get_value`, `add_value`, `get_all_categories`, `register_value`, `load_vectors`, `load_scores`, `load_training_model`, `load_training_model_diagnostics`
- **`domain/training/calibration.py`**: `_as_1d_float_array`, `_strictly_increasing`, `extract_score_calibration`, `apply_score_calibration`
- **`domain/training/grid.py`**: `around`
- **`domain/training/matrix_analysis.py`**: `MatrixAnalyzer`, `__init__`, `get_text_weight`, `_extract_all_params_from_record`, `_add_param_from_value`, `build_matrix`, `calculate_statistics`, `export_to_json`, `print_top_correlations`, `get_matrix_size`, `get_matrix_summary`
- **`domain/training/parameter_analysis.py`**: `ParameterAnalyzer`, `main`, `__init__`, `analyze_all`, `analyze_parameter_pairs`, `analyze_term_correlations`, `_create_scatter`, `_create_2d_scatter`, `_get_category_scores`, `_save_category_stats`, `generate_report`
- **`domain/training/plot.py`**: `_get_metric_direction`, `_prepare_finite_data`, `_calculate_scatter_sizes`, `_setup_scatter_axes`, `plot_scatter_comparison`, `plot_scatter_comparison_continuous`, `prepare_plot_data`, `print_comparison_metrics`, `compare_model_vs_data`, `_plot_metric_on_axes`, `plot_metric`, `plot_loss_curve`, `plot_score_distribution`, `plot_continuous_analysis`, `plot_discrete_analysis`, `plot_aggregate_summary`, `plot_individual_metrics`, `plot_discrete_object_analysis`, `prepare_face_data`, `plot_face_bbox`, `plot_positional_data`, `plot_positional_bbox`, `plot_detection_presence`, `__init__`, `__call__`, `plot_final_results`
- **`domain/vectors/embedding_vector.py`**: `EmbeddingVector`, `__init__`, `parse_value_list`, `create_vector_batch`, `create_vector_list`, `create_text_batch`, `create_text_list`
- **`domain/vectors/helpers.py`**: `l2_normalize_batch`, `get_value_from_entry`
- **`domain/vectors/image_vector.py`**: `scaled_batch_size`, `probe_bound_for_failed`, `ImageVector`, `__init__`, `array_to_pil`, `get_batch_size`, `create_vector_list`
- **`domain/vectors/keypoint_vector.py`**: `__init__`, `_config_index`, `_grow`, `parse_value_list`, `create_vector_list`
- **`domain/vectors/map_vector.py`**: `__init__`, `_config_index`, `_maybe_grow`, `_normalize`, `parse_value_list`, `create_vector_list`
- **`domain/vectors/number_vector.py`**: `IntVector`, `FloatVector`, `__init__`, `parse_value_list`, `create_vector_list`, `__init__`, `parse_value_list`, `create_vector_list`
- **`domain/vectors/person_map_vector.py`**: `__init__`, `_config_index`, `_per_unit`, `_grow`, `parse_value_list`, `create_vector_list`
- **`domain/vectors/position_vector.py`**: `__init__`, `_config_index`, `_grow`, `parse_value_list`, `create_vector_list`
- **`domain/vectors/terms.py`**: `ExtractionResult`
- **`infrastructure/external_services/mediapipe_models.py`**: `download_mediapipe_models`, `_download_to`
- **`infrastructure/loading/maps_loader.py`**: `MapsLoader`, `__init__`, `get_all_categories`, `_save_single_map`, `_load_single_map`, `load_maps`
- **`infrastructure/loading/training_loader.py`**: `TrainingLoader`, `__init__`, `_reset_models`, `remove_training_models`, `load_vectors_array`, `_load_vectors_from_jsonl`, `_load_vectors_from_npz`, `_save_vectors_to_npz`, `load_scores_array`, `_load_scores_from_jsonl`, `_load_scores_from_npz`, `_save_scores_to_npz`, `_load_comparisons_from_npz`, `_save_comparisons_to_npz`, `load_feature_rule`, `save_feature_rule`, `save_comparison_rule`, `load_interaction_data`, `save_interaction_data`, `_normalize`, `load_training_model_diagnostics`, `load_training_model`
- **`infrastructure/ml_models/batch_sizer.py`**: `HistoryEntry`, `ProfileData`, `BatchSizer`, `__init__`, `_ensure_session_profiled`, `_resolution_key`, `get`, `_profile_new_resolution`, `_evaluate_candidate`, `_fit_model`, `_save_cache`
- **`infrastructure/ml_models/model_loader.py`**: `_missing_model_error`, `_face_attributes_checkpoint_path`, `MultiTaskClipVisionModel`, `ModelLoader`, `verify_models_present`, `download_configured_models`, `__init__`, `forward`, `__init__`, `_select_transform`, `load_vision_model`, `get_model_info`, `load_embedding_model`, `load_hf_vision_model`, `_load_hf_vision_model_impl`
- **`infrastructure/ml_models/training/model_trainer.py`**: `ModelTrainer`, `__init__`, `create_training_model`, `create_callbacks`, `create_metrics`, `train_model_pairs`, `train_model`, `pbar_callback`
- **`infrastructure/ml_models/training/pair_data.py`**: `load_comparison_records`, `build_pairwise_dataset`
- **`infrastructure/persistence/cleanup_orphans.py`**: `_walk_all_files`, `_scored_root_files`, `cleanup_orphans`, `main`
- **`infrastructure/persistence/comparisons_repository.py`**: `_canonicalize_pair`, `_safe_parse_timestamp`, `comparison_exists_for_pair`, `clear_all_comparisons`, `get_total_comparisons`, `get_skipped_comparison_count`, `get_all_comparisons`, `get_images_with_only_wins`, `get_images_with_only_losses`, `add_comparison`, `add_historical_comparison`, `clean_comparisons`
- **`infrastructure/persistence/database.py`**: `_ensure_meta_table`, `_ensure_images_table`, `_ensure_comparisons_table`, `_check_proxy_entry`, `_set_meta_value`, `vacuum_database`
- **`infrastructure/persistence/deduplicate_scored.py`**: `_md5`, `_merge_comparison_histories`, `deduplicate_scored`, `main`, `_scan_worker`
- **`infrastructure/persistence/images_repository.py`**: `get_all_images`, `get_image`, `add_image`, `update_image_rating_state`, `update_image_tags`, `get_image_count`, `clear_all_images`, `reset_all_image_ratings`
- **`infrastructure/persistence/path_handler.py`**: `clear_folder_cache`, `get_ranked_root`, `compute_path_from_filename`, `find_image_path`, `_build_history_for_filename`, `_move_image_and_json`

### 3.14 Engineering Reliability Improvements (v6 — Proposed)

**1. Comprehensive Test Coverage**
- **What**: Create matching test files mirroring the `core`, `domain`, `application`, and `infrastructure` directories inside `tests/`.
- **Where**: A new, fully populated `tests/` directory structure.
- **Why**: The current test suite has only 4 files and 34 tests, leaving the vast majority of ML inference, domain logic, and graph algorithms completely untested. High coverage ensures structural refactoring doesn't break behavior. (Permitted as of the 2026-08-22 rule 5 amendment.)

**2. Strict Type Safety**
- **What**: Eliminate all 2,731 Pyright strict errors. Use precise types, `typing.Protocol` for dependency injection interfaces, and strictly define generic types (e.g. `list[str]`, `dict[str, Any]`).
- **Where**: Across all Python files in the module. Missing type stubs may need to be added to `typings/` for external, untyped ML libraries like `mediapipe` or `sentence_transformers`.
- **Why**: Reduces runtime `TypeError` and `AttributeError` exceptions, and strictly enforces the contracts between `ports` and `adapters` defined by the Clean Architecture.

**3. Concurrency & Memory Management**
- **What**: Refactor multi-threading logic to respect ML hardware boundaries. Replace unbounded or standard `ThreadPoolExecutor` logic with a robust async queue or explicitly chunked, sequential batch processing that yields to the GIL and GPU memory limits.
- **Where**: `application/services/image_processor.py` (which orchestrates batches) and `domain/analysis/image_analysis.py` (which executes them).
- **Why**: ML operations (`torch`, `mediapipe`) are inherently memory-intensive. Running them across many standard Python threads risks catastrophic Out-Of-Memory (OOM) crashes and CPU bottlenecking due to the Python Global Interpreter Lock (GIL).

**4. Strict Input Data Validation**
- **What**: Implement strict payload validation using `Pydantic` schemas for all incoming HTTP requests.
- **Where**: All API endpoint files inside `adapters/server/endpoints/` (e.g. `build.py`, `training.py`, `files.py`).
- **Why**: Currently, endpoints pass `request.get_json()` directly into domain services. Malformed inputs, missing keys, or invalid types will bypass the adapter layer and cause fatal, unhandled `TypeError` or `KeyError` crashes deep within the business logic.

**5. Configuration Schema Validation**
- **What**: Replace the unstructured `AutoSaveDict` JSON wrapper with strongly typed configuration models (e.g., using `pydantic-settings` or `dataclasses`).
- **Where**: `core/configuration/settings.py`.
- **Why**: The current configuration loader blindly parses `config.json` without verifying if required keys, paths, or thresholds exist. Missing configurations currently cause runtime exceptions only when that specific logic path is triggered, rather than failing safely at startup.

**Dependency note (2026-08-22):** adding `pydantic` (+ `pydantic-settings` if used) is user-approved as necessary per the AGENTS.md necessity clause; add to `pyproject.toml` and regenerate `requirements.txt` via `uv pip compile pyproject.toml -o requirements.txt` when implementing.

**Flagged observation (no edit scheduled):** `model_loader.py:5–10` syncs `_hub_constants.HF_HUB_OFFLINE` at import time only — flipping `os.environ` at request time may not enable hub downloads. Verify during implementation of §3.7 #27; surface back before touching `model_loader.py`.
