# AGENTS.md — comfyui_image_scorer (module rules)

**Scope:** this file governs all work inside `comfyui_image_scorer/`. The
ComfyUI root `AGENTS.md` covers ComfyUI core and does not apply here. When a
rule here conflicts with the root file, this file wins for this module.

## Why Things Are Not Always Correct

- This module was reorganized out of a legacy layout
  (`comfyui_image_scorer_old/`). That folder is **read-only reference
  material** — never edit it; the user removes it manually.
- The codebase still violates parts of its own documented architecture.
  `REORGANIZATION_PLAN.md` (v2) is the live remediation roadmap and
  enumerates the known violations (layer import violations, `core` purity,
  structural defects). It is the source of truth for what must change.
- Fix violations by moving code across the boundary per the plan — never by
  relaxing a rule or deleting the test that checks it.
- When in doubt, check `REORGANIZATION_PLAN.md` §2 (verified violations) and
  §7 (explicitly out of scope) before changing anything.

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
- Tests: `pytest` (colocated `tests/` next to the module under test;
  architecture test at `tests/test_architecture.py`).
- Verification order after a change: `pytest` → `pyright` → AST layer scan
  (the script in `REORGANIZATION_PLAN.md` §6) → node registration smoke check.

## Architecture

- Layering, imports point inward only:
  `core → domain → application → adapters → infrastructure`.

| Layer | May Import From | Must Not Import From |
|---|---|---|
| `core` | stdlib only | `domain`, `application`, `adapters`, `infrastructure` |
| `domain` | `core` | `application`, `adapters`, `infrastructure` |
| `application` | `core`, `domain` | `adapters`, `infrastructure` |
| `adapters/*` | `core`, `domain`, `application` | other `adapters/*`, `infrastructure` |
| `infrastructure` | `core`, `domain` | `application`, `adapters` |

- **Nothing imports `infrastructure`.** Its implementations reach callers via
  dependency injection; wiring happens at the composition roots in `adapters`
  (`adapters/server/main.py`, `adapters/cli/main.py`, `adapters/comfyui/`).
- Ports live in `domain`; implementations live in `infrastructure`.
- Each layer owns its concepts: no UI/API/workflow/persistence/telemetry
  concerns leaking into unrelated layers. Pass the narrowest data across
  boundaries.
- The ComfyUI node integration is the primary deliverable; all other layers
  exist to serve it.

## Engineering Style

- Small, direct changes touching the narrowest code path. Change the least
  number of files possible.
- Practical fixes over broad architecture work; add abstractions only when
  they remove real repeated logic or match an existing pattern.
- Fewer dependencies — never add a new one unless absolutely necessary.
- Delete dead code aggressively: dead fallbacks, migration paths, unused
  options, debug prints, compatibility branches, unreachable code, functions
  that are never called.
- Preserve existing APIs, node names, model-loading behavior, file layout, and
  workflow compatibility unless the change is explicitly about replacing them.
- Backward compatible by default: add inputs with sensible defaults; avoid
  changing output types. The module is young and internal callers are few —
  when a parameter's default is ambiguous, state it explicitly at every call
  site instead of relying on the default.
- Revert or disable problematic behavior quickly rather than keeping a
  complicated partial fix.
- Warning and info messages: short and actionable; remove noisy output.
- No telemetry, analytics, uploads, update checks, remote config, or any other
  outbound internet path. Model downloading happens only via the explicit
  `files download models` CLI command; runtime loading is offline-only with a
  fail-fast hint.

## Python Style

- Relative imports, at module scope. The CLI command modules use lazy inline
  imports for heavy dependencies — that established pattern is allowed before fixing the remaining work, but do
  not spread it to new code.
- No `try`/`except` blocks. Let failures surface with clear errors. No fallbacks. The only exception is batch size profiler, which is part of the actual working of the function.
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
- No default: defaults (foo.get(....,default)) are highly discouraged, and strictly forbidden for config objects. also, for functions args always try to avoid them.
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
