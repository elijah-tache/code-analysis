# DECISIONS.md — Single authoritative decision log

**Mandatory rule:** Claude must record **every material decision it makes** here, including architecture, dependencies, parsing strategies, scope limits, schema/ID choices, resolution algorithms, uncertainty classification, version sources, performance compromises, security policies, and changes to requirements. No undocumented “obvious” decisions. Small routine coding details can be grouped per task, but any choice affecting behavior, interface, correctness, or maintenance needs an entry. This file is append-only: supersede rather than silently edit earlier entries. Do not confuse proposals with approved decisions.

## Decision entry template

### D-0001 — [short title]
- Date (UTC): YYYY-MM-DD
- Status: proposed | accepted | superseded | rejected | needs-user
- Author/approver: Claude / user where relevant
- Related: requirement IDs, task IDs, question IDs, commits
- Context/problem: ...
- Options considered: ... (at least two meaningful options where feasible)
- Chosen option: ...
- Rationale/evidence: ...
- Tradeoffs, risks, limitations: ...
- Consequences and follow-up work: ...
- Verification: test IDs, benchmark evidence, code references or pending
- Supersedes: D-... (if applicable)

## Initial baseline decisions to validate
These are **proposals**, not silent implementation approvals. Claude must explicitly accept/modify each relevant proposal in numbered entries before implementing it.

- B01: Non-executing, offline-first source analysis with no AI.
- B02: Typed provenance graph with uncertainty and environment-specific edges.
- B03: SQLite-backed indexed persistence behind an adapter as the initial candidate.
- B04: AST-driven core with optional syntax/token or stub support.
- B05: Deterministic snapshots, bounded traversals, no whole-graph render.
- B06: Local versioned artifacts required for claims about third-party API availability; absent evidence is `unknown`.
- B07: User approval required for external network access, security-affecting behavior, and changes to release scope.

## Decision entries

<!-- Claude appends D-0001, D-0002, ... here. -->

### D-0001 — Git branching model and baseline commit
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user (workflow specified in the Stage 1 kickoff instruction) / Claude (orchestrator)
- Related: all tasks; IMPLEMENTATION_PLAN.md "Workflow protocol" step 5
- Context/problem: The repository had a remote (`origin`) but no commits, no `.gitignore` and no branch structure. The autonomous workflow needs a stable branch, an integration branch and isolated per-task branches, plus a committed baseline of the planning documents so that later diffs are reviewable.
- Options considered: (a) single `main` with feature branches; (b) `main` (stable) + `dev` (integration) + `feature/<task-id>-<description>` branches merged into `dev` with non-fast-forward merges, `dev` merged into `main` only on user-approved release; (c) trunk-based with direct commits to `main`.
- Chosen option: (b), as specified by the user.
- Rationale/evidence: Keeps `main` releasable, retains per-task history through merge commits, and matches the user's explicit instruction. A baseline commit on `main` containing only the planning documents, agent/skill configuration and `.gitignore` is required before `dev` can be created without rewriting history.
- Tradeoffs, risks, limitations: Merge commits add history noise; conflicts must be resolved on the feature branch and re-tested before merging. No push/PR until the user authorizes remote operations (`progress.json` config `allow_push`/`allow_pr`, default false).
- Consequences and follow-up work: Every verified task is committed on its feature branch with a `Task: <ID>` trailer and merged `--no-ff` into `dev`; merged local feature branches are deleted after the merge. `progress.json` config records `base_branch: dev`, `stable_branch: main`.
- Verification: `git log --graph` on `dev` after the first task merge; `devstate.py status` reports the task's commits reachable from `dev`.
- Supersedes: none

### D-0002 — Q01: Supported Python syntax range is 3.8–3.14
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user
- Related: Q01; T002, T006; R01, R02; AC-01
- Context/problem: The parser's supported grammar range must be fixed before the support matrix (T002) and parser (T006).
- Options considered: proposed default 3.10–3.13; user-specified 3.8–3.14.
- Chosen option: 3.8–3.14 syntax support. Syntax outside the range, or unsupported by the available parser, must yield a diagnostic, never silent omission (SPEC §3.2).
- Rationale/evidence: User decision.
- Tradeoffs, risks, limitations: The stdlib `ast` module parses only the host interpreter's grammar (development host is CPython 3.12.3). 3.14 syntax (e.g. PEP 750 template strings, PEP 758) is not parsable by a 3.12 `ast`; 3.8-only constructs are a subset of later grammars. How to achieve full-range coverage (multiple interpreters in CI, a version-independent third-party parser, or documented per-host limits with diagnostics) is a technical decision for T002, to be recorded in its own entry.
- Consequences and follow-up work: T002 must publish a per-version matrix stating, for each Python version, what is parsed, under which host interpreter, and the diagnostic emitted otherwise.
- Verification: T002 tests; pending.

### D-0003 — Q02: Browser viewer is optional
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user
- Related: Q02; T027; R03; AC-10
- Context/problem: Whether the browser visualization is mandatory for Stage 1.
- Options considered: mandatory viewer; CLI/API mandatory with optional viewer.
- Chosen option: Not mandatory. CLI and graph API are the required interface; viewer only if core gates pass (SPEC §8).
- Rationale/evidence: User decision.
- Tradeoffs, risks, limitations: T027 may be descoped to a documented optional deliverable without failing Stage 1.
- Consequences and follow-up work: T027 remains in the plan; its absence does not block the release report.
- Verification: n/a.

### D-0004 — Q03: Performance scale and reference machine
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user (proposed default accepted)
- Related: Q03; T028; R12; AC-11
- Context/problem: Hard performance gates need a defined dataset and hardware.
- Options considered: proposed default (10k files / ~1M LOC fixture, publish hardware and observed values); user-supplied reference machine.
- Chosen option: Proposed default. The development host (to be documented with CPU/RAM/OS in the benchmark report) is the reference machine unless the user later specifies another.
- Rationale/evidence: User accepted the default.
- Tradeoffs, risks, limitations: Targets are measured on one machine; results elsewhere will differ.
- Consequences and follow-up work: T028 builds a reproducible synthetic corpus generator and publishes results.
- Verification: T028 benchmark report; pending.

### D-0005 — Q04: Lockfile and manifest coverage priority
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user (proposed default accepted)
- Related: Q04; T017, T018; R09; AC-06
- Context/problem: Which dependency manifest/lock dialects must be complete in Stage 1.
- Options considered: all dialects complete; prioritized subset with adapters and diagnostics.
- Chosen option: `pyproject.toml`, `requirements*.txt` and installed distribution metadata first; lockfiles (`poetry.lock`, `uv.lock`, `pdm.lock`, `Pipfile.lock`) via independent adapters that emit diagnostics for unsupported constructs.
- Rationale/evidence: User accepted the default.
- Tradeoffs, risks, limitations: Lockfile adapters may be partial; completeness must be stated per dialect with fixture coverage (SPEC §4).
- Consequences and follow-up work: T017/T018 document per-format support levels.
- Verification: T017/T018 fixtures; pending.

### D-0006 — Q05: Offline by default; no network metadata sync required
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user (proposed default accepted)
- Related: Q05; T019, T021; R10; AC-07
- Context/problem: Whether the analyzer may fetch package metadata over the network.
- Options considered: opt-in network sync; fully offline with local snapshot import.
- Chosen option: Offline by default; metadata comes from installed dist-info, local wheels/sdists, stubs and user-supplied local snapshots. Network fetching is not required for Stage 1 and, if ever added, remains opt-in and non-executing.
- Rationale/evidence: User accepted the default; matches SPEC §3.3 and B06/B07.
- Tradeoffs, risks, limitations: Release catalogs are only as complete as locally supplied metadata; absence is reported as `unknown`.
- Consequences and follow-up work: No network code in the analyzer; development tooling installs are a separate, user-approved matter (D-0014).
- Verification: security tests assert no network access during indexing; pending.

### D-0007 — Q06: Explicit environment tuple
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user (proposed default accepted)
- Related: Q06; T016, T020; R09, R10; AC-06, AC-07
- Context/problem: Compatibility targets (OS, ABI, architecture, extras, dependency groups).
- Options considered: implicit current platform; explicit environment tuple with current platform as the only default.
- Chosen option: Model an explicit environment tuple (Python version, platform, implementation, ABI/arch, extras, dependency groups, marker values). Default to the current platform only when the user states so; otherwise compatibility for unspecified environments is `unknown`.
- Rationale/evidence: User accepted the default.
- Tradeoffs, risks, limitations: Users must configure environments explicitly for multi-platform answers.
- Consequences and follow-up work: T016 defines the tuple schema and PEP 508 marker evaluation.
- Verification: T016 tests; pending.

### D-0008 — Q07: Permissive licenses only
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user (proposed default accepted)
- Related: Q07; T003; R12; AC-12
- Context/problem: License constraints on third-party parsers, type engines, graph libraries and metadata.
- Options considered: no constraint; permissive-only (MIT/BSD/Apache-2.0/PSF/ISC) with documented alternatives.
- Chosen option: Permissive-only. Every runtime dependency is listed with its license and the alternative considered in T003's decision entry.
- Rationale/evidence: User accepted the default.
- Tradeoffs, risks, limitations: Excludes copyleft libraries even when technically superior.
- Consequences and follow-up work: T003 records the dependency/license table; CI may add a license check.
- Verification: T003 documentation; pending.

### D-0009 — Q08: Impact certainty categories are certain / possible / unknown
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user
- Related: Q08; T025; R11; AC-08
- Context/problem: Which evidence-backed categories distinguish a breaking change from a potential impact.
- Options considered: four categories (certain/likely/possible/unknown) as proposed; three categories (certain/possible/unknown) as chosen by the user.
- Chosen option: Three categories. `certain` requires structural incompatibility proven statically (e.g. removed symbol with a resolved reference); `possible` covers candidate/transitive/behavioral impact; `unknown` covers unresolved or dynamic cases. No `likely` tier.
- Rationale/evidence: User decision; avoids an unfounded probabilistic middle tier (SPEC §3.4).
- Tradeoffs, risks, limitations: Less granularity; users cannot rank `possible` impacts by strength without consulting evidence.
- Consequences and follow-up work: T025 defines the rule set mapping edge kinds/resolution states to categories.
- Verification: T025 golden tests; pending.

### D-0010 — Q09: Single repository, multiple packages, cross-repo-ready design
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user
- Related: Q09; T001, T007; R01, R03; AC-01
- Context/problem: Whether Stage 1 analyzes one repository or graphs spanning repositories.
- Options considered: single workspace with multiple local packages; cross-repository graphs in Stage 1.
- Chosen option: Start with a single repository containing multiple local packages, but design the workspace model so it can scale to cross-repository graphs later (workspace = ordered set of roots with stable per-root identity; IDs namespaced by root).
- Rationale/evidence: User decision.
- Tradeoffs, risks, limitations: Cross-repo features (remote roots, cross-root snapshots) are deferred and not tested in Stage 1.
- Consequences and follow-up work: T001 defines the workspace/root model with this extension point explicitly documented.
- Verification: T001 tests; pending.

### D-0011 — Q10: Analyze supplied stubs/artifacts; unknown if absent
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user (proposed default accepted)
- Related: Q10; T019, T020; R10; AC-07
- Context/problem: Availability of `.pyi` stubs and local wheels for version-specific API analysis.
- Options considered: require artifacts; analyze what is supplied and report `unknown` otherwise.
- Chosen option: Analyze supplied artifacts; report `unknown` when evidence is absent.
- Rationale/evidence: User accepted the default; consistent with B06.
- Tradeoffs, risks, limitations: API availability findings depend on what the user provides.
- Consequences and follow-up work: T019 documents artifact discovery paths and provenance.
- Verification: T019/T021 fixtures; pending.

### D-0012 — Q11: Optimize storage for navigation speed
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user (direction) / Claude (technical interpretation, see T004/T022 entries)
- Related: Q11; T004, T022; R03, R04; AC-01, AC-08
- Context/problem: Whether to store source content in the graph or only locations/hashes and short excerpts.
- Options considered: store full source in the graph; store locations/hashes plus short redacted evidence excerpts; store nothing but locations.
- Chosen option: User direction: "whatever is faster to navigate, not faster to create". Interpretation: the read/query path is optimized over index build time. Storage therefore keeps locations, hashes and denormalized short evidence excerpts alongside edges so navigation and evidence panels need no file reads; full source is not stored (SPEC §3.7 secret/size concerns) unless measurements in T022 show file reads bottleneck navigation, in which case a new entry revisits this.
- Rationale/evidence: User decision on priority; technical interpretation keeps SPEC §3.7 constraints.
- Tradeoffs, risks, limitations: Larger index and slower indexing; excerpts can go stale if files change without reindexing (hashes detect this).
- Consequences and follow-up work: T004 schema includes evidence excerpt fields with redaction rules; T022 indexes for reverse edges and name search.
- Verification: T022/T024 query benchmarks; pending.

### D-0013 — Q12: Local read-only HTTP API acceptable
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user
- Related: Q12; T026; R03; AC-10
- Context/problem: Whether a local HTTP API is acceptable and its access controls.
- Options considered: no HTTP API; loopback-only read-only API disabled by default.
- Chosen option: Acceptable: loopback-only, read-only, disabled unless explicitly enabled, no arbitrary execution, OpenAPI spec published.
- Rationale/evidence: User decision; proposed default accepted.
- Tradeoffs, risks, limitations: Still a network listener; must have no write endpoints and bind only 127.0.0.1.
- Consequences and follow-up work: T026 implements with security tests for binding and method restrictions.
- Verification: T026 tests; pending.

### D-0014 — Development environment and remote git authorization
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user
- Related: T003, T030; all tasks
- Context/problem: No Python test/type/lint tooling is installed on the host, and `origin` (GitHub) is configured but remote operations were unauthorized.
- Options considered: ask per install; blanket authorization for a project-local venv; no remote use.
- Chosen option: User authorized creating a project virtualenv (`.venv/`, git-ignored) and pip-installing whatever the project needs, and authorized use of the git remote (push branches, open PRs) in addition to local git. The analyzer itself remains offline (D-0006). `progress.json` config: `allow_network`, `allow_push`, `allow_pr` = true.
- Rationale/evidence: User statement in chat, 2026-11-12.
- Tradeoffs, risks, limitations: Installed versions are pinned in T003 to keep builds reproducible; pushes never force, never to protected branches directly.
- Consequences and follow-up work: T003 chooses and pins tooling; feature branches may be pushed and PRs opened per the workflow in D-0001.
- Verification: n/a.
