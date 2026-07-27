# Reorganization Plan — `comfyui_image_scorer`

Each function/class is assigned to its ideal file and folder based on purpose, ignoring current location.

---

## 1. Root (kept)

| File | Contents | Rationale |
|---|---|---|
| `__init__.py` | `__getattr__` lazy-loading `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` from `adapters.comfyui` | Package entry point — correct |
| `scorer.py` | CLI entry point (imports `main` from `adapters.cli.main`, exits with return code) | Keep at root for `python -m comfyui_image_scorer` / `pip-install script` interop |

---

## 2. Core Layer — `core/` (shared infrastructure, no business logic)

### `core/configuration/settings.py` — **kept**
Already in the right place.

| Assignment | Function/Class |
|---|---|
| keep | `_get_config_file` — resolves config path |
| keep | `_load_raw_config` — reads JSON config from disk |
| keep | `_save_raw_config` — writes JSON config to disk |
| keep | `ensure_dir` — creates directories |
| keep | `AutoSaveDict` — auto-saving mutable mapping |
| keep | `Config` — root + sub-config manager |

### `core/filesystem/paths.py` — **kept**
Already in the right place. Module-level path constants only.

### `core/observability/logger.py` — **kept**
Already in the right place. Full logging subsystem.

| Keep | `_custom_find_caller`, `_is_progress_line`, `set_log_filter_hook`, `get_logger`, `configure_package_logging`, `log_message` |
|---|---|
| Keep | `_TaskOutput`, `CaptureStream`, `SSELogBroadcaster`, `_DynamicModuleFilter`, `TaskLogHandler` |
| Keep | `ModuleLogger`, `SharedLogger`, `CustomFormatter` |

### `core/io/serialization.py` — **split**
Mostly correct. Two generic concurrency helpers should move to dedicated utility.

| Move from `core/io/` | Move to `core/utilities/concurrency.py` |
|---|---|
| `parallel_batch` | Generic sequential batch executor (not IO-specific) |
| `parallel_for` | Generic `ThreadPoolExecutor` with tqdm (not IO-specific) |

| Keep in `core/io/serialization.py` | Reason |
|---|---|
| `load_single_jsonl` | JSONL file format — IO concern |
| `write_single_jsonl` | JSONL file format — IO concern |
| `discover_files` | File-system walking — IO concern |
| `collect_single_file` | Image/metadata pair processing — IO concern |
| `collect_valid_files` | Multi-file collection — IO concern |
| `_recursive_parse_json` | JSON string parsing — IO concern |
| `load_json` | JSON file loading — IO concern |
| `atomic_write_json` | Atomic JSON write — IO concern |
| `load_single_entry_mapping` | JSON mapping load — IO concern |

---

## 3. Domain Layer — `domain/` (business logic, no side effects)

### `domain/graph/`

| File | Contents | Rationale |
|---|---|---|
| `chain_manager.py` | `ChainManager` class + module-level graph helpers (`parse_comparison`, `add_directed_edge`, `add_undirected_edge`, `process_one_comparison`, `has_no_predecessors`, `has_no_successors`, `find_top_nodes`, `find_bottom_nodes`, `bfs_one_component`, `index_component`, `build_components`, `same_component`, `find_common_chain_id`, `tarjan_scc`, `strongconnect`) | Core graph domain logic — **keep** |
| `node_proxy.py` | `NodeProxy` | Domain model — **keep** |
| `chain_proxy.py` | `ChainProxy` | Domain model — **keep** |
| `component_proxy.py` | `ComponentProxy` | Domain model — **keep** |
| `tests/test_chain_manager.py` | Chain manager tests | **keep** |

### `domain/vectors/`

| File | Contents | Rationale |
|---|---|---|
| `terms.py` | `extract_weight_from_paren`, `tokenize_by_depth`, `clean_term`, `filter_terms`, `deduplicate_terms`, `_extract_recursive`, `extract_terms`, `ExtractionResult` | Domain concepts (prompt parsing) — **keep** |
| `tests/test_terms.py` | Term extraction tests | **keep** |

### `domain/database/ports/`

| File | Contents | Rationale |
|---|---|---|
| `__init__.py` | Re-exports `ImageRepository`, `ComparisonRepository`, `PathResolver` | **keep** |
| `repository_ports.py` | `ImageRepository` protocol, `ComparisonRepository` protocol, `PathResolver` protocol | Domain interfaces (ports) — **keep** |

### Removed from `domain/` — moved to other layers (see below)

| Current Location | Move to | Reason |
|---|---|---|
| `domain/database/schema.py` | `infrastructure/persistence/database.py` | DB connection + schema creation are implementation, not domain |
| `domain/database/comparisons_table.py` | `infrastructure/persistence/comparisons_repository.py` | SQL CRUD is infrastructure implementation |
| `domain/graph/crystal_graph.py` | `application/services/graph_service.py` | Orchestration of repos + domain — application service |

---

## 4. Application Layer — `application/` (use cases / orchestration)

### `application/services/graph_service.py`

**Moved from** `domain/graph/crystal_graph.py`

| Class/Function | Role |
|---|---|
| `CrystalGraph` | Orchestrates `ChainManager` + repositories; provides high-level graph API for server/frontend/CLI consumers |

The `_ImageRepo` and `_ComparisonRepo` inner classes (module-level, conditionally defined) are **not** part of `CrystalGraph`'s concern — they are infrastructure wiring:

| Current location | Move to |
|---|---|
| `_ImageRepo` class (bottom of `crystal_graph.py`) | `infrastructure/persistence/images_repository.py` |
| `_ComparisonRepo` class (bottom of `crystal_graph.py`) | merge into `infrastructure/persistence/comparisons_repository.py` |

The global `crystal_graph` instance + auto-rebuild-on-import at the bottom of `crystal_graph.py` should be removed. The caller (server startup or CLI) should create and initialize the instance explicitly.

---

## 5. Infrastructure Layer — `infrastructure/` (implementations)

### `infrastructure/persistence/database.py`

**Moved from** `domain/database/schema.py`

| Function | Role |
|---|---|
| `get_db_connection` | Creates SQLite connection with WAL pragmas |
| `_ensure_meta_table` | Creates `meta` table |
| `_ensure_images_table` | Creates/migrates `images` table |
| `_ensure_comparisons_table` | Creates `comparisons` table |
| `init_database` | Runs all table creation, sets initial meta |
| `_set_meta_value` | Upserts into `meta` table |
| `get_meta_value` | Reads from `meta` table |
| `vacuum_database` | Runs `VACUUM` |

### `infrastructure/persistence/comparisons_repository.py`

**Moved from** `domain/database/comparisons_table.py` + merged with `_ComparisonRepo` from `crystal_graph.py`

| Function/Class | Role |
|---|---|
| `_canonicalize_pair` | Sort pair filenames |
| `_safe_parse_timestamp` | Safe timestamp parsing |
| `add_historical_comparison` | Insert historical comparison |
| `add_comparison` | Insert new comparison |
| `comparison_exists_for_pair` | Check existence |
| `clear_all_comparisons` | Delete all |
| `get_recent_comparisons` | Recent comparisons for a file |
| `get_comparison_count` | Count for a file |
| `get_total_comparisons` | Total count |
| `get_skipped_comparison_count` | Low-weight count |
| `get_all_comparisons` | All comparisons, optional weight filter |
| `get_images_with_only_wins` | Files that only won |
| `get_images_with_only_losses` | Files that only lost |
| `delete_comparisons_for_image` | Delete by image |
| `delete_comparison_by_id` | Delete by PK |
| `delete_comparison` | Delete by key fields |
| `clean_comparisons` | Clean/repair comparisons |

### `infrastructure/persistence/images_repository.py`

**New file** — extracted from `_ImageRepo` references in `crystal_graph.py` (currently missing)

| Function | From |
|---|---|
| `get_all_images()` | Referenced as `images_table.get_all_images` |
| `get_image(filename)` | Referenced as `images_table.get_image` |
| `add_image(...)` | Referenced as `images_table.add_image` |
| `update_image_rating_state(...)` | Referenced as `images_table.update_image_rating_state` |

---

## 6. Adapters Layer — `adapters/` (external interface code)

### `adapters/cli/main.py`

**Moved from** `scorer.py` (entry point logic) — the root `scorer.py` stays as `python -m` entry that imports this.

| Function | Role |
|---|---|
| `main()` | CLI logic (sys.path setup, argument parsing, orchestrating application services) |

### `adapters/comfyui/__init__.py`

**To be created** — must export `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` (referenced by root `__init__.py`).

### `adapters/comfyui/nodes/`

Currently empty. Future ComfyUI node definitions go here:
- `aesthetic_score/` — aesthetic scoring node
- `ranking/` — ranking UI/operations node
- `gallery/` — gallery display node
- `maps/` — map visualization node

### `adapters/` — frontend assets

All existing frontend directories (`analysis/frontend`, `comparison/frontend`, `data_transform/frontend`, `database_structure/frontend`, `gallery/frontend`, `maps/frontend`, `maps2/frontend`, `server/frontend`, `training_hyperparameters/frontend`) are correctly placed — **keep**.

---

## 7. Empty Directories — Summary of Repurposing

| Empty directory | Repurpose / Fill |
|---|---|
| `application/dto/` | Data transfer objects (for server API) |
| `application/ports/` | Application-level port interfaces (if needed) |
| `application/services/` | ← **CrystalGraph** (`graph_service.py`) |
| `infrastructure/external_services/` | External API clients (future) |
| `infrastructure/ml_models/` | ML model wrappers / inference code (future) |
| `infrastructure/persistence/` | ← **database.py**, **comparisons_repository.py**, **images_repository.py** |
| `core/utilities/` | ← **concurrency.py** (`parallel_batch`, `parallel_for`) |
| `nodes/aesthetic_score/` | ComfyUI aesthetic score node definition |
| `adapters/cli/commands/` | CLI sub-command implementations (future) |
| `adapters/comfyui/input_adapters/` | ComfyUI input type adapters (future) |
| `adapters/comfyui/output_adapters/` | ComfyUI output type adapters (future) |
| `adapters/comfyui/nodes/aesthetic_score/` | ComfyUI node definition |
| `adapters/comfyui/nodes/ranking/` | ComfyUI node definition |
| `adapters/comfyui/nodes/gallery/` | ComfyUI node definition |
| `adapters/comfyui/nodes/maps/` | ComfyUI node definition |
| `adapters/server/endpoints/` | Server API endpoint handlers |
| `adapters/server/routing/` | Route definitions |
| `adapters/server/middleware/` | Server middleware |
| `adapters/server/tests/` | Server tests |
| `domain/analysis/tests/` | Analysis domain tests (when domain/analysis/ is populated) |
| `domain/comparison/tests/` | Comparison domain tests (when domain/comparison/ is populated) |
| `domain/data_transformation/` | Data normalization/transformation logic |
| `domain/database/tests/` | Database port tests |
| `domain/loading/tests/` | Loading tests (when domain/loading/ is populated) |
| `domain/training/` | Training domain logic |
| `nodes/` (root) | **Remove** — redundant; ComfyUI nodes live in `adapters/comfyui/nodes/` |

---

## 8. Move Summary

| Current path | New path | Action |
|---|---|---|
| `scorer.py` | stays at root (add `adapters/cli/main.py` as target) | Update import |
| `core/io/serialization.py` `(parallel_batch, parallel_for)` | `core/utilities/concurrency.py` | Extract and move |
| `domain/database/schema.py` | `infrastructure/persistence/database.py` | Move file |
| `domain/database/comparisons_table.py` | `infrastructure/persistence/comparisons_repository.py` | Move + merge `_ComparisonRepo` |
| `domain/graph/crystal_graph.py` `(CrystalGraph)` | `application/services/graph_service.py` | Move file |
| `domain/graph/crystal_graph.py` `(_ImageRepo)` | `infrastructure/persistence/images_repository.py` | Extract |
| `domain/graph/crystal_graph.py` `(_ComparisonRepo)` | `infrastructure/persistence/comparisons_repository.py` | Merge |
| `domain/graph/crystal_graph.py` `(global instance + auto-rebuild)` | Remove — callers create explicitly | Delete |
| *(missing)* | `adapters/comfyui/__init__.py` | Create with node mappings |
| *(missing)* | `infrastructure/persistence/images_repository.py` | Create from `_ImageRepo` references |

### Import updates required

After moves, update these files' imports:

| File | Old import → New import |
|---|---|
| `__init__.py` | (no change — already imports `adapters.comfyui`) |
| `application/services/graph_service.py` (ex-`crystal_graph.py`) | `domain.database.ports` → **keep**; `domain.database.comparisons_table` → `infrastructure.persistence.comparisons_repository`; `domain.database.images_table` → `infrastructure.persistence.images_repository` |
| `domain/graph/chain_manager.py` | (no change — no external deps beyond graph siblings) |
| Any file importing from `domain.database.schema` | → `infrastructure.persistence.database` |
| Any file importing from `domain.database.comparisons_table` | → `infrastructure.persistence.comparisons_repository` |
