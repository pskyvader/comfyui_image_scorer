# AGENTS.md — comfyui_image_scorer (module rules)

**Scope:** this file governs all work inside `comfyui_image_scorer/`. The
ComfyUI root `AGENTS.md` covers ComfyUI core and does not apply here. When a
rule here conflicts with the root file, this file wins for this module.
- All agents must work within the limits of this module
  (`comfyui_image_scorer/`). Agents can read everything, but cannot write
  anything outside this directory.

## Reference Material

- The `comfyui_image_scorer_old/` folder is **read-only reference material** —
  never edit it; the user removes it manually.
- `REORGANIZATION_PLAN.md` is the live remediation roadmap and the source of
  truth for what must change. When in doubt, check §1 (source of truth) and
  §5 (explicitly out of scope) before changing anything.
- Fix violations by moving code across the boundary per the plan — never by
  relaxing a rule or deleting the check that enforces it.
- Structure (folder layout, paths, section mapping) is documented in
  `README.md` — never restate it here or in chat summaries of the layout.

## Environment & Commands

- Every command (`pytest`, `pyright`, import checks, CLI runs) executes in the
  **ComfyUI venv** — the one ComfyUI uses (`.venv` at the ComfyUI root).
  Activate it first; this is what makes `torch`, `comfy`, and ComfyUI-internal
  packages resolve for both the server and the node entry points.
- The package is never pip-installed; only its dependencies are
  (`pip install -r requirements.txt`, regenerated via
  `uv pip compile pyproject.toml -o requirements.txt`).
- Static typing: `pyright` must pass in strict mode (`pyrightconfig.json`,
  `"typeCheckingMode": "strict"`).
- Tests: `pytest` (colocated `tests/` next to the module under test).
  **Test scope:** by default run only the colocated suites for the module
  under change (e.g. `pytest domain/graph/tests`). The general suite at the
  root `tests/` directory (`test_general.py` — the full command↔endpoint
  contract) runs only when the user explicitly prompts for it.
- Verification order after a change: `pytest` → `ruff` (ARG/F401) → `pyright`
  → AST layer scan (REORGANIZATION_PLAN §4) → node registration smoke check.

## Engineering Style

- Small, direct changes touching the narrowest code path. Change the least
  number of files possible.
- Practical fixes over broad architecture work; add abstractions only when
  they remove real repeated logic or match an existing pattern.
- Fewer dependencies — never add a new one unless absolutely necessary.
- Delete dead code aggressively: dead fallbacks, migration paths, unused
  options, debug prints, compatibility branches, unreachable code, functions
  that are never called. If code is not necessary for current behavior,
  remove it.
- Preserve existing APIs, node names, model-loading behavior, file layout, and
  workflow compatibility unless the change is explicitly about replacing them.
- Revert or disable problematic behavior quickly rather than keeping a
  complicated partial fix.
- Warning and info messages: short and actionable; remove noisy output.
- No telemetry, analytics, uploads, update checks, remote config, or any other
  outbound internet path. Model downloading happens only via the explicit
  `files download models` CLI command (or its server button); runtime loading
  is offline-only with a fail-fast hint.

## Python Style

- Relative imports, at module scope. Only `adapters/cli/main.py`'s lazy
  parser dispatch uses inline imports — that one established pattern is
  allowed, but do not spread it to new code.
- No error-swallowing `try`/`except` blocks. Let failures surface with clear
  errors. No fallbacks. Permitted forms only (see REORGANIZATION_PLAN.md
  §3.10 #37): finally-only cleanup with a comment naming what it restores;
  except used solely to translate-and-reraise a clearer error (`raise ...
  from e`, never suppressed); and `except torch.cuda.OutOfMemoryError`
  where OOM-adaptive batching is the working of the function (batch-size
  profiler, image-vector retry loop).
- No workarounds for pinned library versions.
- Let unsupported formats, invalid states, and bad data fail clearly instead
  of silently degrading quality.
- Match the local style of the file you edit. Long lines, simple helpers,
  module-level state, and direct tensor operations are fine when they make the
  code easier to follow for a human.
- Keep comments sparse and useful; strip comments that restate the code.
- No global mutable state in `core`/`domain`/`application`. State lives in
  `adapters` or `infrastructure`.
- Configuration enters only via `core.configuration` — no `os.getenv` or
  scattered path resolution in domain/application code.
- No default: defaults (`foo.get(..., default)`) are highly discouraged, and
  strictly forbidden for config objects. Also, for function args always try to
  avoid them.
- Tests: colocated `tests/` directory next to the tested module. Tests may
  import across layers but must satisfy the dependency table (use fakes, not
  real infrastructure).

## Model, Device, and Memory

- dtype, device placement, VRAM usage, and offloading behavior are core
  correctness concerns. Check CPU/CUDA/ROCm/MPS/DirectML/XPU/NPU and low-VRAM
  implications when touching shared execution or loading code.
- Use existing ComfyUI helpers and optimized kernels (`comfy.quant_ops`,
  `comfy.model_management`, `comfy.memory_management`, Comfy Kitchen) before
  writing local implementations. Treat optimized backend functions as opaque:
  depend on the documented interface, never on which backend was selected.
- No `torch.no_grad`/`torch.inference_mode` wrappers; no freeze/unfreeze
  toggles; models are always frozen for inference.
- No `einops` in core inference code — use native torch ops.
- No tensors as Python-side metadata: sequence lengths, offsets, counts, and
  structural values stay Python ints/lists.
- Avoid unnecessary casts and transfers; preserve compute dtype, storage
  dtype, bias dtype, and shape metadata.
- No global/module/class stores of large tensors across executions. Temporary
  caches are scoped to a single call and passed explicitly down the stack.
- Model code does not perform memory management (loading, offloading, device
  movement, VRAM policy) — that belongs to model-management/execution layers.
- `nn.Parameter` placeholders loaded from the state dict are initialized with
  `torch.empty`, never with meaningful values.

## Nodes & User-Facing Behavior

- Follow node conventions: `INPUT_TYPES`, `RETURN_TYPES`, `FUNCTION`,
  `CATEGORY`, and registration through the local mapping.
- Minimal nodes: reuse existing nodes over creating new ones; adapt the model
  to existing nodes when possible.
- Nodes output only values they own — no pass-through or placeholder outputs.
- Node code never patches model code directly; use the model patcher class.

## Commit & Review Habits

- Commit subjects: `Fix ...`, `Add ...`, `Support ...`, `Remove ...`,
  `Update ...`, `Make ...`, `Use ...`, `Disable ...`, `Bump ...`,
  `Revert ...`.
- One coherent behavioral change per commit; short reviewable PR descriptions
  (problem, behavioral change, tests run).
- Review priority: crashes, wrong dtype/device behavior, memory regressions,
  broken model loading, workflow incompatibility, noisy or misleading
  user-facing output.