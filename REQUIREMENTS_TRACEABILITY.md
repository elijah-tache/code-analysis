# REQUIREMENTS_TRACEABILITY.md

## Traceability rules
Every requirement maps to task(s), acceptance criteria, tests, and evidence. On each task completion, Claude replaces `pending` evidence with exact test path, test name, run result, commit and decision entry. Keep unresolved/partial cases explicit. `DECISIONS.md` is the authoritative decisions record.

| Requirement | Definition | Tasks | Acceptance criteria | Verification evidence |
|---|---|---|---|---|
| R01 | Safety: no target execution, bounded safe file discovery | T001, T002, T006, T029, T033 | AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12 | pending |
| R02 | Python parsing and lexical/symbol indexing | T002, T006, T007, T033 | AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12 | pending |
| R03 | Typed persistent graph and fast navigation | T004, T007, T022, T024, T026, T027, T033 | AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12 | pending |
| R04 | Evidence, confidence states and diagnostics | T004, T010, T014, T024, T033 | AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12 | pending |
| R05 | Imports, aliases, re-exports and module resolution | T008, T033 | AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12 | pending |
| R06 | Classes, inheritance, methods, decorators and object sites | T009, T033 | AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12 | pending |
| R07 | References, calls, conservative points-to and dispatch | T011, T012, T014, T015, T033 | AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12 | pending |
| R08 | Def-use and argument/return data flow | T013, T015, T033 | AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12 | pending |
| R09 | Manifest, lock, distribution and environment version modeling | T016, T017, T018, T021, T033 | AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12 | pending |
| R10 | Version-specific API, deprecation and compatibility intelligence | T019, T020, T021, T033 | AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12 | pending |
| R11 | Impact, incremental snapshots and graph diff | T022, T023, T025, T033 | AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12 | pending |
| R12 | Documentation, decisions, tests, security, CI and performance | T001, T003, T005, T015, T028, T029, T030, T031, T032, T033 | AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12 | pending |

## Acceptance criteria to tasks

| Acceptance | Verifying tasks | Status | Evidence |
|---|---|---|---|
| AC-01 | T001, T002, T004, T006, T022, T033 | pending | pending |
| AC-02 | T008, T010, T033 | pending | pending |
| AC-03 | T007, T009, T010, T033 | pending | pending |
| AC-04 | T004, T011, T012, T014, T015, T033 | pending | pending |
| AC-05 | T013, T015, T033 | pending | pending |
| AC-06 | T016, T017, T018, T021, T033 | pending | pending |
| AC-07 | T019, T020, T021, T033 | pending | pending |
| AC-08 | T024, T025, T033 | pending | pending |
| AC-09 | T023, T025, T029, T033 | pending | pending |
| AC-10 | T022, T024, T026, T027, T031, T033 | pending | pending |
| AC-11 | T001, T005, T006, T028, T029, T030, T033 | pending | pending |
| AC-12 | T003, T005, T031, T032, T033 | pending | pending |

## Required verification artifacts

- `tests/fixtures/` contains source trees, expected graph facts, expected uncertainty/diagnostics and dependency metadata per supported environment.
- `tests/` has unit, integration, regression, security and golden suites.
- `benchmarks/` includes dataset generation, measurement harness and reproducible result report.
- `docs/` includes graph schema, API reference, parser support matrix, architecture, security, known limitations, compatibility evidence and usage guide.
- `DECISIONS.md` contains every material choice, alternatives, rationale, verification and related task IDs.
- `tasks.json` records state, blockers, and evidence for each task.

## Change control

When a requirement changes, update `SPEC.md`, impacted tasks, acceptance criteria, tests, this matrix and `DECISIONS.md` together. Never mark a requirement verified solely because code exists. Record failed tests and waived cases explicitly; a waiver requires user approval for mandatory acceptance gates.
