# Spike — configuration schema validation (§3.14 #58)

Date: 2026-08-24 · Decision: Option B, recorded below and since implemented.

The implementation this spike analysed no longer exists. `Config` used to be a
`MutableMapping` over `config.json` with per-section `AutoSaveDict` wrappers that
rewrote the file on every `__setitem__`, so mutation was autosave-on-set with no
schema and no explicit save step. All of that is gone.

## Options considered

**A. Typed models preserve autosave write-back** — pydantic-settings style
models per section; assignment validates then persists exactly as today.
Keeps current behavior/workflows identical; adds validation; keeps implicit
disk writes on every set.

**B. Load-time-validated / read-only config + explicit save path** — sections
parse into frozen typed models at load; mutation happens through a small
explicit API. Stronger invariant (config immutable during runs), but every
current writer must be converted and any external tooling writing `config.json`
directly stays authoritative only at next load.

## Recommendation

Option B for `prepare`/`ranking`/`vector` (read-heavy, mutated only by
bootstrap) plus a narrow explicit updater for `training` results — i.e., B
with one sanctioned write API. Validation catches malformed user JSON at load
(fail fast per ground rules) instead of mid-run.

## Decision

**Option B** (2026-08-24, user review): load-time-validated read-only config
sections plus one explicit save API (training-results updater).

Implemented in `core/configuration/settings.py`: `Config` is a read-only
validated view that parses each section through `SECTION_MODELS` on first
access, and persists only through `set_root` and `save_section`.