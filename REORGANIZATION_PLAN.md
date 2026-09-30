# Reorganization Plan

This roadmap covers the remaining implementation and documentation work for the image-scorer module. The rules, functionality description, and current structure are maintained separately; this file owns sequencing, dependencies, acceptance criteria, and remediation status.

Every task below includes **why** the work is required and **how** it must be implemented. Each implementation must preserve the architecture boundaries, ownership rules, and validation discipline owned by `AGENTS.md`, and must use the current paths and symbols in the structure index owned by `FUNCTION_INDEX.md`. After an implementation change, update the index to the new current state; do not pre-document the change in the index.

The documentation baseline is the module-local Git repository at commit
`5fc9cd0` (`just more changes`). The ComfyUI root repository is not the history source
for these files; its virtual environment is used only to run validation.

## Documentation tasks

- [x] **D-01 — Make the four documents independent.**
  - **Why:** duplicated or circular documentation causes agents to follow stale rules and makes current structure unclear.
  - **Rules/structure:** follow the document-ownership and one-way-reference constraints in `AGENTS.md`; use the four current document paths listed in `FUNCTION_INDEX.md`.
  - **How:** keep permanent rules only in `AGENTS.md`, functionality only in `README.md`, live inventory only in `FUNCTION_INDEX.md`, and roadmap work only here. Cross-references may identify the document that owns a fact, but no document may duplicate another document's rules, functionality, inventory, or roadmap status.

- [x] **D-02 — Complete the current structure index.**
   - **Why:** every implementation task needs an accurate path and symbol anchor; missing descriptions hide ownership and make edits speculative.
   - **Rules/structure:** follow the live-tree and current-state documentation rules in `AGENTS.md`; anchor entries to the paths currently listed by the repository structure in `FUNCTION_INDEX.md`.
   - **How:** enumerate every current package, test, configuration, frontend, documentation, and script file. Add concise file descriptions plus reliable public classes, protocols, functions, constants, node mappings, and CLI entry-point descriptions. Do not list planned or removed files.

- [x] **D-03 — Resolve missing index descriptions before finalization.**
  - **Why:** a blank description is an undocumented structure constraint and prevents agents from knowing what a file owns.
  - **Rules/structure:** follow the ownership, source-of-truth, and no-future-state rules in `AGENTS.md`; name the exact live path or symbol from `FUNCTION_INDEX.md`.
  - **How:** add each missing file or symbol here under “Index description tasks,” state the required explanation, then add that explanation to `FUNCTION_INDEX.md` before marking the task complete.

## Pending implementation tasks

- [x] **P-01 — Align port annotations.**
  - **Why:** inconsistent protocol shapes allow adapters and implementations to drift, violating the typed-boundary rule.
  - **Rules/structure:** follow strict typing, pure-port, inward-dependency, and ownership rules in `AGENTS.md`; edit the current port and facade paths recorded in `FUNCTION_INDEX.md`.
  - **How:** parameterize bare tuples/dicts in loading ports and reconcile graph port return types with the concrete facade; preserve behavior and validate with focused type and protocol checks.

- [x] **P-02 — Centralize comparison helpers.**
  - **Why:** pair canonicalization and timestamp ordering must have one owner to keep database cleanup and rebuild collapse deterministic.
  - **Rules/structure:** follow pure-core, dependency-direction, and single-owner rules in `AGENTS.md`; use the current comparison algorithm and persistence paths recorded in `FUNCTION_INDEX.md`.
  - **How:** move each helper only to the lowest layer that owns its concept, keeping domain comparison semantics in `domain` and infrastructure-specific persistence mechanics in `infrastructure`. Re-import the helpers from repository and ranking code without reversing the README dependency direction, and preserve sortable timestamp behavior with focused tests.

- [x] **P-03 — Complete the graph port contract.**
  - **Why:** callers currently rely on graph methods that the port does not declare, weakening dependency inversion and strict typing.
  - **Rules/structure:** follow protocol purity, graph-facade ownership, proxy vocabulary, and strict typing rules in `AGENTS.md`; reconcile the graph port, graph facade, and graph algorithm paths in `FUNCTION_INDEX.md`.
  - **How:** make the graph interface a protocol, add the actually-used graph operations, and resolve `add_comparison` versus `add_link`, graph-stat value types, and cleanup return types. Confirm the facade satisfies it.
  - **Dependency:** complete P-03 before P-04; update `FUNCTION_INDEX.md` only after the live protocol and facade have changed.

- [x] **P-04 — Return the touched comparison record.**
  - **Why:** reverse-searching mutable history after insertion is fragile and violates narrow ownership of the record being updated.
  - **Rules/structure:** follow narrow ownership, public-interface compatibility, and graph/database-boundary rules in `AGENTS.md`; change only the chain manager and graph facade paths identified in `FUNCTION_INDEX.md`.
  - **How:** have chain application return the created or updated record; stamp its database ID and timestamp directly in the graph facade without changing the public facade behavior. Keep persistence construction in the composition roots and pass repositories through the existing port.

- [x] **P-05 — Add one pure history-collapse operation.**
  - **Why:** two-sided JSON histories can duplicate or contradict comparisons; insertion order is nondeterministic and can change ratings.
  - **Rules/structure:** follow pure-domain, deterministic-data, graph-history, and test-isolation rules in `AGENTS.md`; place the operation beside the current comparison algorithm and repository consumers listed in `FUNCTION_INDEX.md`.
  - **How:** normalize candidates, sort by an explicit total order, apply the existing missing-node, self-link, same-direction, and contradiction rules, and return survivors plus counts. Reuse it from cleanup and test each rule.
  - **Dependency:** complete P-05 before P-06; keep the collapse operation in the domain-owned comparison layer and leave SQLite access in infrastructure.

- [x] **P-06 — Rebuild history through collapse.**
  - **Why:** inserting every historical row and cleaning afterward causes a second graph rebuild and obscures the intended survivor ordering.
  - **Rules/structure:** follow explicit database lifecycle, graph-facade, filesystem ownership, and deterministic replay rules in `AGENTS.md`; use the current image processor, graph facade, and persistence paths in `FUNCTION_INDEX.md`.
  - **How:** collect validated candidates, skip self-links explicitly, collapse once, insert survivors through `add_link`, rebuild only at the required seed point, replay ratings, and synchronize JSON in survivor order. *(Status: complete — candidate collection, self-link skipping, `collapse_comparison_history` call, survivor `add_link` insertion, and survivor-order JSON sync are implemented in `application/services/image_processor.py`; the redundant `clean_comparisons()` call after collapse is removed and the `rebuild_from_database()` seed point after survivor insertion is retained because only `ChainManager.build()` rebuilds chains. Focused coverage: `tests/test_graph_facade.py`, `tests/test_graph_helpers.py`, `domain/graph/tests/test_chain_manager.py`).*
  - **Dependency:** P-06 depends on P-03 through P-05. Preserve `CrystalGraph` as the application boundary and use injected repository ports rather than importing infrastructure from the image processor or domain.

- [x] **P-07 — Remove historical-comparison insertion.**
  - **Why:** after P-06, the legacy insertion path duplicates graph/database ownership and leaves an obsolete API surface.
  - **Rules/structure:** follow dead-code removal, graph/database-facade, and compatibility rules in `AGENTS.md`; verify all current callers and update the affected paths in `FUNCTION_INDEX.md`.
  - **How:** verify zero callers, then remove only `add_historical_comparison` from its callers, the repository implementation, the `ComparisonRepository` protocol, and any obsolete facade forwarding method. Preserve `CrystalGraph`, `CrystalGraph.add_link`, graph proxy factories, repository ports, node/CLI behavior, and workflow compatibility. Update the live index afterward.
  - **Dependency:** P-07 depends on P-06 and zero-caller verification. It must not remove or bypass the `CrystalGraph` application boundary.

- [x] **P-08 — Decide the filesystem boundary.**
  - **Why:** direct filesystem operations in the image processor can bypass the filesystem port and violate infrastructure ownership.
  - **Rules/structure:** follow infrastructure ownership, port purity, and narrow-boundary rules in `AGENTS.md`; inspect the image processor, filesystem port, and file manager paths recorded in `FUNCTION_INDEX.md`.
  - **How:** route persistence and synchronization operations through the narrow filesystem port where that port owns them; explicitly document any image-discovery or movement operations retained by the application. Keep `FileManager` construction in the three approved adapter composition roots, and do not import infrastructure into `ImageProcessor`. Test both delegated and intentionally owned behavior. *(Status: complete — `FilePort` is injected into `ImageProcessor` via constructor and all three adapter composition roots construct it; `FUNCTION_INDEX.md` now lists each retained operation (`get_fast_total_count`, `process_next_batch`, `reorganize_folder_structure`, `process_image_file`, `rebuild_database_from_ranked`) against the delegated `FilePort` surface; `tests/test_image_processor.py` covers both delegated and intentionally owned behavior).*

- [x] **P-09 — Replace shared row and payload `Any` types.**
  - **Why:** untyped rows leak infrastructure details and prevent strict domain contracts from catching shape errors.
  - **Rules/structure:** follow strict typing, boundary ownership, and no-bare-container rules in `AGENTS.md`; trace types through the proxy, service, endpoint, and repository paths listed in `FUNCTION_INDEX.md`.
  - **How:** define narrow row/payload types at the owning boundary and thread them outward from proxy data through services and endpoints without using bare dicts as a shortcut. *(Status: complete — `ImageRow`/`ComparisonRow` in `domain/ports/repository.py` and the config payload shapes (`VectorEntry`, `ImageVectorEntry`, `VisionModelConfig`, `EmbeddingModelConfig`, `AttributeModelConfig`) in `core/configuration/settings.py` are the owning boundary; the feature-mapping and interaction-statistic payloads in `domain/data_transformation/data_transformer.py` and the HPO state payload in `application/hyperparameters/hyperparameter_optimizer.py` are defined beside their producers. These are threaded through the graph facade, image processor, scoring service, comparison recorder, training loader, endpoints, and composition roots without bare dicts.)*

- [x] **P-10 — Finish the strict type-check cleanup.**
  - **Why:** remaining diagnostics obscure real interface errors and contradict the typed architecture rule.
  - **Rules/structure:** follow strict typing, model/device correctness, and minimal-change rules in `AGENTS.md`; work only in the current infrastructure, transformation, and optimizer paths named in `FUNCTION_INDEX.md`.
  - **How:** fix the known infrastructure, transformation, and optimizer diagnostics after P-09, checking that no touched file regresses. *(Status: complete — module-wide `pyright` is 246 errors, down from a 945 baseline. Every real interface error in the named infrastructure, transformation, and optimizer paths is fixed; the residual count is `reportUnknown*` leaking from third-party packages that ship no `py.typed` or incomplete stubs (`sklearn`, `scipy`, `comfy.model_management`, `timm`, `transformers`, `huggingface_hub`, `safetensors`, `torch.cuda`). Notable changes: `GridCell` in `domain/training/grid.py`; `ScoringModel`, `FeatureFilterModel`, and `ModelTrainingService` replacing the empty `_ModelTrainer` in `domain/ports/loading.py`; typed `DataTransformer` dependencies; the `HpoState` payload; `ModelInfo`-keyed model info cache; dead `is None` and `hasattr` branches removed; the infrastructure→application import of `ModelTrainer` in `scoring_service.py` replaced by the domain port. `domain/training/grid.py`, `domain/ports/loading.py`, `application/hyperparameters/hyperparameter_optimizer.py`, `application/services/scoring_service.py`, `core/configuration/settings.py`, and `adapters/comfyui/services.py` are at zero.)*

- [x] **P-11 — Remove the test-only filesystem bypass and validate.**
  - **Why:** leaving the bypass disables destructive operations in the real workflow and means the tested path differs from production behavior.
  - **Rules/structure:** follow explicit destructive-operation, test-isolation, validation-order, and node-registration rules in `AGENTS.md`; validate the image processor, tests, and registration paths represented in `FUNCTION_INDEX.md`.
  - **How:** first grep the codebase for the bypass flag or monkeypatch (search `image_processor` tests and any `conftest.py` for skip/bypass of move/delete operations); if absent, the bypass was already removed and this task closes after a focused test run confirms destructive operations execute. If found, remove the bypass only after focused tests pass, then run lint, typing, architecture, registration, full non-real-data tests, and user-run real-data equivalence checks. *(Status: complete — grep found no bypass flag, no `conftest.py`, and no `monkeypatch` in the image-processor tests. `tests/test_image_processor.py` covers the retained-versus-delegated filesystem operations with a temporary-directory `TempFilePort` fake, so the destructive paths run under test. Full validation on 2026-09-24: `python -m pytest -q` → 76 passed, 1 deselected; `ruff check --select ARG,F401 --target-version py313 .` → clean except the pre-existing `domain/comparison/algorithm/pair_active.py` F401, which is unrelated user WIP; `pyright` → 246 errors (baseline 945); `pytest tests/test_architecture.py -v` → 3 passed; node registration smoke check → `['AestheticScore']`.)*

- [x] **P-12 — Remove legacy compatibility modules.**
  - **Why:** dead compatibility layers (`domain/database/`, `domain/graph/_init.py`, `domain/graph/_/_init.py`) violate the "remove obsolete code aggressively" rule in `AGENTS.md`; they have zero imports in the current tree.
  - **Rules/structure:** follow dead-code removal and single-owner rules in `AGENTS.md`; verify zero references via grep before deletion.
  - **How:** delete `domain/database/__init__.py`, `domain/graph/_init.py`, `domain/graph/_/_init__.py`; update `FUNCTION_INDEX.md` to remove their entries. *(Status: complete - all three paths are gone from the live tree, grep finds no imports of them, and no FUNCTION_INDEX.md entry references them.)*

- [x] **P-13 — Remove empty frontend adapter packages.**
  - **Why:** `adapters/maps/`, `gallery/`, `comparison/`, `build/`, `analyze/`, `database/`, `training/` contain only empty `__init__.py` files; they are not imported by any Python code (server serves static folders directly). (`adapters/maps2/` and `adapters/maps3/` were already removed when the maps2/maps3 frontends were consolidated into `adapters/frontend/maps/`.)
  - **Rules/structure:** follow dead-code removal and minimal-dependency rules in `AGENTS.md`.
  - **How:** delete the seven empty adapter directories; keep `adapters/frontend/` static assets and `adapters/server/endpoints/maps.py` (the only registered maps API). Update `FUNCTION_INDEX.md`.

- [x] **P-14 — Run architecture boundary tests.**
  - **Why:** `AGENTS.md` validation step 4 requires `tests/test_architecture.py` (layer-import, database-boundary, proxy-construction gates) to pass; no explicit plan task covers this.
  - **Rules/structure:** follow architecture ownership and dependency-direction rules in `AGENTS.md`.
  - **How:** execute `pytest tests/test_architecture.py -v` in the ComfyUI virtual environment; confirm all layer-import and boundary tests pass. *(Verified: 3/3 passed).*

- [x] **P-15 — Verify ComfyUI node registration.**
  - **Why:** `AGENTS.md` validation step 5 requires the node-registration smoke check (`AestheticScore` in `NODE_CLASS_MAPPINGS`); no explicit plan task covers this.
  - **Rules/structure:** follow node-registration and workflow-compatibility rules in `AGENTS.md`.
  - **How:** run the smoke check from `AGENTS.md`:
    ```powershell
    python -c "import sys; sys.path.insert(0, '..'); from comfyui_image_scorer.adapters.comfyui.node_registry import NODE_CLASS_MAPPINGS; assert 'AestheticScore' in NODE_CLASS_MAPPINGS; print(list(NODE_CLASS_MAPPINGS))"
    ```
    *(Verified: `['AestheticScore']` registered successfully).*

- [x] **P-16 — Integrate Models with ComfyUI Memory Management.**
  - **Why:** Current `ModelLoader` loads models directly with `.to(device)` and maintains manual caches, bypassing ComfyUI's VRAM management, offloading, and device handling (`--cpu`, `--lowvram`, `--gpu-only`, MPS, DirectML). This causes OOM risk and hardcoded CUDA dependencies.
  - **Rules/structure:** Follow architecture boundaries (`infrastructure` implements domain ports; `domain` must not import `comfy` or manage GPU memory), strict typing (no `Any` or bare `object` in protocols), dtype/device/VRAM correctness, no `torch.no_grad()` or `torch.inference_mode()` in inference code, preserve offline loading, no internet requests.
  - **How:** In `infrastructure/ml_models/model_loader.py`, wrap models with `ModelPatcher` / `CoreModelPatcher` and encapsulate `comfy.model_management.load_model_gpu` inside infrastructure callable wrappers (`ComfyVisionModel`, `ComfyEmbeddingModel`, `ComfyAttributeModel`). Keep `domain/ports/loading.py` purely protocol-based (`VisionModel`, `EmbeddingModel`) without importing `comfy`. Update callers in `domain/` to call the wrapped models directly without context managers or manual GPU loading calls. Explicitly refer to and follow the draft implementation design in [Appendix: P-16 Implementation Specification (Draft)](#appendix-p-16-implementation-specification-draft).
  - **Dependency:** Complete P-09 and P-10 (strict typing cleanup) first; update `FUNCTION_INDEX.md` after implementation.
  - *(Status: complete — `infrastructure/ml_models/model_loader.py` wraps every vision, embedding, and attribute model in a `ModelPatcher` built from `comfy.model_management.text_encoder_device()` / `text_encoder_offload_device()`, and `ComfyVisionModel`/`ComfyEmbeddingModel`/`ComfyAttributeModel` call `load_model_gpu` on every invocation. The hardcoded `device != "cuda"` guards, the manual `model.to(device)` calls, the manual HF model lock, and every `torch.no_grad()`/`torch.inference_mode()` in the inference paths are removed. `domain/ports/loading.py` stays protocol-only: `VisionModel`, `EmbeddingModel`, `AttributeModel`, `Transform`, `BatchTensors`, and `ImageProcessor` describe the callable surfaces domain code uses, and the former underscore-prefixed protocols were renamed because they are now cross-module public contracts. `infrastructure/ml_models/batch_sizer.py` profiles through `load_vision_model_patcher()` and returns a conservative size of 1 on non-CUDA devices. Because ComfyUI only puts its own root on `sys.path` when it loads custom nodes, the package `__init__.py` adds the host ComfyUI root before importing the node registry, so the standalone CLI, the test suite, and the documented registration smoke check all keep working. Verified 2026-09-24: 76 tests pass, architecture tests pass, registration smoke check returns `['AestheticScore']`, and `python scorer.py --help` runs. The real-model `python scorer.py build all --limit 10` check still requires a user run against a downloaded model set.)*

- [x] **P-17 — Make a rebuild fast and reproducible.**
  - **Why:** A rebuild took 720 s and rewrote all 30,471 companion JSON files on every run. Two independent causes: one database connection and transaction per row (about 162,000 of them), and a non-deterministic replay order that made every rating differ in its sixth decimal.
  - **How:** Add chunked bulk writes behind the existing graph and repository ports (`add_comparisons_bulk`, `add_images_bulk`, `update_image_rating_states_bulk`, chunked by `DB_BULK_CHUNK`), used by both the rebuild and `database recalculate`. Remove `comparison_id` from companion JSON. Return results in input order from `discover_files`, `collect_valid_files`, and `parallel_for`. Replay in stored link order.
  - *(Status: complete — verified 2026-09-29. An isolated benchmark on the live 101,441-row table showed the per-row insert was 99.6% of the survivor step (467 s against 1.79 s of in-memory graph work), so the bulk write is the whole win and the graph keeps its existing per-row apply semantics. Measured on the real 30,471-image tree: the survivor step fell from 105 s to 14 s, image inserts from 22 s to 3 s, rating updates from 30 s to 3 s, and the run reached **75 s against the original 720 s**. The metadata write guard now converges: a second consecutive rebuild wrote **0** files and skipped all 30,471, where before it rewrote roughly 27,000 every run. `ruff --select SLF001` is clean, and the six CLI parser builders were made public because the structural-parity test is their only external consumer and no public alternative exists. Verified: 99 tests pass and 1 deselected, architecture tests pass, registration returns `['AestheticScore']`, pyright holds at the 247 baseline, and ruff reports only the pre-existing `stable_seed_pool` F401.)*

## Required rebuild invariants
- Database and in-memory graph history remain synchronized.- Companion JSON history carries no database identifiers. `comparison_id` was removed because the database is cleared and repopulated on every rebuild, which left it pointing at rows that no longer existed. Training and NPZ consumers read the `id` field instead.
- Collapse uses an explicit deterministic total order independent of file discovery completion order.
- File discovery, `collect_valid_files`, and `parallel_for` all return input order so a rebuild of unchanged files is bit-identical and the JSON write guard converges.
- Replayed ratings and per-file histories are exactly equal across runs of unchanged input, not merely equivalent.
- The ranking loop's LRU-overflow chain-cover refresh remains intact.
- Focused coverage includes duplicate two-sided histories, contradictions, self-links, missing nodes, equal timestamps, ID uniqueness, and JSON sync.

## Validation

For every task, follow the agent rulebook's narrow-to-broad validation order. From the module root, use the configured non-real-data pytest suite as appropriate, then `ruff check --select ARG,F401 --target-version py313 .`, `pyright`, architecture/database/proxy tests, and the node-registration smoke check. Record the command, date, and result for any baseline. Run real-data tests only by explicit request because they are destructive. Documentation work is complete only when the four documents preserve their ownership boundaries, the index describes only the live tree, and every missing description has first been recorded as a task here.

## Index description tasks

Add one entry here before finalizing the index for every file or public symbol that lacks a useful description. Each entry must name the path or symbol and state the ownership or behavior the index description must explain.

---

## Appendix: P-16 Implementation Specification (Draft)

This appendix preserves the draft technical design and code specifications for task **P-16** (Integrate Models with ComfyUI Memory Management).

- **Why:** Current `ModelLoader` loads models directly with `.to(device)` and maintains manual caches, bypassing ComfyUI's VRAM management, offloading, and device handling (`--cpu`, `--lowvram`, `--gpu-only`, MPS, DirectML). This causes OOM risk, no automatic offloading, and hardcoded CUDA dependency.
- **Rules/structure:** Follow architecture boundaries (`infrastructure` implements domain ports; `domain` must not import `comfy` or manage GPU memory), strict typing (no `Any` in protocols), dtype/device/VRAM correctness, use ComfyUI optimized ops (`load_model_gpu`, `get_free_memory`), preserve offline loading, no internet requests, no `torch.no_grad()` or `torch.inference_mode()` in inference paths. Update `FUNCTION_INDEX.md` after implementation.
- **How:** In `infrastructure/ml_models/model_loader.py`, wrap models with `ModelPatcher` / `CoreModelPatcher` and encapsulate `comfy.model_management.load_model_gpu` inside infrastructure callable wrappers (`ComfyVisionModel`, `ComfyEmbeddingModel`, `ComfyAttributeModel`). Keep `domain/ports/loading.py` purely protocol-based (`_VisionModel`, `_EmbeddingModel`) without importing `comfy`. Update callers in `domain/` to call the wrapped models directly without context managers or manual GPU loading calls.

### Files to Modify

| File | Change Type |
|------|-------------|
| `domain/ports/loading.py` | Protocol update (pure `_VisionModel`, `_EmbeddingModel`, `_AttributeModel` protocols) |
| `infrastructure/ml_models/model_loader.py` | Core implementation & ComfyUI wrappers |
| `infrastructure/ml_models/batch_sizer.py` | Device-aware profiling (Option 1) |
| `domain/vectors/image_vector.py` | Caller update (direct execution, no `torch.no_grad`) |
| `domain/vectors/embedding_vector.py` | Caller update (direct execution) |
| `domain/analysis/image_analysis.py` | Caller update |
| `domain/analysis/attribute_analysis.py` | Caller update (direct execution, no `torch.no_grad`) |

---

### 1. Protocol Change (`domain/ports/loading.py`)

```python
"""Port interfaces for loading-related services.

Moved from ``domain/loading/ports.py``. These protocols describe the surface
expected by domain and application code so infrastructure implementations can be
injected at adapter roots. All types are concrete — no ``Any``, no ComfyUI imports.
"""

from __future__ import annotations

from typing import Callable, Protocol, NamedTuple
import numpy as np
import numpy.typing as npt
import torch


class ModelInfo(NamedTuple):
    variable_input: bool
    input_size: tuple[int, int]


class _VisionModel(Protocol):
    """Abstract interface for vision model objects."""
    def __call__(self, x: torch.Tensor) -> torch.Tensor: ...
    @property
    def device(self) -> torch.device: ...


class _Transform(Protocol):
    """Abstract interface for image transform pipelines."""


class _EmbeddingModel(Protocol):
    """Abstract interface for embedding model objects."""
    def encode(self, sentences: list[str]) -> npt.NDArray[np.float32]: ...


class _AttributeModel(Protocol):
    """Abstract interface for attribute model objects."""
    def __call__(self, **kwargs: torch.Tensor) -> dict[str, torch.Tensor]: ...
    @property
    def device(self) -> torch.device: ...


class _ModelTrainer(Protocol):
    """Abstract interface for trained model objects."""


class VisionModelResult(NamedTuple):
    output_dim: int
    total_memory: int


class EmbeddingModelResult(NamedTuple):
    output_dim: int


class CategoryValue(NamedTuple):
    c: int
    value: int


class ModelLoader(Protocol):
    def load_vision_model(self, model_key: str) -> tuple[_VisionModel, int, int, _Transform]: ...
    def get_model_info(self, model_key: str) -> ModelInfo: ...
    def load_embedding_model(self) -> tuple[_EmbeddingModel, int]: ...
    def load_hf_vision_model(self, model_key: str) -> tuple[_AttributeModel, int, object]: ...


class BatchSizer(Protocol):
    def get(
        self,
        width: int,
        height: int,
        rebuild: bool,
        bound: int | None,
    ) -> int: ...


BatchSizerFactory = Callable[[str], BatchSizer]


class MapsProvider(Protocol):
    def get_value(self, name: str, value: str) -> CategoryValue: ...
    def add_value(self, name: str, value: str) -> CategoryValue: ...
    def get_all_categories(self, name: str) -> list[str]: ...
    def register_value(self, name: str, value: object) -> None: ...


class TrainingDiagnostics(NamedTuple):
    """Diagnostics returned by the training model loader."""
    final_score: float | None = None
    pairwise_accuracy: float | None = None
    score_calibration: dict[str, float] | None = None


class TrainingLoader(Protocol):
    def load_vectors(self) -> dict[str, float]: ...
    def load_scores(self) -> dict[str, float]: ...
    def load_training_model(self) -> _ModelTrainer: ...
    def load_training_model_diagnostics(self) -> TrainingDiagnostics | None: ...
```

---

### 2. Model Loader Implementation (`infrastructure/ml_models/model_loader.py`)

#### ComfyUI Infrastructure Wrappers
These wrappers encapsulate `ModelPatcher` and `comfy.model_management.load_model_gpu` inside infrastructure so domain code stays 100% pure without importing `comfy`.

```python
import comfy.model_management
from comfy.model_patcher import ModelPatcher


class ComfyVisionModel:
    """Infrastructure wrapper satisfying domain._VisionModel with ComfyUI VRAM management."""
    def __init__(self, patcher: ModelPatcher) -> None:
        self.patcher = patcher

    @property
    def device(self) -> torch.device:
        return self.patcher.load_device

    def __call__(self, x: torch.Tensor) -> torch.Tensor:
        comfy.model_management.load_model_gpu(self.patcher)
        return self.patcher.model(x)


class ComfyEmbeddingModel:
    """Infrastructure wrapper satisfying domain._EmbeddingModel with ComfyUI VRAM management."""
    def __init__(self, patcher: ModelPatcher) -> None:
        self.patcher = patcher

    def encode(self, sentences: list[str]) -> npt.NDArray[np.float32]:
        comfy.model_management.load_model_gpu(self.patcher)
        return self.patcher.model.encode(sentences, convert_to_numpy=True)  # type: ignore[return-value]


class ComfyAttributeModel:
    """Infrastructure wrapper satisfying domain._AttributeModel with ComfyUI VRAM management."""
    def __init__(self, patcher: ModelPatcher) -> None:
        self.patcher = patcher

    @property
    def device(self) -> torch.device:
        return self.patcher.load_device

    def __call__(self, **kwargs: torch.Tensor) -> dict[str, torch.Tensor]:
        comfy.model_management.load_model_gpu(self.patcher)
        return self.patcher.model(**kwargs)  # type: ignore[return-value]
```

> **Note:** `CoreModelPatcher` is a runtime alias for `ModelPatcher` in this ComfyUI version (`CoreModelPatcher is ModelPatcher` evaluates to `True`). Use `ModelPatcher` throughout; do not import `CoreModelPatcher`.

#### Device Selection (all PyTorch models)
```python
load_device = comfy.model_management.text_encoder_device()
offload_device = comfy.model_management.text_encoder_offload_device()
```

#### Vision Models (timm) — `load_vision_model`
```python
def load_vision_model(self, model_key: str) -> tuple[ComfyVisionModel, int, int, Compose]:
    cached = self.vision_model_cache.get(model_key)
    if cached is not None:
        return cached

    vision_models: dict[str, dict[str, object]] = self.prepare_config["vision_models"]
    if model_key not in vision_models:
        raise KeyError(
            f"Vision model key '{model_key}' not found in prepare_config. "
            f"Available: {list(vision_models.keys())}"
        )

    model_config = vision_models[model_key]
    name: str = model_config["name"]
    output_dim: int = model_config["output_dim"]
    variable_input: bool = model_config["variable_input"]
    global_pool: str = model_config["global_pool"]

    logger.info("Loading Vision Model (%s): %s...", model_key, name)

    try:
        model: nn.Module = timm.create_model(
            name,
            pretrained=True,
            num_classes=0,
            global_pool=global_pool,
        )
    except OSError as e:
        raise _missing_model_error(f"Vision model '{name}'") from e

    model = model.eval()

    # Create patcher - model starts on offload_device (CPU by default)
    load_device = comfy.model_management.text_encoder_device()
    offload_device = comfy.model_management.text_encoder_offload_device()
    # ModelPatcher(model, load_device, offload_device, size=0) — args are positional.
    patcher = ModelPatcher(model, load_device, offload_device)

    # Total memory for return value (same as before for batch sizer compatibility).
    # comfy.system_memory.virtual_memory_total() returns cgroup-aware RAM total on Linux,
    # psutil.virtual_memory().total on Windows/Mac — correct for non-CUDA devices.
    if load_device.type == "cuda":
        props = torch.cuda.get_device_properties(load_device)
        total_memory = int(props.total_memory)
    else:
        import comfy.system_memory
        total_memory = comfy.system_memory.virtual_memory_total()

    data_config = timm.data.resolve_model_data_config(model)
    input_size = data_config["input_size"]
    model_input_size = (input_size[2], input_size[1])

    transform = self._select_transform(name)
    if not variable_input:
        transform = transforms.Compose(
            [
                transforms.Resize(model_input_size),
                transform,
            ]
        )

    wrapped_model = ComfyVisionModel(patcher)
    result = (wrapped_model, output_dim, total_memory, transform)
    self.vision_model_cache[model_key] = result
    self._model_info_cache[model_key] = {
        "variable_input": variable_input,
        "input_size": model_input_size,
    }
    return result
```

#### Embedding Model (SentenceTransformer) — `load_embedding_model`
```python
def load_embedding_model(self) -> tuple[ComfyEmbeddingModel, int]:
    if self.embedding_model is not None:
        return self.embedding_model

    embedding_config = self.prepare_config["prompt_representation"]
    name: str = embedding_config["name"]
    output_dim: int = embedding_config["output_dim"]

    load_device = comfy.model_management.text_encoder_device()
    offload_device = comfy.model_management.text_encoder_offload_device()

    try:
        # Load SentenceTransformer on CPU initially; patcher moves it to load_device on demand.
        st_model = SentenceTransformer(
            name, device="cpu", local_files_only=not self.download_mode
        )
    except OSError as e:
        raise _missing_model_error(f"Embedding model '{name}'") from e

    # ModelPatcher(model, load_device, offload_device, size=0) — args are positional.
    patcher = ModelPatcher(st_model, load_device, offload_device)
    wrapped_model = ComfyEmbeddingModel(patcher)

    self.embedding_model = (wrapped_model, output_dim)
    return self.embedding_model
```

#### HF Attribute Models — `_load_hf_vision_model_impl`
```python
def _load_hf_vision_model_impl(
    self, model_key: str
) -> tuple[ComfyAttributeModel, int, object]:
    attribute_models: dict[str, dict[str, object]] = self.prepare_config["attribute_models"]
    if model_key not in attribute_models:
        raise KeyError(
            f"Attribute model key '{model_key}' not found in prepare_config. "
            f"Available: {list(attribute_models.keys())}"
        )

    model_config = attribute_models[model_key]
    name: str = model_config["name"]
    output_dim: int = model_config["output_dim"]

    load_device = comfy.model_management.text_encoder_device()
    offload_device = comfy.model_management.text_encoder_offload_device()

    logger.info("Loading Attribute Model (%s): %s...", model_key, name)

    try:
        if model_key == "face_attributes":
            processor = CLIPImageProcessor.from_pretrained(name)
            num_labels = {"age": 9, "gender": 2, "race": 7}
            model = MultiTaskClipVisionModel(num_labels=num_labels)
            cache_path = _face_attributes_checkpoint_path(name)
            if not os.path.exists(cache_path):
                if not self.download_mode:
                    raise _missing_model_error(f"Attribute model '{name}'")
                torch.hub.download_url_to_file(
                    f"https://huggingface.co/{name}/resolve/main/model.safetensors",
                    cache_path,
                )
            state_dict = load_safetensors(cache_path)
            model.load_state_dict(state_dict, strict=False)
            model = model.eval()
            logger.info(
                "Attribute model '%s' loaded on device: %s", model_key, load_device
            )
            # ModelPatcher(model, load_device, offload_device, size=0) — args are positional.
            # CoreModelPatcher is a runtime alias for ModelPatcher; use ModelPatcher directly.
            patcher = ModelPatcher(model, load_device, offload_device)
            wrapped_model = ComfyAttributeModel(patcher)
            result = (wrapped_model, output_dim, processor)
        elif model_key == "nsfw":
            processor = AutoImageProcessor.from_pretrained(name)
            model = AutoModelForImageClassification.from_pretrained(name)
            model = model.eval()
            logger.info("NSFW model '%s' loaded on device: %s", model_key, load_device)
            patcher = ModelPatcher(model, load_device, offload_device)
            wrapped_model = ComfyAttributeModel(patcher)
            result = (wrapped_model, output_dim, processor)
        else:
            raise KeyError(f"Unknown attribute model key: {model_key}")
    except OSError as e:
        raise _missing_model_error(f"Attribute model '{name}'") from e

    return result
```

#### Method for Batch Sizer
```python
def load_vision_model_patcher(self, model_key: str) -> ModelPatcher:
    """Return the underlying ModelPatcher for batch sizer profiling (internal infrastructure helper)."""
    vision_model = self.load_vision_model(model_key)[0]
    return vision_model.patcher
```

#### Removed from `ModelLoader.__init__`
- `self._hf_model_lock = threading.Lock()` (ComfyUI handles thread safety)
- Hardcoded `"cuda"` device checks in `load_vision_model`, `load_embedding_model`

#### Cache Structure Changes
```python
# Before:
# vision_model_cache: (model, output_dim, total_memory, transform)
# embedding_model: (SentenceTransformer, output_dim)
# _hf_model_cache: (model, output_dim, processor)

# After:
# vision_model_cache: (ComfyVisionModel, output_dim, total_memory, transform)
# embedding_model: (ComfyEmbeddingModel, output_dim)
# _hf_model_cache: (ComfyAttributeModel, output_dim, processor)
```

---

### 3. Batch Sizer (`infrastructure/ml_models/batch_sizer.py`)

#### Updated `_profile_new_resolution`
```python
def _profile_new_resolution(
    self,
    width: int,
    height: int,
    rebuild: bool,
    bound: int | None,
) -> int:
    _start = time.perf_counter()
    profile = self._active
    assert profile is not None

    key = self._resolution_key(width, height)
    if key not in profile.history:
        profile.history[key] = []

    # Get patcher from model loader
    patcher = self.model_loader.load_vision_model_patcher(self._model_key)
    device = patcher.load_device

    # Option 1: Skip profiling on non-CUDA, return conservative default = 1
    if device.type != "cuda":
        return min(1, bound or 1)

    # Existing CUDA profiling logic - ensure model is loaded first
    comfy.model_management.load_model_gpu(patcher)
    profile.model_memory_bytes = int(torch.cuda.memory_allocated(device))

    device_id = profile.device_id
    available = int(profile.total_memory) - profile.model_memory_bytes

    if rebuild and profile.history[key]:
        best = max(entry.batch_size for entry in profile.history[key])
        if bound is not None:
            best = min(best, bound)
        result = self._evaluate_candidate(
            model=patcher.model,  # Use inner model
            profile=profile,
            key=key,
            candidate=best,
            width=width,
            height=height,
            device_id=device_id,
        )
        if result is not None:
            return result
        low, high = 1, best - 1
    else:
        high = 1000
        if profile.pixel_cost is not None:
            per_image = profile.pixel_cost * width * height * 3
            fixed = profile.fixed_overhead or 0
            if per_image > 0:
                high = max(1, int((available - fixed) / per_image) * 2)
        if bound is not None:
            high = min(high, bound)
        low = 1

    last_success = 0
    while low <= high:
        mid: int = (low + high) // 2
        if mid == last_success:
            break

        result = self._evaluate_candidate(
            model=patcher.model,
            profile=profile,
            key=key,
            candidate=mid,
            width=width,
            height=height,
            device_id=device_id,
        )
        if result is None:
            high = mid - 1
        else:
            last_success = result
            low = mid + 1

    result = max(last_success, 1)

    old_fixed = profile.fixed_overhead
    old_pixel = profile.pixel_cost
    self._fit_model()
    if (
        old_fixed is not None
        and old_pixel is not None
        and profile.fixed_overhead is not None
        and profile.pixel_cost is not None
    ):
        fixed_shift = abs(profile.fixed_overhead - old_fixed) / max(abs(old_fixed), 1)
        pixel_shift = abs(profile.pixel_cost - old_pixel) / max(abs(old_pixel), 1e-12)
        if fixed_shift > 0.1 or pixel_shift > 0.1:
            logger.warning(
                "model parameters shifted significantly after rebuild "
                f"(fixed: {old_fixed} -> {profile.fixed_overhead}, "
                f"pixel: {old_pixel} -> {profile.pixel_cost})"
            )

    self._save_cache()
    return result
```

#### Updated `_evaluate_candidate` (model parameter type)
```python
def _evaluate_candidate(
    self,
    *,
    model: nn.Module,  # Now receives patcher.model (inner model)
    profile: ProfileData,
    key: str,
    candidate: int,
    width: int,
    height: int,
    device_id: str,
) -> int | None:
    result = None
    logger.debug(
        f"Evaluating batch size {candidate} for resolution {width}x{height}"
    )
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(device_id)
    batch_tensor = torch.zeros((candidate, 3, height, width), device=device_id)
    try:
        # Inference mode is set globally by ComfyUI; do not use torch.inference_mode() locally
        model(batch_tensor)
        torch.cuda.synchronize(device_id)

        peak = int(torch.cuda.max_memory_allocated(device_id))
        delta = peak - profile.model_memory_bytes
        threshold = int(profile.total_memory)
        if peak < threshold:
            profile.history[key].append(
                HistoryEntry(
                    batch_size=candidate,
                    delta_memory=delta,
                    timestamp=time.time(),
                )
            )
            result = candidate
    except Exception as e:
        logger.warning(
            f"batch size {candidate} for resolution {width}x{height} failed with error: {e}"
        )
    finally:
        del batch_tensor
        torch.cuda.empty_cache()
    return result
```

---

### 4. Caller Updates

#### `domain/vectors/image_vector.py`

**`create_vector_list` / `create_vector_list_from_paths`:**
```python
# Before:
# self.model, self.vector_length, _, self._transform = self.model_loader.load_vision_model(self.model_key)

# After:
self.model, self.vector_length, _, self._transform = self.model_loader.load_vision_model(self.model_key)
# Domain receives _VisionModel wrapper directly. No ModelPatcher or comfy imports in domain!
```

**`create_image_vector_batch`:**
```python
def create_image_vector_batch(self, current_batch: list[imageTuple]) -> vectorDict:
    if self._transform is None:
        raise RuntimeError("Model transform not set. Cannot process batch.")
    batch_id, image_batch = zip(*current_batch)

    model = self.model
    transformed_images: list[torch.Tensor] = [
        self._transform(img) for img in image_batch
    ]
    device = model.device

    batch_tensor = torch.stack(transformed_images, dim=0).to(
        device, non_blocking=True
    )

    # Calling model(batch_tensor) triggers load_model_gpu in infrastructure wrapper.
    # No torch.no_grad() context manager (inference mode is handled globally by ComfyUI).
    outputs = model(batch_tensor)

    # ... rest unchanged (validation, normalization) ...
```

---

#### `domain/vectors/embedding_vector.py`

**`create_vector_batch`:**
```python
def create_vector_batch(
    self, current_batch: Iterable[tuple[str, str]]
) -> dict[str, list[float]]:
    embedding_model, vector_length = self.model_loader.load_embedding_model()
    
    batch_id, batch_values = zip(*current_batch)
    # Infrastructure wrapper automatically calls load_model_gpu on demand
    encoded_values = embedding_model.encode(list(batch_values))
    processed: npt.NDArray[np.float32] = np.asarray(
        encoded_values, dtype=np.float32
    )
    if processed.shape[-1] != vector_length:
        raise RuntimeError(
            "CLIP returned unexpected vector length "
            f"{processed.shape[-1]}, expected {vector_length}"
        )
    if vector_length != self.slot_size:
        raise RuntimeError(
            f"Embedding model output length {vector_length} for '{self.name}' "
            f"does not match configured slot_size {self.slot_size}"
        )
    normalized: npt.NDArray[np.float32] = l2_normalize_batch(processed)
    normalized_list = normalized.tolist()
    result: dict[str, list[float]] = dict(zip(batch_id, normalized_list))
    return result
```

---

#### `domain/analysis/image_analysis.py`

**`__init__`:**
```python
def __init__(
    self,
    raw_data: list[ImageEntry],
    model_loader: ModelLoader,
    batch_sizer_factory: BatchSizerFactory,
    cache: CacheProvider,
    mediapipe: MediaPipePort,
) -> None:
    image_entries = [v for v in config["vector"]["vectors"] if v["type"] == "image"]
    if not image_entries:
        raise KeyError("No image-type entries found in vector_config")
    model_key = image_entries[0]["model_key"]
    slot_size = image_entries[0]["slot_size"]
    super().__init__(
        "tmp_image",
        model_key=model_key,
        slot_size=slot_size,
        model_loader=model_loader,
        batch_sizer_factory=batch_sizer_factory,
    )
    self.raw_data: list[ImageEntry] = raw_data
    self.processed_data: list[ImageEntry] = []
    self._cache = cache
    self._mediapipe = MediaPipeAnalyzer(mediapipe)
    # Pass model_loader to analyzers (they call load_hf_vision_model internally)
    self._face_attr = FaceAttributeAnalyzer(model_loader)
    self._nsfw = NSFWAnalyzer(model_loader)
    # ... rest unchanged
```

---

#### `domain/analysis/attribute_analysis.py`

**`FaceAttributeAnalyzer`:**
```python
class FaceAttributeAnalyzer:
    MODEL_KEY = "face_attributes"

    def __init__(self, model_loader: ModelLoader) -> None:
        self._model_loader = model_loader
        self._model: _AttributeModel | None = None
        self._output_dim: int = 0
        self._processor: object | None = None
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            model, self._output_dim, self._processor = self._model_loader.load_hf_vision_model(self.MODEL_KEY)
            self._model = model

    def predict_batch(
        self, imgs: Sequence[Image.Image]
    ) -> list[dict[str, list[dict[str, float]]]]:
        self._ensure_loaded()
        assert self._model is not None
        assert self._processor is not None
        
        device = self._model.device
        inputs = self._processor(images=list(imgs), return_tensors="pt").to(device)
        logits = self._model(pixel_values=inputs["pixel_values"])

        # ... rest unchanged (softmax, formatting) ...
```

**`NSFWAnalyzer`:**
```python
class NSFWAnalyzer:
    MODEL_KEY = "nsfw"

    def __init__(self, model_loader: ModelLoader) -> None:
        self._model_loader = model_loader
        self._model: _AttributeModel | None = None
        self._output_dim: int = 0
        self._processor: object | None = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        model, self._output_dim, self._processor = self._model_loader.load_hf_vision_model(self.MODEL_KEY)
        self._model = model

    def predict_batch(self, imgs: Sequence[Image.Image]) -> list[float]:
        self._ensure_loaded()
        assert self._model is not None
        assert self._processor is not None
        
        device = self._model.device
        inputs = self._processor(images=list(imgs), return_tensors="pt").to(device)
        outputs = self._model(**inputs)
        logits = outputs.logits
        probs = F.softmax(logits, dim=-1)
        nsfw_idx = 1
        return probs[:, nsfw_idx].cpu().float().numpy().tolist()
```

---

### 5. Device Behavior Summary

| Scenario | Vision/Embedding/Attribute Models | MediaPipe |
|----------|-----------------------------------|-----------|
| Default | Load to GPU, offload to GPU | CPU |
| `--gpu-only` | Load to GPU, offload to GPU | CPU |
| `--lowvram` | Load to GPU (partial), offload to CPU | CPU |
| `--novram` | Load to GPU (minimal), offload to CPU | CPU |
| `--cpu` | **Load to CPU, offload to CPU** | CPU |
| MPS (Mac) | Load to MPS, offload to MPS | CPU |

**Batch sizer on `--cpu`**: Returns `1` (no CUDA profiling possible)

---

### 6. Validation Steps

1. **Type check**: `pyright` - verify protocol + caller updates
2. **Lint**: `ruff check --select ARG,F401 --target-version py313 .`
3. **Architecture tests**: `pytest tests/test_architecture.py -v` (ensure zero comfy imports in domain)
4. **Node registration**: Smoke check from `AGENTS.md`
5. **CLI build test**: `python scorer.py build all --limit 10` (verify no OOM, models load)

---

### 7. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Batch sizer CUDA-only | Option 1 (return 1 on non-CUDA) - safe default |
| SentenceTransformer device handling | Wrap in `ComfyEmbeddingModel`; handles `load_model_gpu` and respects model device |
| Domain layer purity & ComfyUI imports | Encapsulate `ModelPatcher` and `load_model_gpu` in infrastructure `Comfy*` wrappers; domain remains 100% pure without `comfy` imports |
| Protocol breaking change | All callers updated in same change |
| VRAM pressure during build | ComfyUI `free_memory()` evicts automatically |

---

### 8. Out of Scope

- MediaPipe models (already CPU, no change)
- Training models (separate loader)
- Config/schema changes
- Frontend/web changes
