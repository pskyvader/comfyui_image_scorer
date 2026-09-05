# Reorganization Plan — `comfyui_image_scorer` (v8)

## 0. Ground Rules & Non-Negotiables

1. **Environment**: Every command runs in the ComfyUI venv (`& "E:\ComfyUI\.venv\Scripts\Activate.ps1"` first).
2. **Imports**: Relative imports at module scope, at top of file. No inline imports (except lazy parser dispatch in `adapters/cli/main.py`).
3. **Typing**: Pyright strict mode (`pyrightconfig.json`). Zero `Any` in protocols and domain interfaces. Strive for complete elimination of `Any`.
4. **Error Handling**: No error-swallowing `try`/`except`. Fail fast with explicit errors. Permitted forms only: finally-only cleanup, translate-and-reraise, and GPU OOM-adaptive batching.
5. **No Mutable Global State**: No global stores in `core`, `domain`, or `application`. State lives in `adapters` or `infrastructure`.
6. **Layer Boundary Rules**: Inward dependencies only: `core → domain → application → adapters → infrastructure`. Nothing imports `infrastructure` except the three composition roots (`adapters/server/main.py`, `adapters/cli/deps.py`, `adapters/comfyui/services.py`).
7. **No Default Arguments / No Optional Sentinels**: Every required value is passed explicitly at every call site. No default arguments for configuration objects or functions.
8. **No Internet Requests**: Offline runtime loading. The only download path is user-initiated via `files download models`.
9. **Single Database**: Sole supported database filename is `cache.db`. Automatic deletion or automatic rebuilds are strictly prohibited.
10. **Single Graph & Database Facade**: `CrystalGraph` is the sole boundary for graph and database operations. Callers use node/link/proxy vocabulary (`NodeProxy`, `LinkProxy`, `ChainProxy`, `ComponentProxy`). No caller outside `CrystalGraph` imports or accesses repositories or database tables.
11. **Ports Are Pure Interfaces**: Ports define abstract `Protocol` classes only. No concrete implementations, no filesystem I/O, no DB calls, and no plotting occur inside ports.

---

## 1. Task Inventory

### Group A: Domain Ports Consolidation & Typing Hardening (Zero `Any`)

- [x] **TASK-01: Create canonical `domain/ports/graph.py` with zero `Any`** ✅ COMPLETED
  - Define `CrystalGraphPort` (or `GraphFacadePort`) abstracting all graph read and write methods.
  - Return types must be concrete proxies (`NodeProxy | None`, `list[NodeProxy]`, `LinkProxy`, `list[LinkProxy]`, `ChainProxy`, `list[ChainProxy]`, `ComponentProxy | None`, `list[ComponentProxy]`).
  - Eliminate all `Any` return types and parameter types.
  - Ensure `CrystalGraph` in `application/services/graph_service.py` satisfies this protocol exactly.

- [x] **TASK-02: Migrate algorithm protocols to `domain/ports/graph.py`** ✅ COMPLETED
  - Delete local `CrystalGraph` protocol in `domain/comparison/algorithm/pair_active.py` and import `domain/ports/graph.py`.
  - Delete local `CrystalGraph` protocol in `domain/comparison/algorithm/merge_sort_ranker.py` and import `domain/ports/graph.py`.
  - Delete local `CrystalGraph` protocol in `domain/comparison/algorithm/graph_helpers.py` and import `domain/ports/graph.py`.
  - Replace `cg: Any` in `domain/comparison/algorithm/view.py` with `CrystalGraphPort`.

- [ ] **TASK-03: Move and strictly type graph write contract in `domain/ports/graph.py`** ⚠️ PARTIAL
  - `CrystalGraphPort` in `domain/ports/graph.py` exposes write methods with concrete return types. ✅
  - `comparison_recorder.py` still uses a bare `GraphService` annotation (line 43) that is never imported or defined — the type is a phantom. Must be replaced with `CrystalGraphPort`. ❌

- [x] **TASK-04: Consolidate repository ports into `domain/ports/repository.py`** ✅ COMPLETED
  - `domain/ports/repository.py` exists with `ImageRepository`, `ComparisonRepository`, `PathResolver` protocols.
  - `domain/database/ports/` directory deleted.

- [x] **TASK-05: Consolidate filesystem port into `domain/ports/files.py`** ✅ COMPLETED
  - `domain/ports/files.py` exists; `domain/files/ports.py` deleted.
  - `sync_metadata` uses explicit typed parameters (no `Any`).

- [x] **TASK-06: Consolidate loading ports into `domain/ports/loading.py`** ✅ COMPLETED
  - `domain/ports/loading.py` exists; `domain/loading/ports.py` deleted.
  - `domain/loading/__init__.py` re-exports from the new location.

- [x] **TASK-07: Consolidate cache and ML provider ports under `domain/ports/`** ✅ COMPLETED
  - `domain/ports/cache.py` (`CacheProvider`) and `domain/ports/ml_providers.py` (`MediaPipePort`, `VisionEncodingPort`, `FeatureEnginePort`) both exist.
  - `domain/database/ports/`, `domain/files/ports.py`, `domain/loading/ports.py` all deleted.

### Group B: Graph Facade & Proxy Encapsulation

- [ ] **TASK-08: Enforce graph proxy construction ownership** ⚠️ PARTIAL
  - No external callers (adapters, CLI, endpoints) instantiate proxies directly — all receive them from `CrystalGraph` methods. ✅
  - `NodeProxy`, `LinkProxy`, `ChainProxy`, `ComponentProxy` constructors are still named publicly (not `_NodeProxy`). The "private constructor pattern" rename is not done. ❌

- [ ] **TASK-09: Complete `CrystalGraph` proxy API migration** ⚠️ PARTIAL
  - `get_all_nodes()`, `get_node()`, `get_node_count()`, `get_all_links()`, `get_link_count()`, `get_winner_only_nodes()`, `get_loser_only_nodes()`, `link_exists_between()`, `get_all_chains()`, `get_all_components()` all implemented. ✅
  - Legacy methods still present on `CrystalGraph`: `get_nodes_with_only_wins()`, `get_nodes_with_only_losses()`, `get_total_comparisons()` (via repo facade) and `add_historical_comparison()`. Must be deleted. ❌

- [x] **TASK-10: Complete write-through persistence synchronization in `CrystalGraph`** ✅ COMPLETED
  - `add_link()` persists to `ComparisonRepository` then atomically applies to chain topology and in-memory history.
  - Repository failure raises before in-memory state is mutated.

- [x] **TASK-11: Sanitize residual comparison `weight` in `pair_data.py`** ✅ COMPLETED
  - `comp.get("weight", 1.0)` removed; `pair_data.py` now hard-codes `1.0` directly without reading from comparison dicts.

### Group C: Architecture & Directory Layout Alignment

- [x] **TASK-12: Inline `application/data_transform/config/maps.py`** ✅ COMPLETED
  - `register_map_values()` is defined directly in `application/data_transform/prepare_data.py`.
  - `application/data_transform/config/` directory deleted.

- [x] **TASK-13: Move parameter analysis plotting to `infrastructure/ml_models/plot.py`** ✅ COMPLETED
  - `application/analysis/parameter_analysis.py` has no matplotlib/sklearn imports; only data calculation logic remains.
  - Rendering lives in `infrastructure/ml_models/plot.py`.

- [x] **TASK-14: Decouple `domain/analysis/attribute_analysis.py` from torchvision** ✅ COMPLETED
  - No `torchvision` import found in `domain/analysis/attribute_analysis.py`.

- [x] **TASK-15: Consolidate static frontends into `adapters/frontend/`** ✅ COMPLETED
  - All 9 feature frontend directories moved to `adapters/frontend/<feature>/`.
  - Shared shell frontend moved to `adapters/frontend/shared/`.
  - `adapters/server/main.py::SECTION_FRONTENDS` and `SERVER_FRONTEND` updated to point to `adapters/frontend/`.
  - Old `adapters/*/frontend/` directories deleted.

### Group D: Caller Migration & Vocabulary Elimination

- [ ] **TASK-16: Migrate `adapters/server/endpoints/` to proxy API** ⚠️ PARTIAL
  - Endpoints use proxy API (`get_node`, `get_node_count`, `get_all_links`) — no direct repository calls. ✅
  - `Any` still used in request/response type annotations in `comparison.py`, `gallery.py`, `maps.py`. ❌

- [x] **TASK-17: Migrate `application/services/image_processor.py` to graph and `FilePort`** ✅ COMPLETED
  - All file operations route through injected `FilePort`.
  - No direct repository access found; all graph interactions go through `CrystalGraph` node/link methods.

- [ ] **TASK-18: Migrate CLI commands and domain algorithms to node/link vocabulary** ⚠️ PARTIAL
  - Deprecated vocabulary `get_image`, `get_all_images`, `get_all_comparisons`, `add_comparison` not found in CLI. ✅
  - `clean_comparisons()` still called from `adapters/cli/commands/database.py::cleanup()` — this routes through `CrystalGraph` which wraps the repo, so it's not a raw repository call, but the method still exists on the facade and must be evaluated against TASK-09 cleanup. ❌ (depends on TASK-09 resolution)

### Group E: Typing Remediation & Gate Verification

- [ ] **TASK-19: Eradicate `Any` across domain and application layers** ❌ NOT DONE
  - `Any` still present in `adapters/server/endpoints/comparison.py`, `gallery.py`, `maps.py`.
  - `Any` used in `domain/comparison/algorithm/view.py` return types.
  - `Any` in `application/services/graph_service.py` (`_images: dict[str, dict[str, Any]]`, `_make_link`, `get_graph_stats`, `reset_all_image_ratings`, `clean_comparisons`).
  - `Any` in `infrastructure/ml_models/training/pair_data.py` (`dict[str, Any]`).

- [ ] **TASK-20: Drive Pyright Strict to <= 455 baseline** ❌ NOT DONE
  - Not yet run / not yet verified.

- [ ] **TASK-21: Full verification suite** ❌ NOT DONE
  - `pytest`, `ruff`, architecture tests, facade tests not yet confirmed passing.
  - ComfyUI `AestheticScore` node registration not yet verified.
