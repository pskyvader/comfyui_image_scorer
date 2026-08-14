# Reorganization Plan — `comfyui_image_scorer` (v4)

**Status (2026-08):** v2 is complete (verified against the live tree: 28
adapter-wiring statements in the three composition roots, pytest 30 passed,
ruff ARG/F401 clean, pyright 701-error baseline with zero new, node smoke OK).
v3 (CLI-parity remediation) is superseded by this revision, which extends it:
**strict CLI parity, a full rename cascade to CLI command names, and the
complete removal of the server task system.** The CLI
(`adapters/cli/`) is the source of truth and is **not modified**.

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
2. Relative imports at module scope.
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
3. **All command endpoints become synchronous:** run the work in the request,
   capture logs, and return `{"status": "done", "result": ..., "log": ...}`
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

12. **Add `POST /api/training/train`** replicating CLI `train-model`:
    synchronous; loads training data via `deps.training_loader`/
    `deps.model_trainer`, trains `config["training"]["top1"]`, saves model +
    plots. Result: metrics + plot paths.
13. **`/hpo` honors request params** — accept `cycles`, `optimization_steps`,
    `max_combos` from the body (absent/`None` → config defaults).
14. **Remove `POST /api/training/reset`** and **`GET/POST
    /api/training/config`** — no CLI counterpart.
15. **Frontend:** remove the "Optimize Hyperparameters" (`optimize-hpo`),
    "View Config" (`get-training-config`), and "Reset Training objects"
    (`reset-config`) buttons/actions. Keep `train-top` → `/training/train`
    and `hpo-cycle` → `/training/hpo`.

### 3.5 `build` — `endpoints/build.py` + `adapters/build/frontend/`

16. **Add `split_vectors` mode** to `POST /api/build/prepare`: replicating
    `build split-vectors` — `build_split_files` with the `batch` loop and the
    `remove_derived_caches` side effect (both currently missing).
17. **Add `full_vectors` mode** replicating `build full-vectors`.
18. **Default branch = `build all`** (split + full + scores), honoring `batch`.
19. **Delete the `rebuild_missing_vectors` and `text_only` branches** — they
    call `run_rebuild_missing_vectors()` / `run_text_only()`, which do not
    exist in `application/data_transform/prepare_data.py` and have no CLI
    counterpart. Drop the unused `test_run` flag.
20. **Remove `POST /api/build/scan-import`** — no CLI counterpart.
21. **Frontend:** remove the "Rebuild Missing" and "Text-Only"
    buttons/actions.
22. **Note — `POST /api/build/delete-vectors` (`files remove vectors`):**
    verified 2026-08 — it calls `delete_full_vectors()`
    (`core/utilities/helpers.py`), which unlinks **only** `vectors_file`,
    `scores_file`, `index_file`, `text_data_file`, `comparisons_file` and
    **never touches the `split/` directory** ("keep the split/ directory
    intact"). Keep the endpoint exactly as-is behaviorally; keep the
    frontend confirmation dialog. (Both CLI and endpoint share this helper —
    parity by construction.)

### 3.6 `database` — `endpoints/database.py` + `adapters/database/frontend/`

23. **Add `POST /api/database/recalculate`** replicating CLI `database
    recalculate`: `reset_all_image_ratings(default_score)` →
    `replay_ratings(all_comparisons)` → update each image's
    score/rating/count.
24. **Add `POST /api/database/cleanup`** replicating CLI `database cleanup`
    (clean comparisons + vacuum) — resolves the `cleanup-orphans` name
    collision. Requires adding `vacuum_database` to `ServerDeps`.
25. **`/deduplicate` root alignment:** CLI passes `root=None`, endpoint
    passes `root=Path(image_root_processed)` — verify `deduplicate_scored`
    treats them identically; align if not.
26. **Remove `GET /api/database/status`**, **`POST /api/database/sync-all`**,
    **`POST /api/database/normalize-comparisons`** — no CLI counterpart.
27. **Frontend:** remove "Sync All → JSON" (`sync-all`) and "Normalize
    Comparisons" (`normalize-comparisons`) buttons/actions; remove dead
    actions `reset-ratings`, `cleanup-orphans-dry`, `deduplicate-dry`.

### 3.7 `files` — new `adapters/server/endpoints/files.py`

28. **Create `endpoints/files.py`** (`files_bp`, `/api/files`) with
    synchronous routes: `POST /remove-maps` → `remove_directory(maps_dir)`;
    `POST /remove-downloaded-models` →
    `remove_directory(mediapipe_models_dir)`; `POST /download-models` →
    `download_configured_models()` + `download_mediapipe_models()`
    (**user-initiated only** — button click; no background downloads).
29. **Wire in `adapters/server/deps.py`:** add `vacuum_database`,
    `download_configured_models`, `download_mediapipe_models`, and the
    maps/mediapipe directory removers to `ServerDeps`. **No infrastructure
    imports in the endpoint file.**
30. **Register** `register_files_routes(app, deps)` in `adapters/server/main.py`.
31. **Frontend (database view):** add "Remove Maps", "Remove Downloaded
    Models", "Download Models" buttons/actions; render the returned log.

### 3.8 `analyze` — `endpoints/analyze.py` + `adapters/analyze/frontend/`

32. **Remove `GET /api/analyze/report-file`** — no CLI counterpart (frontend
    never calls it). The three command routes (`/stats`,
    `/analyze-parameters`, `/analyze-matrix`) already match the CLI.

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
(try/except 55→56→51, inline imports 35→35→25, defaults 131→134→115);
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
39. **Module-scope imports — 25 inline imports** outside the established CLI
    lazy pattern (`adapters/cli/`, `scorer.py`). The lazy heavy-dep imports
    in `plot.py` (3) and `application/analysis/run_*_analysis.py` (2) match
    the CLI justification and may stay. Move everything else to module scope:
    `domain/graph/` proxy modules (9 — break the import cycle),
    `domain/comparison/algorithm/view.py` 2, `domain/data_transformation/
    data_transformer.py` 1, `infrastructure/persistence/deduplicate_scored.py`
    1, `core/observability/logger.py` 1, server endpoints
    (`comparison.py` 1, `data_transform.py` 1, `training.py` 2, `main.py` 1,
    `adapters/comfyui/services.py` 1).
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
   `/api/database/recalculate`, `/api/database/cleanup`, `/api/files/*`,
   `/api/build/prepare` (split/full modes), `/api/training/hpo` body params;
   removed routes 404 — `/api/training/reset`, `/api/training/config`,
   `/api/build/scan-import`, `/api/database/status`, `/api/database/sync-all`,
   `/api/database/normalize-comparisons`, `/api/analyze/report-file`, and
   every `/task/<task_id>` route.
4. Frontend smoke: every section loads (`build`, `analyze`, `database`,
   `training`, `compare`, `gallery`, `chains`), no 404 on static assets, no
   TaskPoller references remain.

---

## 5. Explicitly Out of Scope

- CLI changes (`adapters/cli/`) — source of truth, not modified (including
  the unused `--steps` on `train-model` and unused `--limit` on
  `database cleanup`).
- `comparison.py`, `gallery.py`, `maps.py` blueprints and their frontends.
- The `maps` (v1) frontend folder — dead but harmless.
- `core`/`domain`/`application`/`infrastructure` behavior (the logger helper
  in §3.2 #5 is the only non-`adapters` change, and it is additive).
- New ComfyUI nodes, new features, new dependencies, new test files.
- Node names and workflow compatibility.
