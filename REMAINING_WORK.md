# Remaining Modifications — comfyui_image_scorer Reorganization

This document enumerates all remaining work needed to complete the reorganization described in `REORGANIZATION_PLAN.md` and `README.md`. It is organized by priority and dependency order. Do not program anything yet — this is the analysis checklist.

**How to use this file:** Work top-to-bottom. Fix dependency violations (§1-3) first, then create missing files (§4), then migrate old-folder content (§6), then fill structural gaps (§5). Attempting files out of order risks circular imports and broken references.

---

## Agent Instructions

- **Read everything freely.** There are no restrictions on reading files in any folder.
- **Modification scope:** All code changes must be confined to `E:\ComfyUI\custom_nodes\comfyui_image_scorer`. Do not modify files outside this directory.
- **Old folder (`comfyui_image_scorer_old/`):** Read-only reference only. Do not write, move, rename, or delete anything inside `comfyui_image_scorer_old/`. That folder will be removed after the migration is complete.
- **Tests and run commands:** Use the Python venv at `E:\ComfyUI` only. Activate it before running any tests (`pytest`), type checks (`pyright`), or the package. Do not use any other Python environment.
- **Import style:** After all moves are complete, all imports must be absolute from the package root (`comfyui_image_scorer.*`). No relative imports, no `sys.path` manipulation, no `__package__` hacks.

---

## 0. Pre-Flight Check

Before starting any modifications:

| Check | Command | Purpose |
|---|---|---|
| `pyproject.toml` | Read and verify package name, version, deps, entry points match new structure | Ensure editable install works after restructuring |
| `uv.lock` / `requirements.txt` | Verify no drift from `pyproject.toml` | Prevent dependency version mismatches after moves |
| `pyproject.toml [project.scripts]` | Confirm `comfyui-scorer` entry point targets `adapters.cli.main:main` or root `scorer.py` | CLI must resolve after `adapters/cli/main.py` is created |
| Full test suite | `pytest` (if available) | Establish pre-change baseline |
| Type check | `pyright` (if available) | Establish pre-change baseline |

---

## 1. CRITICAL: Dependency Violations (domain/ importing from infrastructure/ and application/)

Per the README architecture rules, `domain` may **only** import from `core`. The following files violate this rule. Each one needs its direct imports replaced with indirection through `application.services` or domain ports.

**⚠️ Circular import risk:** Several of these fixes change imports in files that are also imported by `application/services/graph_service.py`. The order of changes matters — fix `domain/` imports first, then verify `application/` can still import from `domain/`.

| File | Offending Import | Should Go Through | ⚠️ Circular Risk |
|---|---|---|---|
| `domain/vectors/map_vector.py` | `infrastructure.loading.maps_loader` | `application.services` or constructor injection | Low — `maps_loader` is not imported by `graph_service.py` |
| `domain/vectors/person_map_vector.py` | `infrastructure.loading.maps_loader` | `application.services` or constructor injection | Low — same as above |
| `domain/vectors/embedding_vector.py` | `infrastructure.ml_models.model_loader` | `application.services` or constructor injection | Medium — `embedding_vector.py` is imported by `vector_list.py` in `application/` |
| `domain/vectors/image_vector.py` | `infrastructure.ml_models.model_loader` | `application.services` or constructor injection | Medium — same dependency chain |
| `domain/vectors/image_vector.py` | `infrastructure.ml_models.batch_sizer` | `application.services` or constructor injection | Medium — same |
| `domain/analysis/attribute_analysis.py` | `infrastructure.ml_models.model_loader` | `application.services` or constructor injection | Low |
| `domain/data_transformation/data_transformer.py` | `infrastructure.loading.training_loader` | `application.services` or constructor injection | Medium — `data_transformer.py` may be imported by adapters |
| `domain/data_transformation/data_transformer.py` | `infrastructure.ml_models.training.model_trainer` | `application.services` or constructor injection | Medium — same |
| `domain/comparison/state.py` | `infrastructure.persistence.images_repository` | `application.services` or constructor injection | **HIGH** — `infrastructure.persistence.images_repository` imports from `core`, creating potential cycle if domain imports back |
| `domain/comparison/state.py` | `application.services.graph_service` | Remove — should not import from application layer | **CRITICAL** — `graph_service.py` imports from `domain`, so this is a direct cycle |
| `domain/comparison/comparison_recorder.py` | `infrastructure.persistence.comparisons_repository` | `application.services` or constructor injection | **HIGH** — same as images_repository |
| `domain/comparison/comparison_recorder.py` | `infrastructure.persistence.images_repository` | `application.services` or constructor injection | **HIGH** — same |
| `domain/comparison/comparison_recorder.py` | `infrastructure.persistence.path_handler` | `application.services` or constructor injection | **HIGH** — `path_handler` imports from `infrastructure.persistence.comparisons_repository` |
| `domain/comparison/comparison_recorder.py` | `application.services.graph_service` | Remove — should not import from application layer | **CRITICAL** — same cycle as state.py |

### Recommended order for §1 fixes:

1. **First:** Remove `application.services.graph_service` imports from `state.py` and `comparison_recorder.py` (these create direct cycles)
2. **Second:** Fix `infrastructure.persistence.*` imports in `domain/comparison/` — these require `application.services` to be the indirection layer
3. **Third:** Fix `infrastructure.ml_models.*` imports in `domain/vectors/` and `domain/analysis/`
4. **Fourth:** Fix `infrastructure.loading.*` and `infrastructure.ml_models.training.*` imports in `domain/data_transformation/`
5. **Fifth:** Fix `application/services/vector_list.py` imports from `infrastructure`

---

## 2. CRITICAL: Dependency Violations (application/ importing from infrastructure/)

Per the README, `application` may import from `core` + `domain` only.

| File | Offending Import | Should Go Through | ⚠️ Circular Risk |
|---|---|---|---|
| `application/services/vector_list.py` | `infrastructure.loading.maps_loader` | Use domain ports or inject at wire-up time | **HIGH** — `vector_list.py` is imported by `adapters/comfyui/nodes/aesthetic_score/node.py`; if it then imports infrastructure, adapters also violate rules |
| `application/services/vector_list.py` | `infrastructure.persistence.comparisons_repository` | Same | **HIGH** — same cycle risk |
| `application/services/vector_list.py` | `infrastructure.persistence.images_repository` | Same | **HIGH** — same cycle risk |

**Recommended fix:** Refactor `vector_list.py` to accept repository instances as constructor parameters (dependency injection). The `application` layer should define ports/interfaces and receive implementations at wire-up time (in `__init__.py` or a composition root).

---

## 3. CRITICAL: Dependency Violations (adapters/ importing from infrastructure/ and domain/ directly)

Per the README, `adapters` may import from `core` + `domain` + `application`. But nodes should contain **zero domain logic** — only translation and delegation to `application.services`.

| File | Offending Import | Should Go Through | ⚠️ Circular Risk |
|---|---|---|---|
| `adapters/comfyui/nodes/aesthetic_score/node.py` | `infrastructure.loading.training_loader` | `application.services` | Medium — `training_loader` is in infrastructure, not imported by graph_service |
| `adapters/comfyui/nodes/aesthetic_score/node.py` | `domain.analysis.image_analysis` | Delegate to `application.services` | **HIGH** — `image_analysis.py` imports `core` and `domain`, node imports domain directly (bypassing application) |
| `adapters/comfyui/nodes/aesthetic_score/node.py` | `domain.vectors.image_vector` | Delegate to `application.services` | **HIGH** — same |
| `adapters/comfyui/nodes/aesthetic_score/node.py` | `domain.data_transformation.data_transformer` | Delegate to `application.services` | **HIGH** — same |
| `adapters/comfyui/nodes/aesthetic_score/node.py` | `domain.training.calibration` | Delegate to `application.services` | **HIGH** — same |

**Recommended fix:** Create application service methods that encapsulate the domain logic currently called directly by the node. The node should only call `application.services.*` and `core.*`.

---

## 4. MISSING FILES — Need to Be Created

These files do not exist in either the new or old folder, or exist in the old folder but have not been migrated to the correct new location.

### 4.1 `adapters/cli/main.py`

- **Status**: Does not exist anywhere (new or old folder)
- **Why**: `scorer.py` at root imports `from comfyui_image_scorer.adapters.cli.main import main`
- **Content needed**: CLI entry point with `main()` function. Migrate logic from root `scorer.py` and create the `adapters/cli/commands/` implementations from old `external_modules/` server/training/vector/database logic.
- **References**: `REORGANIZATION_PLAN.md` §6, `README.md` § Adapters/CLI
- **⚠️ Circular risk**: This file will import from `application.services` and `domain` — ensure no cycle back to `adapters`

### 4.2 `infrastructure/persistence/path_handler.py`

- **Status**: Does not exist in new folder. Old code is at `comfyui_image_scorer_old/external_modules/database_structure/path_handler.py`
- **Why**: `domain/comparison/comparison_recorder.py` imports `sync_image_metadata_to_json` from `comfyui_image_scorer.infrastructure.persistence.path_handler`
- **Content needed**: Migrate `sync_image_metadata_to_json` and `append_comparison_history_to_json` from old `external_modules/database_structure/path_handler.py`, updating imports to absolute `comfyui_image_scorer.*` style. Remove `sys.path.insert` hack and relative imports from old code.
- **⚠️ Circular risk**: The old `path_handler.py` imports from `comparisons_table.py` (now `infrastructure/persistence/comparisons_repository.py`) and `images_table.py` (now `infrastructure/persistence/images_repository.py`). These files do NOT import from `path_handler.py`, so no cycle — but verify after migration.

### 4.3 `adapters/server/` — actual server code

- **Status**: `adapters/server/` has only empty `__init__.py` dirs and `frontend/` — no Python server files
- **Why**: Old `external_modules/server/server.py` and `external_modules/server/image_processor.py` have not been migrated
- **Content needed**: Migrate from `comfyui_image_scorer_old/external_modules/server/server.py` → `adapters/server/main.py` and `image_processor.py` → `adapters/server/processor.py`, restructuring per the README (`adapters/server/routing/`, `adapters/server/endpoints/`, `adapters/server/middleware/`)
- **⚠️ Circular risk**: Old `server.py` uses `sys.path.insert` and relative imports from `external_modules`. All must be converted to absolute `comfyui_image_scorer.*` imports. `server.py` imports from `shared.*` which no longer exists — must redirect to `core.*` and `domain.*`.

### 4.4 `adapters/comfyui/node_registry.py`

- **Status**: Does not exist
- **Why**: README specifies `adapters/comfyui/node_registry.py` as the central registration module
- **Content needed**: Create node registry with `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`
- **⚠️ Circular risk**: Must not import from `infrastructure` or `adapters/*` subdirectories directly. Should only import from `application.services` and `core`.

### 4.5 `adapters/cli/commands/` — CLI subcommand implementations

- **Status**: `adapters/cli/commands/` has only `__init__.py` — empty
- **Why**: Need `server.py`, `training.py`, `vectors.py`, `database.py` subcommand modules
- **Content needed**: Port from old `external_modules/` server/training/vector/database logic
- **⚠️ Circular risk**: Each command module will import from `application/services/` and `infrastructure/` — ensure no back-import to `cli/`

### 4.6 Test files (migration from old folder)

The following test files exist only in `comfyui_image_scorer_old/` and have not been migrated to the new structure:

| Old Test File | Target Location |
|---|---|
| `external_modules/tests/test_comparison_cleanup.py` | `domain/comparison/tests/` |
| `external_modules/tests/test_comparison_recorder.py` | `domain/comparison/tests/` |
| `external_modules/tests/test_database_structure.py` | `infrastructure/persistence/tests/` |
| `external_modules/tests/test_graph_helpers.py` | `domain/graph/tests/` |
| `external_modules/tests/test_image_processor.py` | `adapters/server/tests/` |
| `external_modules/tests/test_path_handler_and_folder_organization.py` | `infrastructure/persistence/tests/` |
| `external_modules/tests/test_state.py` | `domain/comparison/tests/` |
| `external_modules/tests/test_trueskill_rating.py` | `domain/analysis/tests/` |
| `shared/analysis/tests/test_analysis.py` | `domain/analysis/tests/` |
| `shared/graph/tests/test_chain_manager.py` | `domain/graph/tests/` |
| `shared/loaders/tests/test_maps_loader.py` | `infrastructure/loading/tests/` |
| `shared/loaders/tests/test_model_loader.py` | `infrastructure/ml_models/tests/` |
| `shared/loaders/tests/test_training_loader.py` | `infrastructure/loading/tests/` |
| `shared/tests/test_config.py` | `core/configuration/tests/` |
| `shared/tests/test_io_utils_helpers.py` | `core/io/tests/` |
| `shared/tests/test_logger.py` | `core/observability/tests/` |
| `shared/tests/test_tasks.py` | `core/utilities/tests/` |
| `shared/vectors/tests/test_terms.py` | `domain/vectors/tests/` |
| `shared/vectors/tests/test_vector_list.py` | `domain/vectors/tests/` |
| `shared/vectors/tests/test_vector_primitives.py` | `domain/vectors/tests/` |
| `nodes/aesthetic_score/tests/test_node.py` | `adapters/comfyui/nodes/aesthetic_score/tests/` |

---

## 5. MISPLACED FILES — In Wrong Location in New Structure

### 5.1 Old `adapters/*/` directories are renamed `external_modules/` content

The following directories in the new `adapters/` layer are **not properly restructured** — they are old `external_modules/` directories just renamed, containing `endpoints.py`, `frontend/`, and helper files that mix HTTP/frontend logic with domain logic.

These need to be decomposed and their code redistributed:

| Misplaced Path | Specific Files | Should Be Reorganized Into |
|---|---|---|
| `adapters/analysis/` | `endpoints.py`, `helpers.py`, `frontend/` | `adapters/server/endpoints/analysis.py`, domain logic into `domain/analysis/` |
| `adapters/comparison/algorithm/` | `comparison_algorithm.py`, `constant_comparison.py`, `graph_helper.py`, `merge_sorter.py`, `pair_actor.py`, `phase_ordering.py`, `state.py`, `trueskill.py`, `view.py` | `domain/comparison/algorithm/` (business logic), `adapters/server/endpoints/` (HTTP handlers) |
| `adapters/comparison/endpoints.py` | REST endpoint handlers | `adapters/server/endpoints/comparison.py` |
| `adapters/comparison/frontend/` | Static HTML/CSS/JS | Keep as static assets (not Python code) |
| `adapters/data_transform/` | `endpoints.py`, `config/maps.py`, `data/manager.py`, `data/metadata.py`, `data/processing.py`, `features/meta.py`, `prepare_data.py`, `frontend/` | `domain/data_transformation/` (business logic), `adapters/server/endpoints/` (HTTP handlers) |
| `adapters/database_structure/` | `endpoints.py`, `cleanup_orphans.py`, `deduplicate_scored.py`, `folder_organizer.py`, `path_handler.py`, `schema.py` (already migrated), `images_table.py` (already migrated), `comparisons_table.py` (already migrated) | `infrastructure/persistence/` (persistence logic), `adapters/server/endpoints/` (HTTP handlers) |
| `adapters/gallery/` | `endpoints.py`, `frontend/` | `adapters/server/endpoints/gallery.py`, `adapters/comfyui/nodes/gallery/` |
| `adapters/maps/` | `endpoints.py`, `frontend/graph_map/*`, `frontend/maps.css/html` | `adapters/server/endpoints/maps.py`, static assets |
| `adapters/maps2/` | `endpoints.py`, `frontend/graph_map/*`, `frontend/maps.css/html` | Same as maps above (maps2 appears to be a newer version of maps) |
| `adapters/server/` | Only empty `__init__.py` dirs + `frontend/` | Needs actual server code migrated from old `external_modules/server/` (see §4.3) |
| `adapters/training_hyperparameters/` | `endpoints.py`, `config/`, `frontend/`, `hyperparameter_optimizer.py`, `run.py`, `text_data/` | `domain/training/` (logic), `adapters/server/endpoints/` (HTTP handlers) |

### 5.2 `scorer.py` at root

- **Current**: Imports `from comfyui_image_scorer.adapters.cli.main import main` and calls `sys.exit(main())`
- **Issue**: `adapters/cli/main.py` does not exist yet (see §4.1)
- **Fix**: Either create `adapters/cli/main.py` first, or keep `scorer.py` as-is pending that file's creation. Note: `scorer.py` also uses `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` which the README says should be replaced by editable install + absolute imports. This is a temporary compatibility shim.

---

## 6. STRUCTURAL GAPS — Empty Directories That Need Content

Per the plan and README, these directories are empty or have only `__init__.py` when they should contain code:

| Directory | Expected Content |
|---|---|
| `adapters/comfyui/nodes/ranking/` | Ranking/comparison UI nodes |
| `adapters/comfyui/nodes/gallery/` | Gallery browser nodes |
| `adapters/comfyui/nodes/maps/` | Map visualization nodes |
| `adapters/comfyui/input_adapters/` | TYPE adapters (IMAGE, LATENT, STRING → domain DTOs) |
| `adapters/comfyui/output_adapters/` | Domain results → ComfyUI TYPE adapters |
| `adapters/cli/commands/server.py` | Server subcommand |
| `adapters/cli/commands/training.py` | Training subcommand |
| `adapters/cli/commands/vectors.py` | Vectors subcommand |
| `adapters/cli/commands/database.py` | Database subcommand |
| `adapters/server/endpoints/` | Thin request/response handlers (populated from old `external_modules/*/endpoints.py`) |
| `adapters/server/routing/` | Blueprint registration |
| `adapters/server/middleware/` | Error handling, CORS, logging |
| `adapters/server/main.py` | Flask app entry (migrated from old `external_modules/server/server.py`) |
| `adapters/server/processor.py` | Image processing (migrated from old `external_modules/server/image_processor.py`) |
| `application/dto/` | Data transfer objects |
| `application/ports/` | Application-level port interfaces |
| `infrastructure/external_services/` | External API clients (future) |
| `infrastructure/ml_models/` | Already exists but domain imports it directly (see §1) |
| `domain/loading/` | Empty — should exist per README (or loading stays in `infrastructure/loading/`) |
| Test directories for all above | Colocated `tests/` next to tested module |

---

## 7. DUPLICATION AND CONFIRMED ITEMS

| Item | Status |
|---|---|
| `core/utilities/concurrency.py` has `parallel_batch` and `parallel_for` (migrated from `core/io/serialization.py`) | ✅ Done |
| `core/io/serialization.py` no longer has these functions | ✅ Confirmed |
| `domain/graph/crystal_graph.py` removed from `domain/` (moved to `application/services/graph_service.py`) | ✅ Done |
| `domain/database/schema.py` removed from `domain/` (moved to `infrastructure/persistence/database.py`) | ✅ Done |
| `domain/database/comparisons_table.py` removed from `domain/` (moved to `infrastructure/persistence/comparisons_repository.py`) | ✅ Done |
| `_ImageRepo` extracted to `infrastructure/persistence/images_repository.py` | ✅ Done |
| Global `crystal_graph` instance removed | ✅ Done |

---

## 8. OLD FOLDER — What Still Exists There and Has Not Been Migrated

The `comfyui_image_scorer_old/` folder contains the original codebase. Files that have **not** been fully migrated to the new structure (still only in old folder, or only exist in old folder with correct content):

### 8.1 Already migrated (no action needed)

| Old File | Target New Location | Status |
|---|---|---|
| `shared/config.py` | `core/configuration/settings.py` | Done |
| `shared/paths.py` | `core/filesystem/paths.py` | Done |
| `shared/logger.py` | `core/observability/logger.py` | Done |
| `shared/io.py` | `core/io/serialization.py` (functions migrated) + `core/utilities/concurrency.py` | Done |
| `shared/utils.py` | `core/utilities/utils.py` | Done |
| `shared/helpers.py` | `core/utilities/helpers.py` | Done |
| `shared/tasks.py` | `core/utilities/tasks.py` | Done |
| `shared/analysis/*` | `domain/analysis/*` | Done |
| `shared/graph/*` (ex-crystal_graph) | `domain/graph/*` | Done |
| `shared/graph/crystal_graph.py` | `application/services/graph_service.py` | Done |
| `shared/vectors/*` | `domain/vectors/*` | Done |
| `shared/loaders/*` | `infrastructure/loading/*` | Done |
| `shared/training/*` (ex-model_trainer, pair_data) | `domain/training/*` | Done |
| `shared/training/model_trainer.py` + `pair_data.py` | `infrastructure/ml_models/training/*` | Done |
| `external_modules/database_structure/schema.py` | `infrastructure/persistence/database.py` | Done |
| `external_modules/database_structure/comparisons_table.py` | `infrastructure/persistence/comparisons_repository.py` | Done |
| `external_modules/database_structure/images_table.py` | `infrastructure/persistence/images_repository.py` | Done |

### 8.2 Not yet migrated (action needed)

| Old File | Target New Location | Status |
|---|---|---|
| `external_modules/database_structure/path_handler.py` | `infrastructure/persistence/path_handler.py` | Not migrated |
| `external_modules/database_structure/cleanup_orphans.py` | `infrastructure/persistence/` | Not migrated |
| `external_modules/database_structure/deduplicate_scored.py` | `infrastructure/persistence/` | Not migrated |
| `external_modules/database_structure/folder_organizer.py` | `infrastructure/persistence/` | Not migrated |
| `external_modules/database_structure/endpoints.py` | `adapters/server/endpoints/` | Not migrated |
| `external_modules/comparison/algorithm/*` | `domain/comparison/algorithm/` | Not migrated |
| `external_modules/comparison/endpoints.py` | `adapters/server/endpoints/` | Not migrated |
| `external_modules/analysis/endpoints.py` | `adapters/server/endpoints/` | Not migrated |
| `external_modules/analysis/helpers.py` | Refactor (domain logic → `domain/analysis/`, endpoint logic → `adapters/server/endpoints/`) | Not migrated |
| `external_modules/data_transform/*` | `domain/data_transformation/` | Not migrated |
| `external_modules/gallery/endpoints.py` | `adapters/server/endpoints/` | Not migrated |
| `external_modules/maps/endpoints.py` | `adapters/server/endpoints/` | Not migrated |
| `external_modules/maps2/endpoints.py` | `adapters/server/endpoints/` | Not migrated |
| `external_modules/server/server.py` | `adapters/server/main.py` | Not migrated |
| `external_modules/server/image_processor.py` | `adapters/server/processor.py` | Not migrated |
| `external_modules/training_hyperparameters/config/*.py` | `domain/training/` | Not migrated |
| `external_modules/training_hyperparameters/hyperparameter_optimizer.py` | `domain/training/` | Not migrated |
| `external_modules/training_hyperparameters/run.py` | `adapters/cli/commands/` | Not migrated |
| `external_modules/training_hyperparameters/text_data/*` | `domain/training/` | Not migrated |
| `external_modules/analysis/frontend/*` | Static assets | Not migrated (renamed in `adapters/analysis/frontend/` as empty shell) |
| `external_modules/comparison/frontend/*` | Static assets | Not migrated (renamed as `adapters/comparison/frontend/` empty shell) |
| `external_modules/data_transform/frontend/*` | Static assets | Not migrated |
| `external_modules/database_structure/frontend/*` | Static assets | Not migrated |
| `external_modules/gallery/frontend/*` | Static assets | Not migrated |
| `external_modules/maps/frontend/*` | Static assets | Not migrated |
| `external_modules/maps2/frontend/*` | Static assets | Not migrated |
| `external_modules/server/frontend/*` | Static assets | Not migrated |
| `external_modules/training_hyperparameters/frontend/*` | Static assets | Not migrated |
| `external_modules/tests/*` | `domain/*/tests/` + `infrastructure/*/tests/` | Not migrated |
| `shared/*/tests/*` | `core/*/tests/` + `domain/*/tests/` | Not migrated |
| `nodes/*` | `adapters/comfyui/nodes/` | Partially (only aesthetic_score/node.py) |
| `external_modules/comparison/algorithm/view.py` | May overlap with `domain/comparison/state.py` — verify if same or different | Not migrated |

---

## 9. REORGANIZATION PLAN GAPS (from REORGANIZATION_PLAN.md)

These items from the plan have not yet been completed:

| Plan Item | Status |
|---|---|
| Move `parallel_batch`, `parallel_for` from `core/io/serialization.py` to `core/utilities/concurrency.py` | Done |
| Move `domain/database/schema.py` → `infrastructure/persistence/database.py` | Done |
| Move `domain/database/comparisons_table.py` → `infrastructure/persistence/comparisons_repository.py` | Done |
| Move `domain/graph/crystal_graph.py` → `application/services/graph_service.py` | Done |
| Create `infrastructure/persistence/images_repository.py` from `_ImageRepo` | Done |
| Remove global `crystal_graph` instance from `crystal_graph.py` | Done (refactored into `graph_service.py`) |
| Create `adapters/comfyui/__init__.py` with node mappings | Partially done (only AestheticScore) |
| Create `adapters/cli/main.py` | Not done (§4.1) |
| Migrate `external_modules/database_structure/path_handler.py` → `infrastructure/persistence/path_handler.py` | Not done (§4.2) |
| Migrate server code from `external_modules/server/` → `adapters/server/` | Not done (§4.3) |
| Migrate CLI commands to `adapters/cli/commands/` | Not done (§4.5) |
| Migrate old `external_modules/*/endpoints.py` → `adapters/server/endpoints/` | Not done (§5.1, §8.2) |
| Migrate old `shared/*/tests/*` → new test locations | Not done (§4.6) |
| Migrate old `external_modules/tests/*` → new test locations | Not done (§4.6) |
| Migrate `external_modules/comparison/algorithm/*` → `domain/comparison/algorithm/` | Not done (§8.2) |
| Migrate `external_modules/database_structure/cleanup_orphans.py`, `deduplicate_scored.py`, `folder_organizer.py` → `infrastructure/persistence/` | Not done (§8.2) |
| Migrate `external_modules/gallery/endpoints.py`, `maps/endpoints.py`, `maps2/endpoints.py`, `training_hyperparameters/*` → proper locations | Not done (§8.2) |
| Fix all cross-layer dependency violations (§1-3 above) | Not done |
| Migrate old comparison algorithm files → `domain/comparison/algorithm/` | Not done (§8.2) |
| Complete `adapters/comfyui/` node registrations | Not done |
| Populate `adapters/comfyui/nodes/ranking/`, `gallery/`, `maps/` | Not done |