# Reorganization Plan — `comfyui_image_scorer` (v7)

**Status (2026-08-29):** v4/v5 complete (§3.1–§3.10); §3.11 v5 remainder
complete; v6 Phase A **complete** (#47/#49/#50/#51/#53/#54 done, #48/#52
partial → remaining items tracked in Phase B); v6 Phase B (docstrings) in
progress; v6 Phase C (reliability) #56/#58 complete, #57 in progress; v6
Phase D (tests) started; **v7 Phase E (CrystalGraph Proxy Facade Migration) planned — tasks #60–#71**. This document supersedes all previous revisions.
Stable external references: `§0` rules, `§1` source of truth, `§1.1` parity
contract, `§3.10 #37` taxonomy, `§4` verification, `§5` out of scope.

Verified gates (2026-08-27): pytest 45 passed (+2 realdata deselected by
default); ruff ARG/F401 **0**; pyright strict **455** baseline (zero new
errors per change); layer scan 0; DB-proxy scan blocking with 0 violations;
route map unchanged; `AestheticScore` registers.

**Decision log (user-authorized):**

| Date | Decision |
|---|---|
| 2026-08-17 | Execute full v4 including §3.10 audit |
| 2026-08-18 | v5 scope: renamed `files` commands + matching endpoints/frontend |
| 2026-08-22 | v5.1 refinements: comparison/gallery/maps scope; proxy choke point; HF_HUB_OFFLINE restore; rule 5 new tests; #37 taxonomy; pydantic approved; deps hoisted; general suite explicit-run-only |
| 2026-08-23 | pair_active carve-out lifted; download-models try/finally + deps-injected offline toggle; proxy entry enforced via runtime + static AST scan (narrow whitelist); AutoSaveDict spike; maps3 reuses `/api/maps/graph-data`; pyright recounted at kickoff; ThreadPoolExecutor refactor removed to reactive (§6); comprehensive tests last (§3.15); rule 14 (temp dirs) |
| 2026-08-24 | #47 executed as the full proxy migration (user-selected over mechanical flip); destructive `realdata` tests blocked by default (`addopts -m 'not realdata'`; opt back in with `pytest -m realdata`) |
| 2026-08-24 | #58 spike decided: option B (read-only validated config + explicit save API); implementation pending |
| 2026-08-24 | #49/#50/#54 executed as one batch; #53 deleted all of `typings/` — fresh pyright strict baseline 455 |
| 2026-08-29 | Documentation-only v7 decisions: `cache.db` is the sole database name; database reset/rebuild is manual; all database access terminates at `CrystalGraph`; filesystem operations use a domain port with an infrastructure implementation; no optional values or default arguments |

---

## 0. Ground Rules (from README + module AGENTS.md, abbreviated)

1. Every command runs in the ComfyUI venv
   (`& "E:\ComfyUI\.venv\Scripts\Activate.ps1"` first).
2. Relative imports at module scope, at the top of each file. No inline
   imports anywhere in the module except `adapters/cli/main.py` (lazy parser
   dispatch). Top-of-file conditional guards (`folder_paths` availability,
   `TYPE_CHECKING` cycle-breakers) are not inline imports.
3. pyright strict must pass (`pyrightconfig.json`). Until §3.14 #57 lands,
   the documented 455-error baseline applies: zero *new* errors per change.
4. No error-swallowing `try`/`except`. Permitted forms only — see §3.10 #37
   (normative taxonomy): finally-only cleanup, translate-and-reraise,
   OOM-adaptive batching.
5. New test files are permitted. Existing tests must keep passing.
6. No global mutable state in `core`/`domain`/`application`.
7. Nothing imports `infrastructure` except the three composition roots
   (`adapters/server/main.py`, `adapters/cli/deps.py`,
   `adapters/comfyui/services.py`). Endpoints receive everything through
   `ServerDeps`.
8. No defaults: configuration objects and function arguments have no default
   values. Optional values are not part of this design. Every required value
   is supplied explicitly at every call site; omitted values are not represented
   with `None` or defaulted parameters.
9. No internet requests unless explicitly user-initiated: the only download
   path is `files download models` and its matching server button.
10. Compatibility rule is suspended where it conflicts with user decisions
    (section URLs, blueprint prefixes, frontend folders follow CLI command
    names). Node names and workflow behavior remain untouched.
11. No new dependencies — exception: `pydantic` (+ `pydantic-settings` if the
    §3.14 #58 spike selects it), user-approved.
12. Small, direct changes; narrowest code path per fix.
13. Command endpoints call the CLI command functions directly; endpoint body =
    validate → one call → response wrapping. Endpoints may import
    `adapters/cli/commands/*` (same layer).
14. Tests and stubs touch temp directories only (`tmp_path`) — never real
    `output/`, ranked roots, or `config/`.
15. `CrystalGraph` is the only application-facing database boundary. Callers
    use graph terminology and graph methods (`nodes`, `links`, and proxies),
    never repositories or database rows directly.
16. The sole supported database filename is `cache.db`. Deleting, backing up,
    renaming, or rebuilding it is a manual operator action. No task, startup
    path, test, or command may delete or rebuild it automatically.

---

## 1. Source of Truth — CLI command table

| Section | Command | Behavior |
|---|---|---|
| `server` | `server` | runs this Flask server |
| `training` | `train-model` | load data → train top1 → save model + plots |
| `training` | `hpo` | `HpoRunner.run` with all cycle options supplied explicitly |
| `build` | `split-vectors` | `build_split_files` loop + `remove_derived_caches` |
| `build` | `full-vectors` | `build_full_files` from existing splits |
| `build` | `scores` | `run_rebuild_scores_only(graph)` |
| `build` | `all` | split → full → scores |
| `database` | `cleanup` | graph `clean_comparisons()` + `vacuum_database()` |
| `database` | `rebuild` | `processor.rebuild_database_from_ranked()` |
| `database` | `recalculate` | reset ratings → replay → update images (via graph facade) |
| `files` | `remove vectors` | `delete_full_vectors()` — full files + all splits except `split/image/` |
| `files` | `remove generated-models` | `remove_models()` |
| `files` | `remove vector-maps` | remove maps dir + `split/map` |
| `files` | `remove downloaded-models` | remove mediapipe dir |
| `files` | `download models` | offline toggle around both downloads (user-initiated) |
| `files` | `cleanup` | `deduplicate_scored(root, limit)` + `cleanup_orphans(root)` with explicit roots |
| `analyze` | `parameters` | `run_parameter_analysis()` |
| `analyze` | `matrix` | `run_matrix_analysis()` |
| `analyze` | `stats` | `run_stats(graph)` |

## 1.1 Endpoint → CLI function parity contract

Every command endpoint body = one call to its CLI command function, wrapped
in the response shape. Key rows:

| Endpoint | Function called |
|---|---|
| `POST /api/training/train` | `train_model(deps)` |
| `POST /api/training/hpo` | `deps.hpo_runner.run(...)` |
| `POST /api/build/prepare` | `run_split_vectors / run_full_vectors / run_all` by mode |
| `POST /api/build/delete-vectors` | `delete_full_vectors()` |
| `POST /api/database/*` | `rebuild/recalculate/cleanup(deps)` |
| `POST /api/files/remove-*` | matching `remove_*` helpers |
| `POST /api/files/download-models` | `set_hub_offline(False)` → try both downloads → finally restore |
| `POST /api/files/cleanup` | dedup + orphan cleanup |
| `GET /api/analyze/stats` | `run_stats(graph=deps.graph)` |
| `POST /api/analyze/analyze-*` | matrix/parameter runners |

Mechanics: same-layer imports of `adapters/cli/commands/*`; `ServerDeps`
superset of `CLIDeps` via `to_cli_deps()` (fields include graph, processor,
cache, hpo_runner, plot_manager, mediapipe, vacuum/download/set_hub_offline);
response `{"status": "done", "result", "log"}` via `capture_log_output()`;
matplotlib Agg at startup.

## 2. Section → endpoint/blueprint map

| CLI section | Endpoint file | Prefix | Frontend folder |
|---|---|---|---|
| `training` | `endpoints/training.py` | `/api/training` | `adapters/training/frontend/` |
| `build` | `endpoints/build.py` | `/api/build` | `adapters/build/frontend/` |
| `database` | `endpoints/database.py` | `/api/database` | `adapters/database/frontend/` |
| `files` | `endpoints/files.py` | `/api/files` | buttons in database/build views |
| `analyze` | `endpoints/analyze.py` | `/api/analyze` | `adapters/analyze/frontend/` |

Non-command blueprints keep their routes: `comparison.py`, `gallery.py`,
`maps.py` with frontends `adapters/comparison/`, `adapters/gallery/`,
`adapters/maps/`, `adapters/maps2/`, `adapters/maps3/` (maps3 shares the maps
data pipeline).

---

## 3. Tasks

### 3.1–3.11 — COMPLETE (2026-08-17/18/23)

§3.1–3.10 (v4/v5): task system deleted; synchronous endpoints; rename cascade;
rules audit; `endpoints/files.py`.

§3.11 (v5 remainder): #42 proxy entry enforcement; #43 download-models offline;
#44 delete-vectors confirmation; #45 prediction accuracy; #46 maps3 visualization.

### 3.12 v6 Phase A — Structural corrections — **COMPLETE (6/8 tasks)**

| Task | Description | Status |
|---|---|---|
| 47 | Route DB access through graph proxies | ✅ 2026-08-24 |
| 49 | Remove global mutable state (`state.py` deleted) | ✅ 2026-08-24 |
| 50 | Unified cache architecture | ✅ 2026-08-24 |
| 51 | Semantic misplacements | ✅ 2026-08-24 |
| 53 | typings/ cleanup | ✅ 2026-08-24 |
| 54 | pair_active.py ARG001 resolved | ✅ 2026-08-24 |

**Remaining from Phase A (carried forward):**

48. **PARTIAL.** MediaPipe model-path construction moved into
    `infrastructure/ml_models/mediapipe_provider.py` behind `MediaPipePort`.
    Remaining: inject infrastructure sidecar writer for
    `domain/analysis/image_analysis.py`; `_load_map_slots` reads map JSON
    directly (semantically equal to MapsProvider.get_all_categories); split-file
    path joins remain in vector_list/prepare_data; deep path and shutil work
    remains in image_processor (partially behind PathOps).

52. **PARTIAL.** `domain/ports/ml_providers.py` created with MediaPipePort; all
    mediapipe usage in `infrastructure/ml_models/mediapipe_provider.py`; domain
    MediaPipeAnalyzer is a thin delegate threaded from roots through
    CLIDeps/ServerDeps → build_split_files/ScoringService → ImageAnalysis.
    Remaining ML imports in domain: image_vector.py (torch/torchvision),
    attribute_analysis.py (torch softmax/no_grad around loader-provided HF
    models), data_transformer.py (lightgbm/sklearn). Design: add vision-encoding
    provider (tensor prep + #37c OOM loop) and feature-engine provider (LGBM
    ranking + poly interactions), threaded through dep containers like MediaPipePort.

Execution note: sub-batches with the full §4 gate run after each batch.

### 3.13 v6 Phase B — Docstring completion

55. **IN PROGRESS (2026-08-24):** AST audit identified 781 missing docstrings
    (80 module/class + 701 function). Done: all 4 new endpoint request models,
    CLIDeps, ServerDeps, AestheticScoreNode (+its package/module), and 11
    module-level docstrings (CLI commands database/server/training/vectors,
    cli/main, node_registry, application services x3, hyperparameter_optimizer).
    Remaining ~750 function-level docstrings are a dedicated mechanical pass. pass; pair_active.py included.

### 3.14 v6 Phase C — Engineering reliability

56. ✅ **COMPLETE (2026-08-24).** pydantic added to pyproject.toml;
    requirements.txt regenerated (`pydantic==2.13.4`). Request models added at
    the adapter boundary: `FilesCleanupRequest`, `HpoRequest` (fields
    required integer cycle options supplied explicitly at the call site),
    `PrepareRequest` (mode pattern replaces the manual whitelist),
    `SkipRequest`, `SubmitComparisonRequest`. All routes tolerate absent JSON
    bodies via `get_json(silent=True) or {}` where the original did. The old
    inline `ComparisonRecorder` import became a module-scope import (rule 2);
    the same-image and winner-in-pair checks were restored as route-level
    semantic validations. A global Flask `ValidationError` handler in
    server/main.py maps invalid payloads to 400 with details.
57. **IN PROGRESS (baseline work done).** Pyright strict: recounted 584 at
    kickoff, then reduced to **455** by the #53 typings deletion — that is
    the standing documented baseline for "zero new". Full elimination remains.
    A later run reported 466, but that count is treated as historical drift;
    #57 must replace it with one clean-checkout baseline and exact command
    documentation before the number changes.
58. ✅ **COMPLETE (2026-08-24).** Option B implemented fully: `settings.py`
    rewritten — frozen pydantic section models (`PrepareSection`,
    `RankingSection`, `TrainingSection`, `VectorSection`) validating scalar
    leaves at first access; unknown/nested keys ride as typed extras so
    legacy JSON keeps loading. `AutoSaveDict` deleted. Reads unchanged at
    call sites via `__getitem__`/`__contains__` shims on the model base.
    Writes reduced to exactly two APIs: `Config.set_root` (image_root
    bootstrap in both composition roots) and `Config.save_section`
    (vector slot growth in the four domain vector classes; HPO results in
    `_save_state` via `Config.section_data`). Malformed config JSON now
    fails fast (`RuntimeError`) instead of silently loading `{}`.
    Discovered during inventory: the vector slot-growth writers existed in
    four domain files beyond the two writers named in the spike — all now
    flow through the single save API. settings.py itself: zero pyright
    strict errors.lidated read-only
    config + explicit save path. Recommendation recorded in the spike
    (option B with a narrow training-results updater). Decision recorded 2026-08-24: **Option B** - load-time-validated
    read-only sections + explicit save API (training-results updater).
    Implementation is the remaining work of this task.

### 3.15 v6 Phase D — Comprehensive tests (LAST)

59. **STARTED (2026-08-24).** `tests/test_architecture.py` authored from the
    §4 scan definitions (layer gate + blocking DB-proxy gate), both green.
    Remaining: colocated coverage expansion below (ML inference seams,
    domain logic, graph algorithms, loader round-trips, command↔endpoint
    contract). General suite runs only on explicit user prompt.

---

## 4. Verification

Run after every change, in order:

1. pytest — colocated suites for the module under change; general suite only
   on explicit prompt (realdata additionally blocked by default).
2. ruff — `ruff check --select ARG,F401 --target-version py313 --exclude
   comfyui_image_scorer_old --exclude typings .` — currently zero findings.
3. pyright strict — zero new errors vs the documented 455 baseline until #57
   completes.
4. AST layer scan — README dependency table; now also enforced permanently
   by `tests/test_architecture.py::test_no_layer_violations`.
5. AST DB-proxy scan — blocking since the #47 flip; enforced by
   `tests/test_architecture.py::test_no_db_access_outside_proxies`.
6. Route-map parity — boot the Flask app; URL rules must equal §1.1 command
   endpoints + §2 non-command blueprints + static/asset/error routes; no
   /task routes.
7. Node registration smoke — NODE_CLASS_MAPPINGS exposes AestheticScore.

---

## 5. Explicitly Out of Scope

- CLI behavior changes beyond what tasks specify (source of truth).
- Anything not listed in §3.11–§3.15: no new nodes/features/dependencies
  beyond rule 11's exception.
- Node names and workflow compatibility.
- comfyui_image_scorer_old/ is read-only reference material.

---

## 6. Reactive / deferred ideas (not scheduled)

- Sequential/chunked processing instead of ThreadPoolExecutor
  (image_processor/image_analysis): revisit only upon observed OOM or
  concurrency error, benchmark-gated, reverting if slower.

---

## 7. Next-session handoff (2026-08-27, agreed with user)

Remaining order (user-selected "structure first"): **#57 → #48/#52 → #55 bulk → #59 → #60–#71 (Phase E)**.

Standing decisions from the 2026-08-24 review:
- #55 scope: docstrings on **everything public + private** (~780 items); tests skipped.
- The general suite (`tests/test_general.py`) runs **only after every task
  including #59 is complete** — explicit user authorization condition.
- #57 first step: recount pyright strict against a clean checkout
  (`git stash` → full run → restore) to resolve the 455-vs-466 baseline
  drift, then fix per-file. Fresh minimal stubs for `mediapipe` +
  `sentence_transformers` are pre-sanctioned (see #53 note).
- #48/#52 design: add a vision-encoding port (owning tensor prep + the
  #37c OOM loop) and a feature-engine port (LGBM ranking + poly
  interactions), threaded through both dep containers like MediaPipePort.
- Working tree was left green: 36 colocated tests, ruff 0, layer/DB-proxy
  scans 0, routes unchanged, node registers. Nothing committed.

**Phase E execution order (user-confirmed):**
1. **#60** — Remove `transitive_depth` and `weight` completely (execute first)
2. **#61 + #62** — `LinkProxy` + `ChainManager` history (parallel)
3. **#63** — filesystem port and infrastructure `FileManager`
4. **#64 + #65** — CrystalGraph read/write API migration
5. **#66** — `FileManager` integration
6. **#67–#70** — Caller updates per layer (endpoints → services → domain → CLI)
7. **#71** — Tests & verification

---

### 3.16 v7 Phase E — CrystalGraph Proxy Facade Migration

This phase transforms `CrystalGraph` into the single authoritative graph and
database facade:
- **Reads** → Internal graph structures and graph-owned history after an explicit load
- **Writes** → Graph state and persistence remain synchronized with a defined failure contract
- **Returns** → Proxy objects for graph entities (`NodeProxy`, `LinkProxy`, `ChainProxy`, `ComponentProxy`)
- **File control** → Delegated through a domain filesystem port to infrastructure `FileManager`
- **Encapsulation** → Proxy construction is internal to the graph subsystem; callers receive proxies from `CrystalGraph`
- **Naming** → Consistent graph API (`get_all_nodes`, `get_all_links`, `get_node`, `add_link`, etc.)
- **Database boundary** → Only `CrystalGraph` and its injected ports access repositories; all other callers use graph methods

| Task | Description | Status |
|------|-------------|--------|
| 60 | **Remove `transitive_depth` and `weight` completely** — Delete both names from configuration, SQLite schema and SQL, repository ports and implementations, graph APIs, domain algorithms, metadata serialization, image replay, test fakes, and every active call site. Do not migrate or reinterpret old values. The sole supported database is `cache.db`; any backup, deletion, renaming, or rebuild is performed manually by the operator before or after this work. No code, startup path, test, or command may delete or rebuild the database automatically. **Structural note:** Each layer removes only the contract it owns; no layer may bypass `CrystalGraph` to access persistence. | ⏳ |
| 61 | **Add `LinkProxy` and define internal proxy ownership** — Create `domain/graph/link_proxy.py` with `LinkProxy` wrapping internal `_ComparisonRecord(id, winner, loser, timestamp)`. Keep proxy construction internal to the graph subsystem. Callers receive proxies from `CrystalGraph`; proxy navigation may use a private graph-owned factory, but adapters, services, algorithms, and tests do not construct proxies directly. Export the public proxy types from `domain/graph/__init__.py`. Add tests for navigation and construction boundaries. | ⏳ |
| 62 | **Extend `ChainManager` with comparison history** — Add graph-owned comparison history populated by `build()` and updated by `apply_comparison()`. `build()` replaces history rather than appending; clear operations remove it; repeated rebuilds do not duplicate entries; IDs and timestamps survive repository loading. Define the write failure behavior so in-memory history cannot silently diverge from persisted links. | ⏳ |
| 63 | **Create the filesystem port** — Add a narrow `domain/files/ports.py` protocol containing only the file operations required by `CrystalGraph`. Do not put filesystem implementations, directory scans, JSON persistence, config globals, or cache state in `domain/`. Keep the concrete `FileManager` in `infrastructure/persistence/` or `infrastructure/files/`. Its constructor receives explicit required paths and configuration values from the composition root. | ⏳ |
| 64 | **Migrate CrystalGraph read methods** — Implement the proxy-centric API: `get_all_nodes()` → `list[NodeProxy]`, `get_node(filename)` → `NodeProxy|None`, `get_node_count()` → `int`, `get_all_links()` → `list[LinkProxy]`, `get_link_count()` → `int`, `get_winner_only_nodes()` → `list[NodeProxy]`, `get_loser_only_nodes()` → `list[NodeProxy]`, `link_exists_between(a,b)` → `bool`, `get_all_chains()` → `list[ChainProxy]`, and `get_all_components()` → `list[ComponentProxy]`. Use an explicit loaded/unloaded state; never trigger loading merely because the graph has zero nodes. Define whether stale persistence is rebuilt and keep that behavior separate from the valid empty-graph state. | ⏳ |
| 65 | **Migrate CrystalGraph write methods** — Implement node/link writes with no default arguments and no optional sentinel values. Define persistence ordering and failure behavior before changing code. History, graph structures, and repository state must remain consistent after successful writes, clear operations, cleanup, and repository failures. `CrystalGraph` accesses repositories only through injected domain ports; callers do not. | ⏳ |
| 66 | **Integrate the filesystem port into `CrystalGraph`** — Inject the domain filesystem port into `CrystalGraph` and delegate file methods through that port. Construct the concrete infrastructure `FileManager` only in composition roots. Update `ImageProcessor` and other callers to use graph file methods where graph ownership is intended. Remove `PathOps` only after all callers have migrated and no direct filesystem boundary is lost. | ⏳ |
| 67 | **Update callers — Endpoints layer** — Migrate every endpoint, not only the currently known files. Use the node/link/proxy API and convert proxies to unchanged JSON response shapes at the endpoint/application boundary. Endpoints never access repositories or database rows directly. | ⏳ |
| 68 | **Update callers — Application layer** — Migrate `image_processor.py`, `graph_service.py`, analysis services, data transformation, and every other application caller. Replace direct `PathOps` use with the injected graph filesystem port where appropriate. Keep response shaping and UI/API concepts out of domain objects. | ⏳ |
| 69 | **Update callers — Domain logic layer** — Update every domain Protocol and algorithm to the node/link/proxy vocabulary. Domain algorithms depend on narrow Protocols and do not import application or infrastructure. They use graph methods rather than repositories or database rows. | ⏳ |
| 70 | **Update callers — CLI/build layer and test fakes** — Migrate database, vector, preparation, statistics, command, and test-double callers. CLI commands use `CrystalGraph`; they do not open SQLite or call persistence implementations directly. | ⏳ |
| 71 | **Tests and verification** — Add colocated tests for proxy navigation and construction ownership, explicit graph lifecycle including a valid empty graph, history replacement and clearing, write ordering and failure behavior, filesystem ports and infrastructure implementation, `cache.db` rebuild assumptions, and unchanged endpoint JSON shapes. Search the full package for old image/comparison API names, direct repository access, `weight`, and `transitive_depth`. Run pytest, ruff ARG/F401, pyright against one documented baseline, the AST layer scan, the DB-proxy scan, route parity, and node registration. Update this plan’s status only after all gates pass. | ⏳ |

---

## Appendix B — Verification Baselines (2026-08-27)

### pyright strict: 455 errors (documented baseline)

All pre-existing, zero new errors allowed per change. Breakdown by category:

| Category | Files | Notes |
|----------|-------|-------|
| `mediapipe_provider.py` | 16 | Missing stubs for `mediapipe` — pre-sanctioned per #53 |
| `model_loader.py` | 58 | Missing stubs for `huggingface_hub`, `timm`, `tensorflow` — pre-sanctioned per #53 |
| `plot.py` | 64 | Missing stubs for `scipy`, `matplotlib`, `sklearn` — pre-sanctioned |
| `model_trainer.py` | 52 | Missing stubs for `lightgbm`, `sklearn` — pre-sanctioned |
| `pair_data.py` | 1 | Minor dict type annotation |
| `path_handler.py` | 1 | `old_history: Any` |
| `test_architecture.py` | 8 | Test helper type annotations |
| `test_general.py` | 12 | **Syntax errors** (see below) — general suite runs only on explicit prompt |

**Action:** No fixes needed for Phase E tasks — these are pre-existing baseline errors. Only fix new errors introduced by our changes.

### ruff ARG/F401: 4 errors (all in `test_general.py`)

Syntax errors in general test suite (only runs on explicit prompt):
- Line 639: Unexpected indentation
- Line 641: Unindent mismatch
- Line 642: Unexpected indentation
- Line 659: Expected statement (broken class definition)

**Action:** Fix when running general suite (§3.15 #59), not during Phase E.

### Architecture tests: 2/2 passing

- `test_no_layer_violations` ✅
- `test_no_db_access_outside_proxies` ✅

### Route map parity: Verified

No `/task` routes; blueprints match §1.1 + §2.

### Node registration: `AestheticScore` registers ✅

- 2026-08-17 (v4): task system deleted; synchronous log-captured endpoints;
  rename cascade; ServerDeps superset; matplotlib Agg; dead routes removed.
- 2026-08-18 (v5 + §3.10 audit): five files routes shipped; docs aligned;
  audit executed (try/except 51→12, prints 97→25, inline imports hoisted,
  defaults −48); pyright baselines over time 724→668→640→604.
- Incident: a misdirected test stub deleted output/models/ during route
  testing (motivated ground rule 14).
- 2026-08-23: plan consolidated into this v6 document.
- 2026-08-24 session: §3.11 #42–#46 complete; #47 full proxy migration +
  RuntimeError flip; #49/#50 cache architecture batch (state.py deleted);
  #51 moves; #53 typings deleted (baseline 455); #54 ruff gate at zero;
  tests/test_architecture.py authored; realdata tests blocked by default
  after an accidental general-suite run hit the known destructive path
  (user regenerates output data manually via build all → train-model).
- 2026-08-27 session: Document reorganization — completed tasks consolidated,
  status updated, remaining work clarified. No code changes.
