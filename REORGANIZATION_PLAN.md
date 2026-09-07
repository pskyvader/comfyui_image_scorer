# Reorganization Plan

This roadmap covers the remaining implementation and documentation work for the image-scorer module. The rules, functionality description, and current structure are maintained separately; this file is the only roadmap that may refer to those three documentation roles.

## Documentation contract

- The agent rulebook owns permanent engineering constraints.
- The README owns functionality, goals, usage, and the general architecture diagram.
- The function index owns the current live file and symbol inventory.
- This plan owns sequencing, dependencies, acceptance criteria, and current remediation status.

Every task below includes **why** the work is required and **how** it must be implemented. Each implementation must preserve the architecture boundaries, ownership rules, and validation discipline in the agent rulebook, and must use the current paths and symbols in the structure index.

The documentation baseline is the module-local Git repository at commit
`c3b8655` (`plan v8`). The ComfyUI root repository is not the history source
for these files; its virtual environment is used only to run validation.

## Documentation tasks

- [ ] **D-01 — Make the four documents independent.**
  - **Why:** duplicated or circular documentation causes agents to follow stale rules and makes current structure unclear.
  - **Rules/structure:** follow the document-ownership and one-way-reference constraints in `AGENTS.md`; use the four current document paths listed in `FUNCTION_INDEX.md`.
  - **How:** keep permanent rules only in `AGENTS.md`, functionality only in `README.md`, live inventory only in `FUNCTION_INDEX.md`, and roadmap work only here. Only this plan may reference the other three.

- [ ] **D-02 — Complete the current structure index.**
  - **Why:** every implementation task needs an accurate path and symbol anchor; missing descriptions hide ownership and make edits speculative.
  - **Rules/structure:** follow the live-tree and current-state documentation rules in `AGENTS.md`; anchor entries to the paths currently listed by the repository structure in `FUNCTION_INDEX.md`.
  - **How:** enumerate every current package, test, configuration, frontend, documentation, and script file. Add concise file descriptions plus reliable public classes, protocols, functions, constants, node mappings, and CLI entry-point descriptions. Do not list planned or removed files.

- [ ] **D-03 — Resolve missing index descriptions before finalization.**
  - **Why:** a blank description is an undocumented structure constraint and prevents agents from knowing what a file owns.
  - **Rules/structure:** follow the ownership, source-of-truth, and no-future-state rules in `AGENTS.md`; name the exact live path or symbol from `FUNCTION_INDEX.md`.
  - **How:** add each missing file or symbol here under “Index description tasks,” state the required explanation, then add that explanation to `FUNCTION_INDEX.md` before marking the task complete.

## Pending implementation tasks

- [ ] **P-01 — Align port annotations.**
  - **Why:** inconsistent protocol shapes allow adapters and implementations to drift, violating the typed-boundary rule.
  - **Rules/structure:** follow strict typing, pure-port, inward-dependency, and ownership rules in `AGENTS.md`; edit the current port and facade paths recorded in `FUNCTION_INDEX.md`.
  - **How:** parameterize bare tuples/dicts in loading ports and reconcile graph port return types with the concrete facade; preserve behavior and validate with focused type and protocol checks.

- [ ] **P-02 — Centralize comparison helpers.**
  - **Why:** pair canonicalization and timestamp ordering must have one owner to keep database cleanup and rebuild collapse deterministic.
  - **Rules/structure:** follow pure-core, dependency-direction, and single-owner rules in `AGENTS.md`; use the current comparison algorithm and persistence paths recorded in `FUNCTION_INDEX.md`.
  - **How:** move the pure helpers into the core-owned utility location, re-import them from repository and ranking code, and preserve sortable timestamp behavior with focused tests.

- [ ] **P-03 — Complete the graph port contract.**
  - **Why:** callers currently rely on graph methods that the port does not declare, weakening dependency inversion and strict typing.
  - **Rules/structure:** follow protocol purity, graph-facade ownership, proxy vocabulary, and strict typing rules in `AGENTS.md`; reconcile the graph port, graph facade, and graph algorithm paths in `FUNCTION_INDEX.md`.
  - **How:** make the graph interface a protocol, add the actually-used graph operations, and resolve `add_comparison` versus `add_link`, graph-stat value types, and cleanup return types. Confirm the facade satisfies it.

- [ ] **P-04 — Return the touched comparison record.**
  - **Why:** reverse-searching mutable history after insertion is fragile and violates narrow ownership of the record being updated.
  - **Rules/structure:** follow narrow ownership, public-interface compatibility, and graph/database-boundary rules in `AGENTS.md`; change only the chain manager and graph facade paths identified in `FUNCTION_INDEX.md`.
  - **How:** have chain application return the created or updated record; stamp its database ID and timestamp directly in the graph facade without changing the public facade behavior.

- [ ] **P-05 — Add one pure history-collapse operation.**
  - **Why:** two-sided JSON histories can duplicate or contradict comparisons; insertion order is nondeterministic and can change ratings.
  - **Rules/structure:** follow pure-domain, deterministic-data, graph-history, and test-isolation rules in `AGENTS.md`; place the operation beside the current comparison algorithm and repository consumers listed in `FUNCTION_INDEX.md`.
  - **How:** normalize candidates, sort by an explicit total order, apply the existing missing-node, self-link, same-direction, and contradiction rules, and return survivors plus counts. Reuse it from cleanup and test each rule.

- [ ] **P-06 — Rebuild history through collapse.**
  - **Why:** inserting every historical row and cleaning afterward causes a second graph rebuild and obscures the intended survivor ordering.
  - **Rules/structure:** follow explicit database lifecycle, graph-facade, filesystem ownership, and deterministic replay rules in `AGENTS.md`; use the current image processor, graph facade, and persistence paths in `FUNCTION_INDEX.md`.
  - **How:** collect validated candidates, skip self-links explicitly, collapse once, insert survivors through `add_link`, rebuild only at the required seed point, replay ratings, and synchronize JSON in survivor order.

- [ ] **P-07 — Remove historical-comparison insertion.**
  - **Why:** after P-06, the legacy insertion path duplicates graph/database ownership and leaves an obsolete API surface.
  - **Rules/structure:** follow dead-code removal, graph/database-facade, and compatibility rules in `AGENTS.md`; verify all current callers and update the affected paths in `FUNCTION_INDEX.md`.
  - **How:** verify zero callers, then remove the facade, repository function, repository method, and protocol declaration. Update the live index afterward.

- [ ] **P-08 — Decide the filesystem boundary.**
  - **Why:** direct filesystem operations in the image processor can bypass the filesystem port and violate infrastructure ownership.
  - **Rules/structure:** follow infrastructure ownership, port purity, and narrow-boundary rules in `AGENTS.md`; inspect the image processor, filesystem port, and file manager paths recorded in `FUNCTION_INDEX.md`.
  - **How:** route persistence and synchronization operations through the port; explicitly document any image-discovery or movement operations retained by the application. Test both delegated and intentionally owned behavior.

- [ ] **P-09 — Replace shared row and payload `Any` types.**
  - **Why:** untyped rows leak infrastructure details and prevent strict domain contracts from catching shape errors.
  - **Rules/structure:** follow strict typing, boundary ownership, and no-bare-container rules in `AGENTS.md`; trace types through the proxy, service, endpoint, and repository paths listed in `FUNCTION_INDEX.md`.
  - **How:** define narrow row/payload types at the owning boundary and thread them outward from proxy data through services and endpoints without using bare dicts as a shortcut.

- [ ] **P-10 — Finish the strict type-check cleanup.**
  - **Why:** remaining diagnostics obscure real interface errors and contradict the typed architecture rule.
  - **Rules/structure:** follow strict typing, model/device correctness, and minimal-change rules in `AGENTS.md`; work only in the current infrastructure, transformation, and optimizer paths named in `FUNCTION_INDEX.md`.
  - **How:** fix the known infrastructure, transformation, and optimizer diagnostics after P-09, checking that no touched file regresses.

- [ ] **P-11 — Remove the test-only filesystem bypass and validate.**
  - **Why:** leaving the bypass disables destructive operations in the real workflow and means the tested path differs from production behavior.
  - **Rules/structure:** follow explicit destructive-operation, test-isolation, validation-order, and node-registration rules in `AGENTS.md`; validate the image processor, tests, and registration paths represented in `FUNCTION_INDEX.md`.
  - **How:** remove it only after focused tests pass, then run lint, typing, architecture, registration, full non-real-data tests, and user-run real-data equivalence checks.

## Required rebuild invariants

- Database and in-memory graph history remain synchronized.
- Comparison IDs remain available to JSON, training, and NPZ consumers.
- Collapse uses an explicit deterministic total order independent of file discovery completion order.
- Replayed ratings and per-file histories remain equivalent modulo fresh IDs.
- The ranking loop's LRU-overflow chain-cover refresh remains intact.
- Focused coverage includes duplicate two-sided histories, contradictions, self-links, missing nodes, equal timestamps, ID uniqueness, and JSON sync.

## Validation

For every task, follow the agent rulebook's narrow-to-broad validation order. Record the command, date, and result for any baseline. Documentation work is complete only when the four files have the correct one-way reference policy, the index describes the live tree, and every missing description has first been recorded as a task here.

## Index description tasks

Add one entry here before finalizing the index for every file or public symbol that lacks a useful description. Each entry must name the path or symbol and state the ownership or behavior the index description must explain.
