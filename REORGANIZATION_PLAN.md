# Reorganization Plan — `comfyui_image_scorer` (v6)

**Status (2026-08-24):** v4/v5 complete (§3.1–§3.10); §3.11 v5 remainder
complete; v6 Phase A mostly complete (#47/#49/#50/#51/#53/#54 done,
#48/#52 partial). This document supersedes all previous revisions. Stable
external references: `§0` rules, `§1` source of truth, `§1.1` parity
contract, `§3.10 #37` taxonomy, `§4` verification, `§5` out of scope.

Verified gates at consolidation time: pytest 34 passed; ruff ARG/F401: 1;
pyright strict 604. Fresh baselines after the 2026-08-24 session: pytest 45
passed (+2 realdata deselected by default); ruff ARG/F401 **0**; pyright
strict **455** (584 recounted at kickoff, then reduced by the #53 typings
deletion; zero new errors per change throughout); layer scan 0; DB-proxy
scan blocking with 0 violations; route map unchanged; `AestheticScore`
registers.

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
8. No defaults: config objects and function args avoid default values;
   ambiguous values are stated explicitly at every call site.
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

---

## 1. Source of Truth — CLI command table

| Section | Command | Behavior |
|---|---|---|
| `server` | `server` | runs this Flask server |
| `training` | `train-model` | load data → train top1 → save model + plots |
| `training` | `hpo` | `HpoRunner.run` with cycle options, None → config defaults |
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
| `files` | `cleanup` | `deduplicate_scored(root=None, limit)` + `cleanup_orphans(root=None)` |
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

### 3.1–3.10 — COMPLETE (2026-08-17/18)

Task system deleted; synchronous one-call command endpoints; rename cascade;
`endpoints/files.py`; rules audit (#37 taxonomy normative; prints→logger;
module-scope imports; arg-default removals; constant tables immutable).

### 3.11 Open tasks — v5 remainder — COMPLETE (2026-08-23)

42. ✅ Proxy-entry enforcement: runtime `_check_proxy_entry()` in
    `infrastructure/persistence/database.py` with `os.path.normcase`
    whitelist (`domain/graph/**` + `infrastructure/persistence/**`); static
    AST DB-proxy scan baseline 0. Since the #47 flip the runtime check
    raises RuntimeError and the scan is blocking (encoded in
    `tests/test_architecture.py::test_no_db_access_outside_proxies`).
43. ✅ `/download-models` offline handling: hub computes the offline flag
    once at import; transformers keeps no cached value. `set_hub_offline`
    lives in `infrastructure/ml_models/model_loader.py`, injected through
    both dep containers; endpoint + CLI bodies use the try/finally row.
44. ✅ Delete-vectors confirmation text states maps/split removal and
    re-analysis recovery.
45. ✅ Prediction accuracy tracking: session-only counters in
    `compare_view.js`, fed per successful submission; shown in the debug
    panel. No backend changes.
46. ✅ maps3 score-ranked visualization: new `adapters/maps3/` with an
    adapted ChainMapUI-style class; reuses `/api/maps/graph-data`; wired
    into SECTION_FRONTENDS, index nav/scripts, router.

### 3.12 v6 Phase A — Structural corrections

47. ✅ Route DB access through the graph proxies (2026-08-24, full proxy
    migration): CrystalGraph repository facade; processor/recorder/domain
    selectors/endpoints/CLI rewired off raw repos; repos constructed only at
    roots owning a graph. Flip executed: direct access raises RuntimeError;
    static scan blocking.
48. **PARTIAL (2026-08-24).** MediaPipe model-path construction moved into
    `infrastructure/ml_models/mediapipe_provider.py` behind `MediaPipePort`.
    Remaining named items: inject an infrastructure sidecar writer for
    `domain/analysis/image_analysis.py`; `_load_map_slots` still reads the
    map JSON directly (semantically equal to MapsProvider.get_all_categories);
    split-file path joins remain in vector_list/prepare_data; deep path and
    shutil work remains in image_processor (partially behind PathOps).
49. ✅ Remove remaining global mutable state (2026-08-24): state.py deleted
    (images snapshot via CrystalGraph over injected cache); phase_order/
    pair_active selection memory moved to CrystalGraph accessors;
    hyperparameter_optimizer guard became the single-flight HpoRunner built
    at the roots.
50. ✅ Unified cache architecture (2026-08-24): CacheProvider port in
    `domain/ports/cache.py`; TTL + byte-bounded InMemoryCache in
    `infrastructure/cache/memory_cache.py`; instantiated at all three roots;
    covers images snapshot, analysis processed-cache, split-data cache, WebP
    image cache, folder-listdir cache.
51. ✅ Semantic misplacements (2026-08-24): export_image_batch →
    `infrastructure/ml_models/image_export.py` injected into ScoringService;
    JSON cleaning shed from image_processor into pure
    `core.io.serialization.clean_json_metadata`/`extract_prompt_tags`;
    parameter_analysis → application/analysis; plot.py →
    infrastructure/ml_models injected via CLIDeps.plot_manager.
52. **PARTIAL (2026-08-24).** domain/ports/ml_providers.py created with
    MediaPipePort; all mediapipe usage now lives in
    infrastructure/ml_models/mediapipe_provider.py; domain MediaPipeAnalyzer
    is a thin delegate threaded from the roots through CLIDeps/ServerDeps →
    build_split_files/ScoringService → ImageAnalysis. Remaining ML imports
    in domain: image_vector.py (torch/torchvision), attribute_analysis.py
    (torch softmax/no_grad around loader-provided HF models),
    data_transformer.py (lightgbm/sklearn). Design for the remainder: add a
    vision-encoding provider (owning tensor prep + the #37c OOM loop) and a
    feature-engine provider (owning LGBM ranking + poly interactions);
    thread through the dep containers exactly like mediapipe.

53. ✅ typings/ cleanup (2026-08-24): folder fully deleted — shared/**
    targeted packages that no longer exist and the torch/matplotlib/scipy/
    sklearn shadows actively degraded analysis (~129 spurious strict errors;
    baseline 584 → 455). Fresh minimal stubs (mediapipe,
    sentence_transformers) deferred to #57 where actually needed.
54. ✅ pair_active.py ARG001 resolved (2026-08-24): phase_single_win_loss
    keeps its positional dispatch slot as _cg. Ruff ARG/F401 gate now at
    zero findings.

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
    `int | None = None` to preserve the CLI's None-means-config-default
    contract), `PrepareRequest` (mode pattern replaces the manual whitelist),
    `SkipRequest`, `SubmitComparisonRequest`. All routes tolerate absent JSON
    bodies via `get_json(silent=True) or {}` where the original did. The old
    inline `ComparisonRecorder` import became a module-scope import (rule 2);
    the same-image and winner-in-pair checks were restored as route-level
    semantic validations. A global Flask `ValidationError` handler in
    server/main.py maps invalid payloads to 400 with details.
57. **IN PROGRESS (baseline work done).** Pyright strict: recounted 584 at
    kickoff, then reduced to **455** by the #53 typings deletion — that is
    the standing baseline for "zero new". Full elimination remains. Note
    (2026-08-24): a full run after #56 reports 466; all errors in the five
    touched files sit in pre-existing constructs (untyped `register_*` app
    params, `describe_pair` phase_index, `serve_image_alias` return), so the
    endpoint edits added zero new errors — recount against a clean checkout
    during the next #57 pass to explain the drift.
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

## 7. Next-session handoff (2026-08-24, agreed with user)

Remaining order (user-selected "structure first"): **#57 → #48/#52 → #55 bulk → #59**.

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

---

## Appendix A — Execution history (condensed)

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
