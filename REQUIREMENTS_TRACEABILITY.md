# REQUIREMENTS_TRACEABILITY.md

## Traceability rules
Every requirement maps to task(s), acceptance criteria, tests, and evidence. On each task completion, Claude replaces `pending` evidence with exact test path, test name, run result, commit and decision entry. Keep unresolved/partial cases explicit. `DECISIONS.md` is the authoritative decisions record.

| Requirement | Definition | Tasks | Acceptance criteria | Verification evidence |
|---|---|---|---|---|
| R01 | Safety: no target execution, bounded safe file discovery | T001, T002, T006, T029, T033 | AC-01, AC-11 | **partial (T001 verified 2026-11-12)**: `tests/test_t001.py::TestNonExecution`, `::TestSymlinks`, `::TestNoFollow`, `::TestSizeAndLimits`, `::TestDiagnostics` — 150 passed / 1 skipped (APFS non-UTF-8 name); tester PASS, reviewer APPROVE; D-0015, D-0016, D-0018–D-0023, D-0025–D-0027; commit: see `Task: T001` trailer. Remaining: T002, T006, T029, T033 |
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
| R12 | Documentation, decisions, tests, security, CI and performance | T001, T003, T005, T015, T028, T029, T030, T031, T032, T033 | AC-11, AC-12 | **partial (T001 part verified 2026-11-12; T003 part verified 2026-11-13)**: T001 — `pyproject.toml` (pinned pytest/mypy strict/ruff), `docs/safety-policy.md` (§8 records CI→T030 and benchmark→T028 deferral), `README.md`; D-0017; commit: see `Task: T001` trailer. T003 — `docs/architecture.md` (layers, rules R1–R6) enforced by `tests/test_t003.py::TestImportLayering`; `docs/dependencies.md` (zero runtime deps, license and pin policy) enforced by `::TestDependencyPolicy`; tooling (`Makefile`, ruff families, mypy strict, branch coverage ≥90%, dynamic version, `CHANGELOG.md`, CLI stub `code-analysis`/`python -m code_analysis`) by `::TestToolingConfig`, `::TestPackageMetadata`, `::TestCliStub`; offline wheel build equals `src/` (`::TestWheelContents`); honest editable-install check `scripts/check_install.py` (`::TestInstallCheck`); tester 2026-11-13: 248 passed/1 skipped/1 xfailed, `make check` 96.14% branch; reviewer APPROVE; D-0028–D-0042; commit: see `Task: T003` trailer. Project license undecided (Q13, D-0037) — no license claimed. Remaining: T005, T015, T028–T033 |

## Acceptance criteria to tasks

| Acceptance | Verifying tasks | Status | Evidence |
|---|---|---|---|
| AC-01 | T001, T002, T004, T006, T022, T033 | partial (T001 foundation verified 2026-11-12) | `tests/test_t001.py::TestDiscoveryPositive`, `::TestDeterminism`, `::TestPackages`, `::test_directory_alias_link_does_not_change_canonical_paths` — deterministic multi-package discovery, canonical path + sha256 identity independent of location and symlinks; cross-process fingerprint identical (tester probe). Graph/query parts pending T002, T004, T006, T022, T033 |
| AC-02 | T008, T010, T033 | pending | pending |
| AC-03 | T007, T009, T010, T033 | pending | pending |
| AC-04 | T004, T011, T012, T014, T015, T033 | pending | pending |
| AC-05 | T013, T015, T033 | pending | pending |
| AC-06 | T016, T017, T018, T021, T033 | pending | pending |
| AC-07 | T019, T020, T021, T033 | pending | pending |
| AC-08 | T024, T025, T033 | pending | pending |
| AC-09 | T023, T025, T029, T033 | pending | pending |
| AC-10 | T022, T024, T026, T027, T031, T033 | pending | pending |
| AC-11 | T001, T005, T006, T028, T029, T030, T033 | partial (T001 discovery-level security + determinism verified 2026-11-12) | `tests/test_t001.py::TestNonExecution` (hostile setup.py/side-effect modules never executed, audit hook clean), `::TestSymlinks` (escapes rejected under every policy), `::TestNoFollow` (dir_fd + O_NOFOLLOW, TOCTOU swap, fd leak), `::TestSizeAndLimits`; CI (T030) and 10k-file benchmark (T028) explicitly deferred in `docs/safety-policy.md` §8; residual races recorded in D-0026 for T029 |
| AC-12 | T003, T005, T031, T032, T033 | partial (T003 verified 2026-11-13: decisions logged and linked; open questions tracked) | `DECISIONS.md` D-0028–D-0042 (each with Related/Verification/Supersedes; append-only, `git diff` 0 deletions; D-0030 superseded by D-0040 without edit); `OPEN_QUESTIONS.md` Q13 (license, needs_user), Q14 (iCloud venv layout, needs_user); `tests/test_t003.py::TestT001FollowUps::test_stale_decision_references_removed`; D-0037 needs-user correctly not implemented (no `license` key/classifier, asserted by `::TestDependencyPolicy`); reviewer APPROVE 2026-11-13; commit: see `Task: T003` trailer. Remaining: T005, T031, T032, T033 |

## Required verification artifacts

- `tests/fixtures/` contains source trees, expected graph facts, expected uncertainty/diagnostics and dependency metadata per supported environment.
- `tests/` has unit, integration, regression, security and golden suites.
- `benchmarks/` includes dataset generation, measurement harness and reproducible result report.
- `docs/` includes graph schema, API reference, parser support matrix, architecture, security, known limitations, compatibility evidence and usage guide.
- `DECISIONS.md` contains every material choice, alternatives, rationale, verification and related task IDs.
- `tasks.json` records state, blockers, and evidence for each task.

## Change control

When a requirement changes, update `SPEC.md`, impacted tasks, acceptance criteria, tests, this matrix and `DECISIONS.md` together. Never mark a requirement verified solely because code exists. Record failed tests and waived cases explicitly; a waiver requires user approval for mandatory acceptance gates.
