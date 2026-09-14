# Agent Rules

These rules govern every change inside `comfyui_image_scorer`. They are complete on purpose: an agent working in this directory must not need another document to discover the engineering constraints.

## Scope and safety

- Work only inside this module unless the user explicitly requests an external change.
- Keep changes small, direct, and limited to the owning layer.
- Preserve public APIs, node names, workflow compatibility, model-loading behavior, and file layout unless replacement is explicit.
- Do not revert user changes or unrelated work.
- Do not add telemetry, analytics, uploads, update checks, remote config, or other outbound internet paths. Model downloads are explicit user actions.
- Treat legacy reference material as read-only.
- `FUNCTION_INDEX.md` is a live current-state inventory. It may describe only files, symbols, ownership, and behavior that exist now; it must not describe planned interfaces, future migrations, removed APIs, or acceptance criteria. Update it after any change that alters the live tree, symbols, ownership, or public interfaces.

## Documentation ownership

Four documents describe this module. Each owns a distinct category; no document may duplicate another's content.

| Document | Owns |
|---|---|
| `AGENTS.md` | Permanent engineering constraints, including the documentation ownership rules above. |
| `README.md` | Module purpose, goals, functionality, usage, and the general architecture diagram. |
| `FUNCTION_INDEX.md` | Current live file, symbol, ownership, and behavior inventory. Must never describe planned or removed state. |
| `REORGANIZATION_PLAN.md` | Sequencing, dependencies, acceptance criteria, and current remediation status. |

Cross-references may identify the document that owns a fact, but no document may duplicate another document's rules, functionality, inventory, or roadmap status.

## Architecture

The dependency direction is `core -> domain -> application -> adapters`. Infrastructure implements domain ports and is imported only by these composition roots: `adapters/server/main.py`, `adapters/cli/deps.py`, and `adapters/comfyui/services.py`. These roots construct concrete infrastructure services and inject them through ports; core, domain, and application code must not import infrastructure implementations directly.

- `core` contains generic configuration, filesystem, IO, logging, and utility primitives. It imports no higher layer or ComfyUI code.
- `domain` contains business logic, algorithms, models, and pure port interfaces. It imports only `core`.
- `application` orchestrates use cases and imports only `core` and `domain`.
- `adapters` translates Flask, CLI, frontend, and ComfyUI protocols and may import `core`, `domain`, and `application`.
- `infrastructure` contains SQLite, filesystem, loaders, ML, and cache implementations and imports only `core` and `domain`.

`CrystalGraph` is the application-facing graph/database boundary. Callers use node, link, chain, and component proxies; they do not import repositories, database tables, or construct proxies directly. Ports are abstract protocols only: no concrete logic, IO, database calls, or plotting belongs in a port.

## Code rules

- Use relative imports at module scope. The CLI parser may lazily import heavy command modules when required for startup performance.
- Use strict typing. Do not add `Any` to protocols or domain interfaces; use concrete row, payload, proxy, and result types.
- Avoid default arguments and optional sentinels for required configuration or behavior. Preserve an existing public default only when removing it would break a documented compatibility contract.
- Do not swallow errors. Allowed exception handling is cleanup in `finally`, translation followed by `raise ... from`, and existing CUDA OOM retry behavior where adaptive batching is the function purpose.
- Keep mutable state out of `core`, `domain`, and `application`; put state in the owning adapter or infrastructure service.
- Configuration enters through the configuration service. Do not read environment variables or resolve runtime paths ad hoc in domain or application code.
- Remove unused arguments and repair every caller. Framework-required positional slots may use an underscore-prefixed name.
- Keep tensor metadata and control-flow values as Python values. Avoid unnecessary casts, transfers, persistent tensor caches, and model-owned memory management.
- Do not use `torch.no_grad`, `torch.inference_mode`, `einops`, or explicit model freeze/unfreeze toggles in inference code. Use native tensor operations and existing model-management behavior.
- Initialize checkpoint-owned `nn.Parameter` placeholders with `torch.empty`; do not fabricate meaningful checkpoint contents in model constructors.
- Treat dtype, device placement, VRAM use, offloading, and cleanup as correctness concerns across CPU, CUDA, ROCm, MPS, DirectML, XPU, and NPU paths. Use existing cast, offload, and memory-management helpers at the owning boundary.
- Use existing ComfyUI optimized operations and model-management helpers before writing local kernels. Do not inspect backend implementation identity.
- Nodes follow `INPUT_TYPES`, `RETURN_TYPES`, `FUNCTION`, `CATEGORY`, and the local registration mapping. Nodes translate and delegate; they do not patch model internals or expose pass-through values they do not own. Prefer existing nodes over new compatibility wrappers.
- Do not re-export functions, create empty init files, or write trivial wrappers in the form `a(b): return c(b)`. The sole exception is `__init__.py`, which must re-export `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` from `adapters/comfyui/node_registry` so ComfyUI's custom-node loader can discover the module.

## Data and lifecycle rules

- The supported database filename is `cache.db`.
- Startup schema initialization and in-memory graph loading are allowed.
- Automatic destructive database deletion or rebuild is not allowed. A database rebuild is an explicit operator action and must clearly warn that it clears and repopulates data from ranked-file metadata.
- Runtime loading is offline. Only explicit user-requested model downloads may access the network.
- Keep filesystem, persistence, history, and graph ownership at their proper boundaries. Do not move behavior across layers merely to silence a check.

## Tests and validation

Run commands in the ComfyUI virtual environment. Prefer the narrowest relevant colocated suite first, then run the configured package suite when the change crosses boundaries. Real-data tests are explicit and destructive; never point unit tests at real output, ranked, config, or model directories.

Tests and fakes use temporary directories only. The default package suite is
the configured non-real-data suite; the general command/endpoint contract and
real-data tests require an explicit request. Do not treat a test-only bypass as
production behavior.

For a code change, use this order:

1. Focused pytest suite.
2. `ruff check --select ARG,F401 --target-version py313 .`.
3. `pyright` using the package configuration.
4. Architecture and database/proxy boundary tests.
5. ComfyUI node registration smoke check.

Run broader or real-data validation when the changed behavior requires it. Record meaningful baselines with their command and date; never present an old count as a current result.

For node registration, verify the `NODE_CLASS_MAPPINGS` entry, required
`INPUT_TYPES`, `RETURN_TYPES`, `FUNCTION`, and `CATEGORY` attributes, and the
expected `AestheticScore` mapping. The minimal smoke check is:

```powershell
python -c "import sys; sys.path.insert(0, '..'); from comfyui_image_scorer.adapters.comfyui.node_registry import NODE_CLASS_MAPPINGS; assert 'AestheticScore' in NODE_CLASS_MAPPINGS; print(list(NODE_CLASS_MAPPINGS))"
```

## Editing and review

- Fix root causes with the smallest coherent change.
- Add comments only for non-obvious reasoning.
- Remove dead code when its replacement makes it obsolete.
- Review for crashes, wrong dtype/device behavior, memory regressions, broken model loading, workflow incompatibility, and misleading output.
- Do not commit or create branches unless explicitly requested.
- Keep one coherent behavioral change per commit when commits are requested.
- Use direct commit subjects such as `Fix ...`, `Add ...`, `Support ...`,
  `Remove ...`, `Update ...`, `Make ...`, `Use ...`, or `Revert ...`.
