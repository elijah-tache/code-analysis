# IMPLEMENTATION_PLAN.md

## Operating instructions for Claude Code
Read `SPEC.md`, `tasks.json`, `OPEN_QUESTIONS.md`, `REQUIREMENTS_TRACEABILITY.md` and `DECISIONS.md` before making changes. Treat these files as the source of truth. Do not begin blocked tasks. For any decision, first append a dated, numbered entry to `DECISIONS.md` (or append immediately before implementation if exploration was necessary); document alternatives, evidence, tradeoffs, effects and verification. Update task state and traceability **in the same commit** as implementation. Explain every architectural choice, algorithm, unsupported construct and nontrivial tradeoff in human-readable documentation; inline comments explain tricky mechanics, not replace documentation. Never silently expand scope or claim complete static understanding of Python.

## Workflow protocol
1. Validate repository context and inputs; read open questions. Choose documented defaults only for reversible, low-risk decisions. Escalate architecture/security/product decisions flagged `needs_user` and continue independent tasks.
2. For each task: state plan, dependencies, acceptance criteria, expected files, tests, and risk. Add or update a decision record before selecting tools or algorithms.
3. Write failing focused tests/golden fixtures; implement minimal correct behavior; run tests, type checks and lint; validate edge evidence and unknown states.
4. Persist progress in `tasks.json` (status, notes, evidence paths, blocker IDs); update traceability rows and question resolutions. Record deviations and decisions.
5. Commit coherent units to feature branch; use descriptive commit messages and document commit hashes in progress/decisions when available. Never self-merge or push without user authorization. PRs require user-configured remote/permissions.
6. At phase gates: run all relevant tests, publish coverage/performance evidence and known limitations; proceed only if required gates pass.
7. On context reset/reinstallation: reread the five documents plus decisions log, inspect git status/history, rerun relevant checks, select earliest unblocked task by dependencies. Do not assume previous agent memory.

## Architecture (proposed, subject to decision log)
`discovery -> parsing -> scope/bindings -> import resolution -> semantic graph -> type/points-to -> data flow -> dependency metadata -> compatibility facts -> graph persistence -> queries/impact -> CLI/API/viewer`.

Suggested modules: `core/config`, `discovery`, `syntax`, `scopes`, `imports`, `symbols`, `resolution`, `dataflow`, `metadata`, `compat`, `graph/schema`, `graph/store`, `graph/query`, `impact`, `snapshots`, `cli`, `api`, `viewer`, `diagnostics`, `evidence`. Keep extractors pure where possible; use immutable intermediate records and separate analysis from storage. Use stable IDs derived from canonical workspace-relative path + lexical location/qualified name + kind, with collision handling and explicit rules for edits.

## Phase gates
**P0 — Foundation (T001–T005):** agree support matrix, safety boundaries, graph schema, test harness and decision log; gate: parse/index smoke test and deterministic IDs.

**P1 — Structural graph (T006–T010):** scopes, import resolution, classes/functions and source evidence; gate: golden fixtures for imports, symbols, aliases, inheritance and diagnostics.

**P2 — Semantic relationships (T011–T015):** call resolution, points-to, attributes, data flow, uncertainty; gate: positive/negative golden tests including dynamic constructs; report recall/precision on fixture set without misleading general guarantees.

**P3 — Versions and compatibility (T016–T021):** environment model, manifests, installed/artifact metadata, API inventories, deprecations and compatibility findings; gate: versioned offline fixtures and explicit unknown cases.

**P4 — Query and usability (T022–T027):** persistence, snapshots, incremental invalidation, impact traversal, CLI, export and optional UI; gate: large graph can be explored via bounded indexed queries with evidence.

**P5 — Release quality (T028–T033):** performance, security, CI, Docker, docs, traceability and audit; gate: AC-01 through AC-12 verified or explicitly blocked.

## Testing strategy
- Unit: parser, binding scopes, symbol identity, version specifiers, markers, evidence, graph storage.
- Golden: tiny repositories with expected nodes/edges and uncertainty states, covering both supported and deliberately unresolved patterns.
- Integration: multi-package workspace, editable dependency, namespace packages, alias chains, conditional imports, overloads, stubs and versioned dependency fixtures.
- Differential: compare extracted facts with independently hand-authored expected facts; do not execute arbitrary target packages.
- Metamorphic: harmless whitespace edits, rename/move, reorder, import aliases, repeated indexing, environment changes.
- Security: hostile repository and malformed metadata fixtures; indexing must never execute them.
- Performance: reproducible synthetic/consented open-source corpus, hardware and dataset documented, cold vs warm separated.

## Explicit exclusions
No automatic migration suggestions, no AI, no runtime tracing, no executing dependency imports, no guaranteed perfect call graph, no automatic network scraping, no comprehensive dependency solving, no source rewriting. Optional browser viewer is downstream of correctness and query performance.

## Completion report template
For each phase and final delivery: completed task IDs; changed files/commits; acceptance criteria and tests with actual command/results; measured benchmarks; open blockers; unsupported scenarios; links to decision entries; remaining risks; next unblocked task. Avoid vague statements such as “fully mapped” without coverage evidence.
