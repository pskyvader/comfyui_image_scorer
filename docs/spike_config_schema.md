# Spike — `AutoSaveDict` write paths & configuration schema validation (§3.14 #58)

Date: 2026-08-24 · Outcome to be decided at spike review with the user.

## Current mechanics (`core/configuration/settings.py`, mirrored in old stubs)

- `Config` is a `MutableMapping` over `config.json` with two cache dicts:
  `_root_cache` (whole-file dict) and `_sub_cache` (per-section `AutoSaveDict`s).
- Every section accessed via `config["training"]` constructs (once, cached) an
  `AutoSaveDict` wrapping that section **with a save callback that rewrites
  `config.json` on every `__setitem__`/`__delitem__`**.
- Write paths observed in the codebase:
  1. Startup bootstrap: `config["image_root"] = get_output_directory()` in all
     three composition roots (write-back to disk at import time).
  2. Training/HPO flows persisting results into `config["training"]["topN"]`
     (`used_keys`, `best_score`, …) after each run — this is how
     `training_config.json` changes between runs.
  3. Read-modify-write of ranking knobs? None found outside (1)/(2).
  4. `Config.clear()` reloads from disk (cache invalidation only).
- Mutation is therefore **autosave-on-set**, scattered across any code that
  assigns into a section; there is no explicit "save" step and no schema.

## Options

**A. Typed models preserve autosave write-back** — pydantic-settings style
models per section; assignment validates then persists exactly as today.
Keeps current behavior/workflows identical; adds validation; keeps implicit
disk writes on every set.

**B. Load-time-validated / read-only config + explicit save path** — sections
parse into frozen typed models at load; mutation happens through a small
explicit API (e.g., `training_config.update_top_result(...)` → validate →
persist once). Stronger invariant (config immutable during runs), but every
current writer must be converted and any external tooling writing
`config.json` directly stays authoritative only at next load.

## Recommendation

Option B for `prepare`/`ranking`/`vector` (read-heavy, mutated only by
bootstrap) plus a narrow explicit updater for `training` results — i.e., B
with one sanctioned write API. Validation catches malformed user JSON at load
(fail fast per ground rules) instead of mid-run.

## Decision

**Option B** (2026-08-24, user review): load-time-validated read-only config
sections plus one explicit save API (training-results updater). Implement per
the recommendation in a dedicated pass.
