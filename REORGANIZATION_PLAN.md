# Reorganization Plan

This roadmap covers the remaining implementation and documentation work for the image-scorer module. The rules, functionality description, and current structure are maintained separately; this file owns sequencing, dependencies, acceptance criteria, and remediation status.

Every task below includes **why** the work is required and **how** it must be implemented. Each implementation must preserve the architecture boundaries, ownership rules, and validation discipline owned by `AGENTS.md`, and must use the current paths and symbols in the structure index owned by `FUNCTION_INDEX.md`. After an implementation change, update the index to the new current state; do not pre-document the change in the index.

The documentation baseline is the module-local Git repository at commit
`5fc9cd0` (`just more changes`). The ComfyUI root repository is not the history source
for these files; its virtual environment is used only to run validation.

Task identifiers were renumbered to run consecutively on 2026-10-02, when the
completed tasks were removed. Earlier commit messages use the old identifiers:
D-02 to D-01, D-03 to D-02, P-05 to P-01, P-10 to P-02, P-16 to P-03, P-40 to P-04,
and P-43 to P-05. Index entries keep the `I-` prefix and were not renumbered.

## Documentation tasks

- [ ] **D-01 — Complete the current structure index.**
   - **Why:** every implementation task needs an accurate path and symbol anchor; missing descriptions hide ownership and make edits speculative. Five live files and one port method list still have no entry, so the index does not yet enumerate the whole tracked tree.
   - **Rules/structure:** follow the live-tree and current-state documentation rules in `AGENTS.md`; anchor entries to the paths currently listed by the repository structure in `FUNCTION_INDEX.md`.
   - **How:** enumerate every current package, test, configuration, frontend, documentation, and script file. Add concise file descriptions plus reliable public classes, protocols, functions, constants, node mappings, and CLI entry-point descriptions. Do not list planned or removed files. The concrete gaps are recorded as I-01 below.

- [ ] **D-02 — Resolve missing index descriptions before finalization.**
  - **Why:** a blank description is an undocumented structure constraint and prevents agents from knowing what a file owns.
  - **Rules/structure:** follow the ownership, source-of-truth, and no-future-state rules in `AGENTS.md`; name the exact live path or symbol from `FUNCTION_INDEX.md`.
  - **How:** add each missing file or symbol here under “Index description tasks,” state the required explanation, then add that explanation to `FUNCTION_INDEX.md` before marking the task complete.

## Pending implementation tasks

- [ ] **P-01 — Add one pure history-collapse operation.**
   - **Why:** `domain/comparison/algorithm/history_collapse.py` now owns `collapse_comparison_history`, which the rebuild and the comparison repository both call, but the older `collapse_comparisons` in `domain/comparison/algorithm/graph_helpers.py` is still a second implementation of the same missing-node, self-link, same-direction and contradiction rules. It has no production caller left, only `tests/test_graph_helpers.py`, and it is typed over bare `dict[str, object]` rows instead of `ComparisonRow`. It is also the reason `graph_helpers` imports `canonicalize_pair` and `safe_parse_timestamp` from `history_collapse` and re-exports them, and the reason `infrastructure/persistence/deduplicate_scored.py` and `infrastructure/persistence/path_handler.py` import `safe_parse_timestamp` through a module that does not own it.
   - **Rules/structure:** follow the pure-domain, deterministic-data, dead-code, and no-re-export rules in `AGENTS.md`. The owning layer is `domain/comparison/algorithm/history_collapse.py`; SQLite access stays in `infrastructure`.
   - **How:** delete `collapse_comparisons` from `graph_helpers.py` and the imports it is the last user of, repoint `deduplicate_scored.py` and `path_handler.py` at `domain.comparison.algorithm.history_collapse`, and retarget `tests/test_graph_helpers.py` at `collapse_comparison_history`. Keep one focused case per rule, including duplicate two-sided histories, contradictions, self-links, missing nodes, equal timestamps and id uniqueness. Update `FUNCTION_INDEX.md` after the live tree changes.

- [ ] **P-02 — Clear the remaining real type-check diagnostics.**
   - **Why:** the recorded status for this task claimed the residual `pyright` count was entirely `reportUnknown*` leakage from third-party packages. Measured 2026-10-02, the module reports 189 errors and 20 of them are real interface errors in this module's own code, which that claim would hide.
   - **Rules/structure:** follow strict typing and minimal-change rules in `AGENTS.md`. Fix the cause; a blanket `# type: ignore` is not a resolution.
   - **How:** the 20 real diagnostics fall into four groups. Two belong to this task:
     - `application/analysis/tests/test_analysis.py:281-282` cast to the string names `"CrystalGraphPort"` and `"TrainingLoader"`, which the module never imports, so pyright reports two `reportUndefinedVariable` errors. Import both from `domain.ports` and cast to the real symbols.
     - `domain/analysis/image_analysis.py:328,458` and `domain/vectors/number_vector.py:18,47` pass `object`-typed values into `float` and `int` conversions, producing six `reportArgumentType` errors. Give each value a concrete type where it is produced instead of casting at the use site.
     - Not this task, the first of the other two: the nine `reportArgumentType` errors at `domain/comparison/algorithm/graph_helpers.py:144-165` all sit inside the duplicate `collapse_comparisons`, so P-01 removes them by deleting it.
     - Not this task either: the three `reportArgumentType` errors at `adapters/cli/deps.py:97`, `adapters/comfyui/services.py:33`, and `adapters/server/main.py:124` are the model-loader port mismatch, which P-03 owns.
     Leave the remaining 169 `reportUnknownMemberType`, `reportUnknownVariableType`, and `reportUnknownArgumentType` diagnostics alone: they come from `sklearn`, `scipy`, `comfy.model_management`, `timm`, `transformers`, `huggingface_hub`, `safetensors`, and `torch.cuda`. Re-run `pyright` afterwards and record the new count and date in the baseline table.

- [ ] **P-03 — Reconcile the model loader's annotations with its domain port.**
   - **Why:** the ComfyUI memory-management work moved model device placement and VRAM ownership behind `ComfyVisionModel`, `ComfyEmbeddingModel`, and `ComfyAttributeModel` and left `domain/ports/loading.py` as pure protocols, but the two sides were never made to agree. `infrastructure.ml_models.model_loader.ModelLoader` does not structurally satisfy `domain.ports.loading.ModelLoader`, so `pyright` rejects the injection at all three composition roots — `adapters/cli/deps.py:97`, `adapters/comfyui/services.py:33`, and `adapters/server/main.py:124`. `load_vision_model` is annotated `tuple[ComfyVisionModel, int, int, Compose]` where the port declares `tuple[VisionModel, int, int, Transform]`: `torchvision.transforms.Compose.__call__` takes an untyped positional `img` and returns untyped, so it does not match the `Transform` protocol's `__call__(self, image: Image.Image) -> torch.Tensor`. Everything else is in place: the wrappers call `load_model_gpu` on every invocation, `batch_sizer.py` profiles through `load_vision_model_patcher()` and returns 1 off CUDA, the package `__init__.py` adds the host ComfyUI root to `sys.path`, and `infrastructure/ml_models/tests/test_model_loader.py` covers the three forwards.
   - **Rules/structure:** follow the protocol-purity, composition-root, and strict-typing rules in `AGENTS.md`. `domain/ports/loading.py` keeps describing only the callable surfaces domain code uses and stays free of `comfy` imports; the reconciliation belongs in the infrastructure annotations rather than in a loosened port, and the vision/embedding/attribute device behaviour stays owned by the wrappers.
   - **How:** make the concrete return annotations structurally satisfy the declared port, keeping one owner for each callable surface, and confirm the three composition roots type-check. Validate with `pyright`, `pytest tests/test_architecture.py`, and `pytest infrastructure/ml_models/tests/`.

- [ ] **P-04 — Finish the node/link vocabulary on the comparison status payload.**
   - **Why:** the node/link vocabulary rename that closed earlier graph work covered the pair payload but not every payload. `GET /api/comparison/status` still emits image vocabulary for counts it takes straight from the graph — `total_images`, `ranked_images`, `unranked_images`, and `total_comparisons` — while `total_components`, `total_chains`, and `active_nodes` in the same object already use the new vocabulary. `adapters/frontend/comparison/compare.js:568-581` reads all seven, so nothing is broken today, but the same number is `total_nodes` in the pair payload and `total_images` in the status payload, which is exactly the split the rename existed to close. Two keys in the placeholder pair object at `compare.js:397-410` are also stale: `collapsable` is dead, because the backend and `compare_view.js` spell it `collapsible`, and `seed_percentage: this._config.seed_size ? 0 : 0` evaluates to `0` on both branches while `compare_view.js:282` renders it in the debug table.
   - **Rules/structure:** the `Proxy vocabulary` section in `AGENTS.md` owns both the boundary rule and the HTTP-key contract rule — rename a payload key only together with every consumer that reads it. The database column stays `comparison_count`; only graph-facing names change.
   - **How:** rename the four status keys to node/link vocabulary, update `compare.js:updateStats` in the same change, drop the dead `collapsable` key, and make the placeholder `seed_percentage` read the configured value. Verify with `node --check` over the frontend scripts and the endpoint contract tests.

- [ ] **P-05 — Collect the application tests from the default suite.**
   - **Why:** `pyproject.toml` sets `testpaths = ["tests", "adapters", "domain", "core", "infrastructure"]`, which omits `application`. The 14 analyzer tests in `application/analysis/tests/test_analysis.py` pass when named explicitly but have never run in the default suite, because `AGENTS.md` defines the default package suite as the configured non-real-data suite and that suite does not reach them.
   - **Rules/structure:** the configuration is what is wrong, not the tests. Keep the real-data marker and the `-m 'not realdata'` selection as they are.
   - **How:** add `"application"` to `testpaths`, re-run `python -m pytest -q`, and record the new count and date as the baseline. Expect the count to rise from 117 to 131 with nothing else changing; if it does not, an application test is failing silently today.

## Required rebuild invariants
- Database and in-memory graph history remain synchronized.
- Companion JSON history carries no database identifiers. `comparison_id` was removed because the database is cleared and repopulated on every rebuild, which left it pointing at rows that no longer existed. Training and NPZ consumers read the `id` field instead.
- Collapse uses an explicit deterministic total order independent of file discovery completion order.
- File discovery, `collect_valid_files`, and `parallel_for` all return input order so a rebuild of unchanged files is bit-identical and the JSON write guard converges.
- Replayed ratings and per-file histories are exactly equal across runs of unchanged input, not merely equivalent.
- The ranking loop's LRU-overflow chain-cover refresh remains intact.
- Focused coverage includes duplicate two-sided histories, contradictions, self-links, missing nodes, equal timestamps, ID uniqueness, and JSON sync.

## Validation

For every task, follow the agent rulebook's narrow-to-broad validation order. From the module root, use the configured non-real-data pytest suite as appropriate, then `ruff check --select ARG,F401,SLF001 --target-version py313 .`, `pyright`, architecture/database/proxy tests, and the node-registration smoke check. Record the command, date, and result for any baseline. Run real-data tests only by explicit request because they are destructive. Documentation work is complete only when the four documents preserve their ownership boundaries, the index describes only the live tree, and every missing description has first been recorded as a task here.

### Baseline

Measured 2026-10-02 while re-verifying this plan. It reflects the tree as it stands, not the result of any task below.

| Check | Command | Result |
|---|---|---|
| Focused suites | `python -m pytest tests/test_graph_facade.py tests/test_image_processor.py tests/test_architecture.py -q` | 19 passed |
| Package suite | `python -m pytest -q` | 117 passed, 1 deselected |
| Application tests | `python -m pytest application/analysis/tests/test_analysis.py -q` | 14 passed, not collected by the package suite (P-05) |
| Lint | `ruff check --select ARG,F401,SLF001 --target-version py313 .` | clean; the `domain/comparison/algorithm/pair_active.py` F401 older baselines recorded as pre-existing is gone, its only reference now being a comment |
| Types | `pyright` | 189 errors; 20 are real (P-01, P-02, P-03), the rest are third-party `reportUnknown*` leakage |
| Boundaries | `pytest tests/test_architecture.py -q` | 3 passed |
| Registration | `NODE_CLASS_MAPPINGS` smoke check | `['AestheticScore']` |
| Frontend syntax | `node --check` over all 29 scripts | 0 failures |
| Assets | 35 local `src`/`href` references from the shell and section markup, resolved through the `/static/<section>/`, `/css/`, and `/js/` routes in `adapters/server/main.py` | 35 referenced, 0 failures |

Earlier `945`, `246`, `247`, and `192` figures recorded by superseded tasks are history, not the current baseline. `pyright` must drop below 189 once P-01, P-02, and P-03 land; record the new figure and date here at that point.

`GET /api/analyze/stats` was exercised against a live server on the real 30,473-image graph: the response carries the 17 `GraphStats` keys, `ranked + unranked == total`, `sigma_above_threshold + sigma_below_threshold == total`, the ten score buckets sum exactly to the total, buckets ascend, and the highest and lowest rows sit at the ends of the score range. Real-data and command-contract suites were not run in this pass, as they require an explicit request. See the last deferred finding: another process was writing to `output/` during that measurement, so treat its counts as indicative.

## Index description tasks

Add one entry here before finalizing the index for every file or public symbol that lacks a useful description. Each entry must name the path or symbol and state the ownership or behavior the index description must explain.

- **I-01 — Five live files and one port method list are absent from the structure index.** Re-verified 2026-10-02 by diffing every tracked path against every indexed path. No index entry is stale — each resolves to a file that exists — but these live paths and symbols have no `FUNCTION_INDEX.md` entry, so the index does not yet satisfy D-01.
  - `application/analysis/run_stats.py` — the CLI `run_stats` that drives `scorer.py analyze stats` and `print_stats` beside it, which `adapters/server/endpoints/analyze.py` imports so the endpoint prints the same numbers the CLI does. Neither symbol is indexed.
  - `experiments/loop_detection.ipynb` — the second experimental notebook. The index lists only `experiments/depth_comparisons.ipynb`.
  - `domain/graph/tests/__init__.py` and `infrastructure/ml_models/tests/__init__.py` — test package markers that carry no behavior. Add `Tests` entries for both, or state why they need none.
  - `infrastructure/ml_models/tests/test_model_loader.py` — covers the `ComfyVisionModel`, `ComfyEmbeddingModel`, and `ComfyAttributeModel` patcher wrappers by asserting each forward carries no autograd graph. The index lists `test_batch_sizer.py` beside it but not this one.
  - `domain/ports/files.py` `FilePort` — the indexed method list is missing `pop_sync_counters`, which the protocol declares and `adapters/server/endpoints/database.py` reads.

## Deferred findings

Found while executing the graph-vocabulary, frontend, and analyzer work and recorded rather than fixed, because each is a separate decision from the work it was found in.

- **No test pins the HTTP payload contract.** The graph-vocabulary rename missed two consumers: the analyze dashboard read `stats.total` and rendered Images as a dash, and the comparison footer read `pair.total_images` and threw on every phase because `undefined.toLocaleString()` fails. The backend sent `collapsible` while the view read `pair.collapsable`, so that row and the footer suffix always took the false branch. All four were fixed by hand, and a one-off audit of the keys the analyze and comparison views read now reports no unknown reads, but nothing enforces it: the suite only parses the frontend scripts and never checks that a key a view reads is a key the backend emits, so the next rename can ship the same breakage. Add a test that compares the keys every view script reads against the keys the shaping functions actually return. Note that `/api/comparison/status` is still outside the rename, which P-04 tracks.
- **`VectorList.join_text_data` stringifies every column.** `application/services/vector_list.py:373` writes each value through `str()`, so `text_data.jsonl` stores `steps` as `"20"` and one-hot columns as Python repr strings such as `"{'euler_ancestral': 1.0}"`, which is not valid JSON. `application/analysis/row_fields.py` works around it by preferring the real type and parsing the stringified form, but the artifact itself is lossy. Stop stringifying structured columns, or split the sidecar so numeric and map columns stay typed. This needs a rewrite of the 190 MB artifact, so it is its own task.
- **Unbalanced parentheses defeat term splitting.** About 66 of 400 real prompts contain more `(` than `)`, and `domain/vectors/terms.py:tokenize_by_depth` cannot find a matching depth, so the remainder of the prompt is emitted as one enormous term - visible in the parameter-analysis output as terms such as `using beer_bottle, and makeup and earings and necklace and high heels`. This caps the quality of every term table and is not fixable in the analyzers. Either make the tokenizer recover at depth zero or drop the unmatched tokens.
- **Write-only `_start` timers are widespread.** The gallery and maps endpoints no longer have one, but a whole-repo scan on 2026-10-02 finds the same dead local in `core/io/serialization.py` (4), `core/utilities/helpers.py` (2), `domain/vectors/helpers.py` (2), `domain/comparison/algorithm/graph_helpers.py` (2), `infrastructure/ml_models/batch_sizer.py` (6), and one each in `application/services/vector_list.py`, `adapters/server/compressed_image.py`, `infrastructure/persistence/cleanup_orphans.py`, and `infrastructure/persistence/folder_organizer.py`. Decide whether these are timing scaffolding that should be wired to the logger or removed outright, then do it in one pass.
- **The facade bulk methods were justified, not skipped.** `CrystalGraph.add_images_bulk` and `update_image_rating_states_bulk` leave or update the in-memory node map differently from the single-row methods. That asymmetry is now documented rather than changed, because the ranking pipeline relies on it.
- **No cleanup command covers `analysis_dir`.** `maps_dir` is removed by two commands; `analysis_dir` has no equivalent, so parameter-analysis and matrix-analysis artifacts accumulate with no operator action to clear them. Adding one is a new destructive operation and needs explicit approval.
- **`ImageRow.ranking_generation` is live.** It is declared at `domain/ports/repository.py:21`, has a matching column at `infrastructure/persistence/database.py:78`, and is asserted by `tests/test_image_processor.py`. It is not dead and must not be removed.
- **`prompt_tags` should carry weighted terms and keep the raw prompt.** `core/io/serialization.py:259` stores `extract_prompt_tags(json_data)`, which copies `positive_prompt` through verbatim as a string, so the `images.prompt_tags` column never holds the weighted terms that `domain/vectors/terms.py:extract_terms` produces. Store the extracted `(term, weight)` pairs and keep the raw prompt alongside them, migrate the existing rows, and change gallery search to match either or both. The search box needs its own rework at the same time. Found 2026-10-02 while fixing the analyzers; deliberately out of scope there because it changes a stored column's meaning and the `prompt_tags` test starting at `tests/test_image_processor.py:483` pins the column to `clean_json_metadata`. The 74 images whose `prompt_tags` is NULL have no companion JSON at all, so they can only be recovered from `text_data.jsonl` if they are backfilled that way.
- **Duplicate element ids remain across mutually exclusive route templates.** `log-area` and `clear-log-btn` appear in the four section templates, and `stat-chains`, `stat-comparisons` and `stat-components` appear in both the comparison and map templates. The router loads one template at a time so nothing collides today, but any future shell-level control that queries by id can grab the wrong element. The one pair that was actually duplicated inside the shared shell (`compare-selected-btn` and `selected-count`, which the gallery and map templates both carried) has since moved into the shell itself and is gone from both templates.
- **Something else writes to `output/` while the module is idle.** Observed 2026-10-02: row counts moved between consecutive reads with no write from this work. `prompt_tags` non-null read 30405, then 30399, then 30424, and `describe_graph`'s `total_nodes` moved from 30476 to 30539. `output/image_vector_size.json` was rewritten seconds apart from a read, and `cache.db` last changed at 11:26 while `cache.db-wal` was touched at 12:49. The most likely cause is a running ComfyUI instance or a leftover scorer server. It matters because it makes any recorded count unrepeatable, so the real-data figures quoted in this file should be re-measured once the concurrent writer is stopped, and no measurement taken while it was running should be treated as exact.

---

## Appendix: P-03 Implementation Specification (Draft)

This appendix preserves the original draft technical design for the ComfyUI memory-management work in **P-03**. It is a historical design record, not live documentation: the wrappers, the device helpers, and the batch-sizer behaviour it describes are implemented, and the protocol names below have since moved on. `FUNCTION_INDEX.md` owns the current names — `VisionModel`, `EmbeddingModel`, `AttributeModel`, `Transform`, `ImageProcessor`, `BatchTensors`, `ModelTrainingService`, and `ScoringModel` are public now, `_ModelTrainer` no longer exists, and the draft's `torch.no_grad()`-free forwards were later wrapped deliberately so an unwrapped forward does not retain an autograd graph. Where this appendix and the live tree disagree, the live tree wins.

- **Why:** Current `ModelLoader` loads models directly with `.to(device)` and maintains manual caches, bypassing ComfyUI's VRAM management, offloading, and device handling (`--cpu`, `--lowvram`, `--gpu-only`, MPS, DirectML). This causes OOM risk, no automatic offloading, and hardcoded CUDA dependency.
- **Rules/structure:** Follow architecture boundaries (`infrastructure` implements domain ports; `domain` must not import `comfy` or manage GPU memory), strict typing (no `Any` in protocols), dtype/device/VRAM correctness, use ComfyUI optimized ops (`load_model_gpu`, `get_free_memory`), preserve offline loading, no internet requests. Update `FUNCTION_INDEX.md` after implementation.
- **How:** In `infrastructure/ml_models/model_loader.py`, wrap models with `ModelPatcher` / `CoreModelPatcher` and encapsulate `comfy.model_management.load_model_gpu` inside infrastructure callable wrappers (`ComfyVisionModel`, `ComfyEmbeddingModel`, `ComfyAttributeModel`). Keep `domain/ports/loading.py` purely protocol-based (`_VisionModel`, `_EmbeddingModel`) without importing `comfy`. Update callers in `domain/` to call the wrapped models directly without context managers or manual GPU loading calls.

### Files to Modify

| File | Change Type |
|------|-------------|
| `domain/ports/loading.py` | Protocol update (pure `_VisionModel`, `_EmbeddingModel`, `_AttributeModel` protocols) |
| `infrastructure/ml_models/model_loader.py` | Core implementation & ComfyUI wrappers |
| `infrastructure/ml_models/batch_sizer.py` | Device-aware profiling (Option 1) |
| `domain/vectors/image_vector.py` | Caller update (direct execution) |
| `domain/vectors/embedding_vector.py` | Caller update (direct execution) |
| `domain/analysis/image_analysis.py` | Caller update |
| `domain/analysis/attribute_analysis.py` | Caller update (direct execution) |

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
        # A forward pass must not build an autograd graph: ComfyUI applies
        # @torch.no_grad() per function and enables nothing process-wide, so
        # every intermediate is otherwise retained for backward at several times
        # the peak.
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
    # Run it without building an autograd graph, or every intermediate is
    # retained for backward at several times the peak.
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
