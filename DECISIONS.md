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

### D-0015 — Accept B01: non-executing, offline-first, no-AI analysis (T001 enforcement)
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T001); baseline proposal B01 from the user
- Related: B01; R01, R12; T001, T006, T029; AC-01, AC-11; SPEC §3.1, §3.3, §9
- Context/problem: B01 is a proposal that must be explicitly accepted before implementation. T001 is the first code that touches repository contents, so the non-execution boundary has to be concrete here, not only stated.
- Options considered: (a) accept B01 and enforce it structurally in discovery (byte-only reads, `lstat`-based walking, no `exec`/`compile`/`subprocess`/`importlib` use) plus tripwire tests; (b) accept B01 as a documentation-only policy and rely on code review; (c) reject B01 and allow sandboxed execution of `setup.py` for metadata.
- Chosen option: (a). Discovery (`src/code_analysis/discovery/`) opens files with `O_NOFOLLOW`, re-checks `S_ISREG` via `fstat`, reads bytes in bounded chunks for hashing only, and never calls `exec`, `eval`, `compile`, `importlib`, `runpy`, `subprocess`, `os.system`/`spawn*`/`exec*`/`fork`. `tests/test_t001.py` runs discovery over a programmatically generated hostile fixture (a `setup.py` and a module with top-level side effects) with those builtins/functions patched to fail, and asserts the side effect never happens. The analyzer code uses no network at all (D-0006). No AI/LLM components exist in the codebase.
- Rationale/evidence: SPEC §3.1 and §9 require that malicious `setup.py`/pathological source never trigger execution; structural enforcement plus tests is verifiable, documentation alone is not.
- Tradeoffs, risks, limitations: Tripwire tests patch Python-level entry points only; they cannot intercept native code paths. Later tasks that parse source (T006) must keep using `ast.parse` (parse-only) and never `compile(..., 'exec')` followed by execution; this entry applies to them too.
- Consequences and follow-up work: `docs/safety-policy.md` documents the boundary and the enforcement. T029 (security suite) extends the hostile fixture corpus. Any change to this policy is `needs-user` (see D-0016).
- Verification: `tests/test_t001.py::TestNonExecution` (hostile fixture, tripwires, no `.pyc`/sentinel written).
- Supersedes: none (accepts proposal B01)

### D-0016 — Accept B07: user approval required for network, security-affecting behavior and scope changes
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T001); baseline proposal B07 from the user
- Related: B07; R01, R12; T001; AC-11; D-0006, D-0014
- Context/problem: T001 defines the safety policy settings (symlink policy, size cap, traversal limits, exclusions). Those are security-affecting, so the approval rule in B07 must be made concrete for them.
- Options considered: (a) accept B07 as-is and treat relaxation of any safety default (following symlinks outside a root, unbounded sizes/limits, network access in analyzer code) as `needs-user` decisions; (b) accept B07 only for network access and allow Claude to change local safety defaults autonomously.
- Chosen option: (a). Tightening a safety default is a normal recorded decision; loosening one (or adding any new code path that follows symlinks outside a root, executes target content, or performs network I/O inside the analyzer) requires a `needs-user` entry before implementation. The already-granted approvals are limited to pip installs into `.venv/` and git remote use (D-0014) and do not extend to analyzer runtime behavior.
- Rationale/evidence: SPEC §3.1/§3.7 and B07; keeps security posture changes visible and user-controlled.
- Tradeoffs, risks, limitations: Slower iteration if a later task needs a relaxed default; accepted.
- Consequences and follow-up work: `WorkspaceConfig` deliberately has no option that follows symlinks outside a root; escaping links are always rejected with a diagnostic (D-0020).
- Verification: `tests/test_t001.py::TestSymlinks` asserts escapes are rejected under every policy.
- Supersedes: none (accepts proposal B07)

### D-0017 — Package name, layout and pinned development tooling (minimal skeleton for T001)
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T001)
- Related: R12; T001, T003; AC-11, AC-12; D-0008, D-0014
- Context/problem: T001 needs an importable, type-checked, linted package to host the config and discovery modules. T003 owns the final architecture/dependency decisions, so this skeleton must be minimal and clearly marked as provisional where appropriate.
- Options considered: Package name `code_analysis` (matches the repository and project name) vs `codeimpact`/`pygraph` (shorter but not matching the project); src layout (`src/code_analysis/`) vs flat layout; build backend `setuptools` (MIT, ubiquitous) vs `hatchling` (MIT, newer); dev tools declared as a PEP 735 `[dependency-groups]` group vs `[project.optional-dependencies]`.
- Chosen option: Distribution `code-analysis`, import package `code_analysis`, src layout, PEP 621 `pyproject.toml` with `setuptools>=69` backend, `requires-python >= 3.12` (the analyzer *runtime*; the *parsed syntax* range 3.8–3.14 is a separate matter, D-0002). Dev tooling pinned exactly to what is installed in `.venv/`: `pytest==9.2.0`, `mypy==2.4.1`, `ruff==0.17.5` (all MIT), in `[dependency-groups] dev`. Zero runtime dependencies. mypy runs in `--strict` mode with `mypy_path = src`; ruff with rule sets E, W, F, I, B, UP, N, SIM, RUF at line length 100; pytest uses `pythonpath = ["src"]` and `testpaths = ["tests"]` with `tests/fixtures` excluded from collection, type checking and linting (fixture trees are *data*, never imported).
- Rationale/evidence: src layout prevents accidental imports of the uninstalled tree and mirrors the SPEC's "installable package" deliverable; setuptools is the lowest-risk backend; pinning exactly keeps `D-0014` reproducibility; strict typing is required by the project instructions.
- Tradeoffs, risks, limitations: T003 should revisit: the build backend (setuptools vs hatchling), whether `requires-python` should be lowered to 3.10/3.11 for users, the ruff rule set (e.g. adding `PTH`, `S`, `ANN`), coverage tooling, and the dependency/license table. Nothing in T001 depends on those choices.
- Consequences and follow-up work: `.venv/bin/pip install -e .` installs the package; `pytest`, `mypy` and `ruff check .` run from the repository root with no arguments.
- Verification: `.venv/bin/pytest -q`, `.venv/bin/mypy --strict src tests`, `.venv/bin/ruff check .` (results in the T001 developer report).
- Supersedes: none

### D-0018 — Workspace configuration model: ordered roots, root IDs and canonical workspace paths
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T001)
- Related: R01; T001, T004, T007, T008; AC-01; D-0010, D-0012; IMPLEMENTATION_PLAN "Architecture" (stable IDs from canonical workspace-relative path)
- Context/problem: D-0010 requires a workspace that is an ordered set of roots with stable per-root identity so that cross-repository graphs can be added later without a schema change. T001 must define that model and the canonical path every later ID derives from.
- Options considered: Root identity: (a) user-supplied or name-derived short ID string; (b) hash of the absolute path (stable only while the checkout location is stable); (c) positional index (breaks when roots are reordered). Canonical path: (a) `"<root_id>:<posix-relative-path>"`; (b) `"<root_id>/<relative>"` (ambiguous with a real directory named like a root); (c) absolute paths (not portable, leak machine-specific paths into IDs). Root paths: require absolute vs resolve relative to the CWD.
- Chosen option: `WorkspaceRoot(root_id, path, kind=RootKind.LOCAL_DIRECTORY)` in `code_analysis.core.config`. `root_id` matches `^[a-z0-9][a-z0-9_.-]{0,63}$`, is unique within the workspace and defaults to a sanitized directory name (`WorkspaceRoot.from_path`). `path` must be absolute; it is resolved (`Path.resolve(strict=True)`) at construction so symlinked roots have one canonical real path, and must be an existing directory. Roots may not overlap (one inside another) because a file would otherwise belong to two roots. `WorkspaceConfig(roots, include_patterns, exclude_patterns, safety)` is a frozen dataclass validated in `__post_init__`, raising `ConfigError` with a message naming the offending field/value. The canonical workspace path of a file is `f"{root_id}:{relative_posix_path}"` (`SourceFile.workspace_path`); the colon cannot appear in a root ID so the first colon is an unambiguous separator. `RootKind` has one member today; remote/cross-repository roots become new members plus optional fields with defaults, i.e. no breaking schema change.
- Rationale/evidence: Explicit, user-visible root IDs survive checkout relocation (needed for snapshot diffing, SPEC §6.11) and reorderings; directory-name defaults make the single-repo case zero-config while still being namespaced per D-0010.
- Tradeoffs, risks, limitations: A directory-name-derived ID changes if the user renames the checkout directory; users who need stability across renames must pass an explicit `root_id`. Overlapping roots are rejected rather than de-duplicated. Workspace-level include/exclude patterns apply to every root (per-root overrides can be added as optional fields later).
- Consequences and follow-up work: T004 derives node IDs from `workspace_path` (+ kind + lexical location). T024's CLI must absolutize user-supplied root paths before building the config.
- Verification: `tests/test_t001.py::TestConfig` (valid/invalid IDs, duplicates, overlap, missing/relative roots, limits, patterns).
- Supersedes: none

### D-0019 — Include/exclude pattern syntax: gitignore-style subset implemented with the standard library
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T001)
- Related: R01; T001, T024; AC-01; D-0008; SPEC §3.7 ("ignore configured exclusions"), §4
- Context/problem: Users express exclusions in gitignore terms. The engine needs a deterministic, documented matcher. The `pathspec` library (present in `.venv/` only as a transitive dependency of mypy) implements full gitignore semantics but is licensed MPL-2.0, which is outside the permissive-only rule of D-0008.
- Options considered: (a) depend on `pathspec` (complete semantics; MPL-2.0, excluded by D-0008); (b) plain `fnmatch` on basenames (too weak: no anchoring, no `**`); (c) a documented gitignore-style subset translated to `re` patterns in `code_analysis.core.patterns` with no dependency.
- Chosen option: (c). Semantics (documented in `docs/safety-policy.md`): patterns are matched against the root-relative POSIX path; a pattern containing `/` is anchored at the root (leading `/` optional), a pattern without `/` matches the basename at any depth; `*` matches within one path segment, `?` one character, `[...]` a character class, `**` zero or more segments; a trailing `/` restricts the pattern to directories. Excluded directories are pruned (nothing beneath them is visited). Negation (`!`), escaping (`\`) and comment lines are *not* supported and are rejected by configuration validation with a clear error, as are absolute patterns and `..` segments. Include patterns default to `("**/*.py", "**/*.pyi")`; default excludes are only entries that are never project source: `.git`, `.hg`, `.svn`, `__pycache__`, `.venv`, `venv`, `.tox`, `.nox`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `node_modules`, `*.egg-info`. `build/` and `dist/` are deliberately not excluded by default because projects may have real packages with those names; users add them explicitly.
- Rationale/evidence: Keeps the runtime dependency-free and license-clean; the subset covers the exclusions seen in practice while every unsupported construct fails loudly instead of silently matching differently from git.
- Tradeoffs, risks, limitations: Users cannot re-include a path beneath an excluded directory. Matching is case-sensitive even on case-insensitive filesystems (deterministic across platforms).
- Consequences and follow-up work: T024 (CLI) may add negation if needed, as a new entry with tests. If git-exact semantics are ever required, re-evaluate a permissively licensed implementation in a new entry.
- Verification: `tests/test_t001.py::TestPatterns`.
- Supersedes: none

### D-0020 — Symlink policy: never follow by default, optional within-root following, escapes always rejected
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T001)
- Related: R01; T001, T029; AC-11; D-0016; SPEC §6.1, §9 ("symlink escape")
- Context/problem: Symbolic links can point outside the workspace (secrets, system files), create cycles, or alias the same file under several paths. Discovery must be safe and deterministic in all three cases.
- Options considered: (a) never follow symlinks (simplest, safest; loses legitimately linked in-tree packages); (b) follow only links whose real target is inside the same root, with cycle detection; (c) follow all links (rejected: escapes the trust boundary).
- Chosen option: `SymlinkPolicy.NEVER` as the default and `SymlinkPolicy.WITHIN_ROOT` as the only alternative; (c) does not exist as an option. Under both policies the link target is classified with `os.path.realpath` (no content is read): a dangling link yields `symlink_target_missing`; a target outside the root's real path yields `symlink_escapes_root` (warning, never followed); under `NEVER` an in-root target yields `symlink_not_followed` (info); under `WITHIN_ROOT` an in-root directory target is traversed under the link's logical path unless its real path was already visited (`symlink_cycle`), and an in-root file target is hashed under the link's logical path. The walk itself uses `os.scandir` with `follow_symlinks=False` for every type check, so nothing is ever traversed through a link by accident. Files are opened with `O_NOFOLLOW` and re-checked with `fstat` (regular file, size) to close the lstat/open race.
- Rationale/evidence: SPEC §9 requires symlink-escape tests; D-0016 forbids any option that leaves the root.
- Tradeoffs, risks, limitations: Under `WITHIN_ROOT` the same content can appear under two logical paths; both are reported (identical hashes make this visible). Hard links are not detectable without inode tracking and are treated as ordinary files. On platforms without `O_NOFOLLOW` the flag is omitted (Windows); the `lstat` check still applies.
- Consequences and follow-up work: T029 adds more hostile layouts (deep link chains, links to devices).
- Verification: `tests/test_t001.py::TestSymlinks`.
- Supersedes: none

### D-0021 — File size cap, traversal bounds, chunked SHA-256 hashing and no content retention
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T001)
- Related: R01; T001, T004, T006, T023, T028; AC-11; D-0012; SPEC §3.6, §3.7, §6.1, §9 ("huge files")
- Context/problem: Discovery must be bounded in memory and time on hostile or huge trees, and must give later stages a stable identity basis (D-0012: hashes and locations, not content).
- Options considered: Size cap default 1 MiB (too small for some generated modules such as large `_pb2.py`) vs 2 MiB vs 10 MiB (lets single files dominate parse time); hashing with SHA-256 vs BLAKE2b (faster, less universally recognized) vs MD5 (not collision resistant); whole-file read vs chunked; bounds expressed as one number vs separate knobs.
- Chosen option: `SafetyPolicy(max_file_size_bytes=2 MiB, symlink_policy=NEVER, limits=TraversalLimits(max_files=100_000, max_depth=64, max_entries=2_000_000))`, all configurable and validated (> 0). Size is checked from `lstat` before opening *and* enforced while reading (at most `cap + 1` bytes are consumed), so growing files or misreported sizes cannot bypass it; oversized files yield `file_too_large` and are not hashed. Non-regular files (FIFOs, sockets, devices) are skipped as `not_regular_file` before any `open`, so discovery can never block on them. Content hash is hexadecimal SHA-256 over the raw bytes (no newline/encoding normalisation) computed in 64 KiB chunks; the bytes are discarded afterwards and are never stored in `SourceFile`. `max_files` counts accepted source files; `max_entries` counts every directory entry examined; `max_depth` counts nesting below the root. Hitting any bound emits a `limit_reached` diagnostic (error severity), sets `DiscoveryResult.truncated = True`, and stops the walk deterministically (sorted traversal order), so the truncated result is itself reproducible.
- Rationale/evidence: SHA-256 is what SPEC §5.3 ("file hashes") and lockfile ecosystems use, making hashes comparable with other tooling; 2 MiB admits virtually all hand-written and most generated Python while keeping per-file parse cost bounded; separate knobs let the CLI expose them individually.
- Tradeoffs, risks, limitations: Legitimate files over the cap are not analyzed (visible as diagnostics, overridable); the 10k-file benchmark fixture (T028) must stay under `max_files` or raise it explicitly.
- Consequences and follow-up work: T006 will re-read file bytes for parsing and should compare against `SourceFile.sha256` to detect changes between discovery and parse; T023 uses the hash for incremental invalidation.
- Verification: `tests/test_t001.py::TestSizeAndLimits`, `TestDeterminism`.
- Supersedes: none

### D-0022 — Discovery diagnostics ("no silent omission") and package identification semantics
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T001)
- Related: R01, R04; T001, T008, T010; AC-01, AC-02; SPEC §3.2, §3.4, §6.1
- Context/problem: Every skipped or rejected item must be visible, but a 1M-LOC repository also contains vast numbers of non-Python files; per-file records for all of them would dwarf the useful output. Package identification must not over-claim: whether a directory without `__init__.py` is a namespace package depends on the import search path, which discovery does not know.
- Options considered: Diagnostics: (a) a record for every non-source file; (b) records for every *source candidate* that is skipped plus aggregate counts for files outside the include patterns; (c) counts only. Packages: (a) assert namespace packages for any `__init__`-less directory; (b) report them as candidates with the observed facts and leave the decision to import resolution.
- Chosen option: Diagnostics (b): a `Diagnostic(code, severity, root_id, path, message)` is emitted for every excluded directory (one record; the subtree is pruned), every excluded/oversized/unreadable/non-regular/invalid-name source candidate, every symlink (classified per D-0020), every depth/limit event and every unavailable root; files that merely do not match the include patterns are counted in `DiscoverySummary.ignored_files`. Codes are a `StrEnum` (`DiagnosticCode`) so they are stable strings in JSON. Messages contain paths and numbers only, never file content (SPEC §3.7). Packages (b): a `PackageInfo(root_id, relative_path, kind, has_init_py, has_init_pyi, importable_name)` is produced for every directory that directly contains a source file or a package directory; `kind` is `REGULAR` only when `__init__.py` is present, otherwise `NAMESPACE_CANDIDATE`; `importable_name` records whether the directory name is a valid non-keyword identifier. The root directory itself is reported only when it contains `__init__.py` (relative path `.`). Discovery does not compute dotted module names.
- Rationale/evidence: Meets "never a silent omission" with bounded output; keeps uncertainty explicit per SPEC §3.4.
- Tradeoffs, risks, limitations: Users wanting to know *which* files were ignored by include patterns must widen the patterns or inspect the tree; this can be added as an opt-in verbose mode later.
- Consequences and follow-up work: T008 (import resolution) decides which namespace candidates are real packages given the search roots; T010 maps `Diagnostic` into graph diagnostic nodes.
- Verification: `tests/test_t001.py::TestDiagnostics`, `TestPackages`.
- Supersedes: none

### D-0023 — Hostile fixture is generated at test time; tripwire guards for non-execution tests
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T001)
- Related: R01, R12; T001, T029; AC-11; D-0015
- Context/problem: The non-execution test needs a `setup.py` and a module with top-level side effects. Committing such files under `tests/fixtures/` means a stray `pip install` or import from inside that directory would run them.
- Options considered: (a) commit the hostile files as fixtures; (b) generate them into `tmp_path` from string templates in the test module; (c) commit them with a non-`.py` extension and rename at test time.
- Chosen option: (b) for hostile content; (a) for the benign multi-package fixture (`tests/fixtures/t001_workspace/`), which is excluded from pytest collection, mypy and ruff so it is never imported by tooling. Non-execution tests additionally install tripwires (monkeypatched `exec`, `eval`, `compile`, `subprocess.Popen`, `os.system`, `os.posix_spawn`/`spawnv`/`execv`/`fork`, `importlib.import_module`, `runpy.run_path`, and a `__import__` that refuses modules not already loaded) for the duration of discovery, and assert the sentinel file is absent and no `__pycache__` was created in the fixture.
- Rationale/evidence: The side effect must be observable if it ever occurs (sentinel) and the mechanisms by which it could occur must be fenced (tripwires).
- Tradeoffs, risks, limitations: Tripwires are Python-level only (see D-0015). Symlink fixtures are also created at test time because git does not reliably preserve them on all platforms.
- Consequences and follow-up work: T029 can promote the generator into a reusable hostile-corpus helper.
- Verification: `tests/test_t001.py::TestNonExecution`.
- Supersedes: none

### D-0024 — Amend D-0014: development-time network use is allowed whenever needed
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: user (chat, 2026-11-12) / Claude (orchestrator)
- Related: D-0014, D-0006; all tasks
- Context/problem: D-0014 authorized network access only for pip installs. The user broadened this: subagents may use the network whenever needed during development (documentation, PEPs, package metadata, license texts). An earlier in-place note on D-0014 violated the append-only rule and was reverted (reviewer finding R5 on T001).
- Options considered: keep pip-only authorization; allow any development-time network use.
- Chosen option: Any development-time network use is allowed. Unchanged: analyzer code performs no network I/O by default (D-0006) and never executes analyzed target code (D-0015).
- Rationale/evidence: User instruction in chat; recorded in `progress.json` config `allow_network_dev`.
- Tradeoffs, risks, limitations: None for the product; development reproducibility relies on pinned dependency versions (D-0017).
- Consequences and follow-up work: Agent briefs state this authorization.
- Verification: n/a.
- Supersedes: D-0014 (partial: network scope only)

### D-0025 — Symlink policy revised: directory links are never traversed; exclusions precede resolution; within-root check precedes existence check (supersedes D-0020)
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T001 fix round 2); reviewer findings R1, R2, R8, R9
- Related: R01; T001, T008, T029; AC-01, AC-11; D-0016, D-0018, D-0020; SPEC §3.6 (determinism), §3.7 (exclusions ignored entirely), §5.3 (stable IDs), §9
- Context/problem: D-0020 let `SymlinkPolicy.WITHIN_ROOT` traverse an in-root directory link under the link's logical path and de-duplicated every directory by real path. With `pkg -> src/pkg` the alphabetically earlier link was entered first, the real `src/pkg` was then reported as a `symlink_cycle`, and the canonical path of real files (the stable-ID basis, SPEC §5.3) depended on whether a link existed elsewhere in the root. Separately, exclusions were applied only after a link was resolved and `stat`-ed (so `.venv -> ~/.virtualenvs/x` produced a `symlink_escapes_root` warning and an outside `stat`), the existence check ran before the within-root check (leaking existence of outside paths), and non-candidate special files produced warnings.
- Options considered: (i) never traverse in-root *directory* links; report them with a distinct diagnostic naming the real relative path (orchestrator-preferred; canonical paths become link-independent by construction). (ii) keep traversal but prefer the real path: skip a link whose target will be reached through real components and de-duplicate only on true cycles (requires knowing the future of the walk or a two-pass scan; still reports aliased content twice). (iii) drop `WITHIN_ROOT` entirely (loses legitimately linked single files such as `tests/conftest.py -> ../conftest.py`).
- Chosen option: (i). Under every policy a link is processed in this fixed order: exclusion of the link's own path (matched with `is_dir=True`, i.e. directory-only patterns also match an unresolved link whose type is unknown) → `excluded_by_pattern`, nothing resolved; `realpath` outside the root → `symlink_escapes_root` without any `stat` of the target; in-root target missing/looping (`ENOENT`, `ENOTDIR`, `ELOOP`) → `symlink_target_missing`; `NEVER` → `symlink_not_followed`. Under `WITHIN_ROOT` a directory target is *never* entered: `symlink_cycle` (info) if the target is an ancestor of the link's own directory, otherwise the new code `symlink_alias` (info) whose message names the real root-relative path; a file target is first checked against the exclusions along its real path (`excluded_by_pattern` if any ancestor or the file matches) and otherwise hashed under the link's logical path in addition to its own real path. Only real directories are traversed, so the real-path de-duplication set is gone. Special files (sockets, FIFOs, devices) that do not match an include pattern are only counted in `ignored_files`; only source candidates get `not_regular_file`.
- Rationale/evidence: Canonical workspace paths must be a pure function of the real tree (SPEC §3.6/§5.3; IMPLEMENTATION_PLAN "stable IDs from canonical workspace-relative path"); option (i) makes that true by construction and is testable by adding/removing a link. Applying exclusions before resolution is what SPEC §3.7 ("ignore configured exclusions entirely") requires. Keeping file-link following preserves a useful, bounded meaning for `WITHIN_ROOT`: the real file keeps its own canonical path, and the link's own path is a genuine entry of the tree.
- Tradeoffs, risks, limitations: Packages only reachable through a directory link (e.g. a root-level `pkg -> src/pkg` with `src` outside the search path) must be resolved by T008 using the `symlink_alias` diagnostic rather than by discovery; a project that *only* has such links will see its package under `src/pkg`. Files aliased through a file link appear twice (identical hashes). Directory-only exclusion patterns match links of any type (conservative; visible as a diagnostic).
- Consequences and follow-up work: `docs/safety-policy.md` §3, §4.1, §6 rewritten; `DiagnosticCode.SYMLINK_ALIAS` added (`symlink_alias`); T008 may consume `symlink_alias` diagnostics when building search paths; T029 adds hostile link corpora.
- Verification: `tests/test_t001.py::TestSymlinks` (`test_directory_alias_link_does_not_change_canonical_paths` under both policies, `test_excluded_symlink_is_not_resolved` with a recording `realpath`, `test_dangling_link_to_outside_is_reported_as_escape` with a recording `stat`, `test_file_link_into_excluded_directory_is_not_followed`, revised `test_in_root_symlinks_followed_under_within_root_policy`), `TestSizeAndLimits::test_non_included_special_file_is_only_counted`.
- Supersedes: D-0020 (symlink traversal and de-duplication rules; the policy enum, default and "escapes always rejected" rule are unchanged)

### D-0026 — Descriptor-relative traversal (`dir_fd` + `O_DIRECTORY|O_NOFOLLOW`) to close the directory lstat/open race
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T001 fix round 2); reviewer finding R3
- Related: R01, R12; T001, T029; AC-11; D-0015, D-0020, D-0025; SPEC §3.1, §9
- Context/problem: D-0020 claimed the lstat/open race was closed, which was only true for regular files. A directory classified with `follow_symlinks=False` could be replaced by a symlink before `os.scandir(path)` ran, and `scandir` would follow it — potentially out of the root.
- Options considered: (a) open every directory with `os.open(path, O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)` by absolute path and list it with `os.scandir(fd)` (closes the final-component race only); (b) additionally open each child directory and file *relative to the parent's descriptor* (`dir_fd`) so no path component between root and entry can be swapped (full fix; descriptors open = depth); (c) document the race as a known limitation for T029 without code changes.
- Chosen option: (b) where the platform supports it (`os.open`/`os.stat` in `os.supports_dir_fd`, `os.scandir` in `os.supports_fd`, `O_DIRECTORY` and `O_NOFOLLOW` present — all POSIX), falling back to (a)-style absolute paths with `O_NOFOLLOW` elsewhere (`_FD_TRAVERSAL`). The DFS keeps one frame per open directory (`_Frame`: descriptor, relative path, depth, pending child names in sorted order); a child is opened with `os.open(name, O_DIRECTORY|O_NOFOLLOW, dir_fd=parent_fd)` *when it is entered*, and files are `lstat`-ed/opened via `dir_fd` as well. A swapped entry fails with `ELOOP`/`ENOTDIR` and is reported as `unreadable`. Descriptors are closed when a frame is popped and in a `finally` block on truncation, so at most `max_depth + 1` are open at once and none leak.
- Rationale/evidence: Verified on macOS that `os.open("dlink", O_DIRECTORY|O_NOFOLLOW, dir_fd=fd)` fails with `ENOTDIR` and `os.open("lnk.py", O_NOFOLLOW, dir_fd=fd)` with `ELOOP`; the DFS order and all previous results are unchanged (the full suite and the fallback-mode comparison test pass).
- Tradeoffs, risks, limitations: Residual races remain and are documented in `docs/safety-policy.md` §4.2 for T029: a file link followed under `WITHIN_ROOT` is opened by its resolved absolute path (a *component* swap is undetected; the final component still has `O_NOFOLLOW`); the fallback mode (Windows) only protects the final component; `realpath` is not atomic with the later `stat` of an in-root target. The per-frame pending-name lists hold at most the directory names of each ancestor level (bounded by `max_entries`).
- Consequences and follow-up work: `walk.py` restructured around `_Frame`/`_descend`; `_hash_regular_file(path, cap, *, dir_fd=None)`. T029 should add a hostile-corpus test for the residual file-link component race if a deterministic reproduction is possible.
- Verification: `tests/test_t001.py::TestNoFollow` (`test_directory_swapped_for_link_after_classification_is_not_followed`, `test_hash_refuses_symlink_by_path`, `test_hash_refuses_symlink_relative_to_dir_fd`, `test_no_descriptor_leak_even_when_truncated`, `test_path_fallback_matches_descriptor_traversal`); mutation runs removing `O_NOFOLLOW` from file opens (2 tests fail) and from directory opens (1 test fails).
- Supersedes: D-0020 (the "race is closed" claim; now precise about what is and is not closed)

### D-0027 — Discovery result fingerprint algorithm and JSON shape
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T001 fix round 2); reviewer request
- Related: R01; T001, T004, T010, T023, T024; AC-01; D-0012, D-0018, D-0021, D-0022; SPEC §3.6, §5.4 ("JSON-compatible stable structures")
- Context/problem: `DiscoveryResult.content_fingerprint()` and `to_dict()` existed without a recorded decision on what they commit to.
- Options considered: Fingerprint over (a) the sorted `(workspace_path, sha256)` pairs of accepted files only; (b) the full `to_dict()` serialization including diagnostics and counters (changes whenever a diagnostic message is reworded); (c) a hash of hashes only, without paths (misses renames). Serialization: hand-written `to_dict()` with explicit keys vs. `dataclasses.asdict` (leaks enum objects and makes field order an accident).
- Chosen option: (a): SHA-256 over, for each file in result order, `workspace_path` UTF-8, a NUL byte, the lowercase hex `sha256`, a newline. It is a *content* fingerprint of the discovered sources (what T023 needs for incremental invalidation and what SPEC §6.11 snapshot diffing compares), not of the diagnostics. `to_dict()` returns `{"files": [...], "packages": [...], "diagnostics": [...], "summary": {...}}` with explicit, stable keys (`root_id`, `relative_path`, `workspace_path`, `kind`, `size_bytes`, `sha256`; `has_init_py`, `has_init_pyi`, `importable_name`; `code`, `severity`, `path`, `message`; summary counters and `truncated`), enums as their string values, lists in result order.
- Rationale/evidence: Paths plus hashes capture both renames and edits; excluding diagnostics keeps the fingerprint stable across wording changes and across platform-specific OS error strings.
- Tradeoffs, risks, limitations: Changing the exclusion configuration changes the fingerprint (intended: a different set of sources). Adding fields to `to_dict()` is backward compatible; renaming/removing keys is a schema change that needs a new entry and a version bump in T010/T024.
- Consequences and follow-up work: T024 (CLI/JSON output) and T010 (graph store) consume `to_dict()`; T023 uses `content_fingerprint()`.
- Verification: `tests/test_t001.py::TestDeterminism` (`test_two_runs_are_equal`, `test_fingerprint_independent_of_absolute_location`, `test_fingerprint_changes_with_content`), `TestDiscoveryPositive::test_to_dict_is_json_serializable_and_stable`.
- Supersedes: none

### D-0028 — Package architecture: layered pipeline, module layout and enforced import rules
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T003)
- Related: R03, R12; T003, T002, T004, T006–T027; AC-12; D-0010, D-0012, D-0015, D-0017, D-0018; SPEC §5.4, §6, §8, §11; IMPLEMENTATION_PLAN "Architecture"
- Context/problem: The plan proposes a pipeline and a list of module names but nothing fixes where immutable records live versus storage, which layer may import which, or how the rule is kept true as fifteen more tasks add code. T001 created only `core` and `discovery`.
- Options considered: (a) flat package with naming conventions and prose only; (b) layered subpackages with a numbered dependency rule written in `docs/architecture.md` and enforced by an `ast`-based test over every module in `src/`; (c) split analysis and storage into separate distributions (strongest boundary, but premature for one small team and one package); (d) adopt the `import-linter` dev tool (BSD-2) with a contracts file (another tool and config format for a rule that fits in one test).
- Chosen option: (b). Layers, lowest first, matched by longest dotted prefix under `code_analysis`: 0 `foundation` = `core`; 1 `records` = `graph.schema`, `evidence`, `diagnostics`; 2 `input` = `discovery`, `syntax`; 3 `structure` = `scopes`, `imports`, `symbols`; 4 `semantics` = `resolution`, `dataflow`; 5 `dependency` = `metadata`, `compat`; 6 `persistence` = `graph` (store, migrations); 7 `queries` = `graph.query`, `impact`, `snapshots`; 8 `interfaces` = `cli`, `api`, `viewer`, `__main__`. Rules: R1 a module imports only its own or a lower layer; R2 no module imports a private (underscore-prefixed) module or name from another layer package; R3 absolute imports only; R4 every module under `src/code_analysis` must be mapped to a layer (an unmapped package fails the test, forcing an architecture entry); R5 third-party imports in `src/` are limited to the declared runtime dependencies (D-0029); R6 `code_analysis/__init__.py` imports no subpackage (importing the package stays side-effect free and cheap). `graph.schema` is deliberately in the records layer: it holds immutable node/edge/evidence dataclasses, ID derivation and the schema version and performs no I/O, so analysis stages can produce graph records without importing storage ("analysis separated from storage"). Stub packages created now, documented and empty: `syntax` (parser boundary), `graph` (storage boundary) and `cli` (interface; see D-0036). Other packages are created by their owning task and added to the layer map in the same change.
- Rationale/evidence: An enforced rule is the only kind that survives autonomous multi-task development; `ast` parsing of our own source is already the pattern used by `tests/test_t001.py` for the no-execution self-check, needs no dependency, and runs in milliseconds.
- Tradeoffs, risks, limitations: Longest-prefix mapping means `graph/__init__.py` (layer 6) may not re-export `graph.query` (layer 7); interfaces import `code_analysis.graph.query` directly. Same-layer imports are allowed (e.g. `impact` ↔ `snapshots`), so cycles inside a layer are possible; keep them out by review. The rule checks static imports only; dynamic imports are forbidden anyway (D-0015).
- Consequences and follow-up work: `docs/architecture.md` is the human-readable description and its layer table must match the test's map (checked). T004 creates `graph.schema`, `evidence`, `diagnostics`; T006 `syntax`; T022 `graph.store`; T024 `graph.query`/`cli` commands.
- Verification: `tests/test_t003.py::TestImportLayering` (R1–R6, doc/test consistency, and a negative self-test on synthetic violations).
- Supersedes: none (refines D-0017's layout)

### D-0029 — Runtime dependency set (none), license policy and pin policy
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T003); policy from the user (D-0008)
- Related: Q07; R12; T003, T002, T006, T016, T017, T018, T024; AC-12; D-0006, D-0008, D-0014, D-0017, D-0019; SPEC §7
- Context/problem: D-0008 requires permissive licenses and a documented table of dependencies and alternatives. D-0017 left the runtime set at zero provisionally. Candidates had to be decided, not just listed, and the policy had to become machine-checkable.
- Options considered: Per candidate — `packaging` (Apache-2.0 OR BSD-2-Clause; PEP 440/508 specifiers and markers) vs. a hand-written parser; `tomli` (MIT) vs. stdlib `tomllib`; a lockfile library vs. none; `libcst` (MIT, with PSF-licensed grammar parts) / `parso` (MIT + PSF) vs. stdlib `ast`; `typer` (MIT, depends on `click`) / `click` (BSD-3) vs. stdlib `argparse`; `pydantic` (MIT) vs. stdlib frozen dataclasses; `sqlite3` (stdlib) vs. an ORM or external graph store; `pathspec` (MPL-2.0; already rejected in D-0019). Pinning style for runtime dependencies — exact `==` (reproducible, but hostile to co-installation with other tools in one environment) vs. bounded range `>=tested,<next-major` (co-installable, protected from breaking majors, exact tested version recorded in the table) vs. unbounded floor (not reproducible).
- Chosen option: Stage 1 foundation has **zero runtime dependencies**. `tomllib`, `argparse`, `dataclasses`, `sqlite3`, `ast`, `hashlib` are used from the standard library. `packaging` is *pre-approved* (license and purpose recorded in `docs/dependencies.md`) and is added by T016 when PEP 440/508 evaluation is implemented, as `packaging>=26.3,<27`; writing our own specifier/marker parser is rejected (large, subtle, and the reference implementation is permissively licensed). No lockfile library: `poetry.lock`/`uv.lock`/`pdm.lock` are TOML and `Pipfile.lock` is JSON, both stdlib-parsable (T017/T018). Parser libraries stay out until T002 decides whether stdlib `ast` on the host interpreter suffices; their license facts are recorded now so T002 only decides on technical merit. Allowed SPDX identifiers: `MIT`, `MIT-0`, `BSD-2-Clause`, `BSD-3-Clause`, `0BSD`, `Apache-2.0`, `PSF-2.0`, `Python-2.0`, `ISC`, `Zlib`; `OR` expressions are allowed if any branch is allowed, `AND` only if all are. Not allowed for runtime: MPL, LGPL, GPL, AGPL, EUPL, SSPL, BUSL, CC-BY-SA. Pin policy: runtime dependencies `==X` or a bounded range (`>=a,<b` or `~=a.b`); development dependencies exact `==`; build requirements bounded. Development tools added: `pytest-cov==7.1.0` (MIT), `coverage==7.17.3` (Apache-2.0), `pip-licenses==5.5.5` (MIT). The policy applies to runtime dependencies and anything vendored; development-only transitive packages are listed for transparency (`pathspec` MPL-2.0 arrives via mypy and is neither imported by nor shipped with the analyzer).
- Rationale/evidence: Zero dependencies keeps the analyzer trivially offline (D-0006), auditable (no third-party code runs on untrusted input) and installable anywhere; every stdlib alternative covers the Stage 1 need. License facts were read from the installed distributions' metadata (`License-Expression`/classifiers) with `pip-licenses` on 2026-11-12.
- Tradeoffs, risks, limitations: `argparse` is more verbose than `click`/`typer` for twelve subcommands (T024). Stdlib `ast` ties the parsed grammar to the host interpreter (D-0002 risk, owned by T002). Bounded ranges can admit a broken minor release; the table records the exact version tested.
- Consequences and follow-up work: `docs/dependencies.md` holds the tables; `tests/test_t003.py::TestDependencyPolicy` reads `pyproject.toml` and the tables and fails on any undocumented, unpinned or non-permissive dependency and on any third-party import in `src/` that is not a declared runtime dependency. Adding a runtime dependency requires a new decision entry plus a table row.
- Verification: `tests/test_t003.py::TestDependencyPolicy`, `TestImportLayering::test_only_declared_third_party_imports`; `make licenses` output recorded in the T003 developer report.
- Supersedes: D-0017 (dependency-table and "revisit" items)

### D-0030 — Build backend stays setuptools; editable install made reliable on this host (hidden `.pth` files)
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T003)
- Related: R12; T003, T030; AC-12; D-0008, D-0017, D-0029, D-0034
- Context/problem: D-0017 left the backend choice open. Separately, `pip install -e .` appeared inert on the development host: `.venv/bin/python -c "import code_analysis"` failed although `__editable__.code_analysis-0.1.0.pth` existed and contained the `src` path.
- Options considered: `setuptools` (MIT; ubiquitous, PEP 621/639 support since 77, dynamic `attr:` version read statically) vs. `hatchling` (MIT; cleaner defaults, but another tool to learn and it also installs editable projects through a `.pth` file) vs. `flit-core` (BSD-3; no `package-dir` src mapping needed but no dynamic version from an attribute without importing). For the editable problem: (i) `--config-settings editable_mode=compat` (deprecated by setuptools, prints a warning); (ii) switch backend; (iii) document the real cause and clear it in the install target.
- Chosen option: Keep `setuptools` with `requires = ["setuptools>=77,<85"]` and (iii). Root cause found with `python -v`: `site.py` in CPython 3.12.3 logs `Skipping hidden .pth file` because the file carries the macOS `UF_HIDDEN` flag (`ls -lO` shows `hidden`). The flag is set by pip's wheel extraction on this host — every file of a freshly installed downloaded wheel (e.g. `pytest_cov-7.1.0.dist-info/METADATA`) and the first editable install carried it, while later editable reinstalls did not. Neither editable mode nor the backend addresses this; `chflags nohidden` on the `.pth` files does, immediately and verifiably. `make install` therefore runs the editable install, clears the flag on `site-packages/*.pth` when on Darwin, and proves the import with `python -c "import code_analysis"`. Tests continue to run through pytest's `pythonpath = ["src"]`, so they never depend on the install state.
- Rationale/evidence: Observed on 2026-11-12: before — `.pth` hidden, import fails; after `chflags nohidden` — import succeeds from `src/`; `__editable__` file written by a fresh `pip install -e .` (pip 26.3) not hidden, import succeeds. Changing backends would not have fixed a flag set by the installer.
- Tradeoffs, risks, limitations: The workaround is macOS-specific; Linux CI (T030) does not need it. The `.pth` file may become hidden again after a reinstall; `make install` is idempotent. `pip wheel`/`build` need network for build isolation, so tests do not build a wheel; installability is verified by the editable install plus `importlib.metadata` checks.
- Consequences and follow-up work: README documents `make install` and the symptom. T030 verifies a clean non-editable `pip install .` in CI.
- Verification: `tests/test_t003.py::TestPackageMetadata::test_installed_distribution_matches_source` (skips when not installed), `::test_build_backend_is_setuptools`; manual: `.venv/bin/python -c "import code_analysis"`.
- Supersedes: D-0017 (backend provisional note)

### D-0031 — Analyzer runtime floor: `requires-python >= 3.12`
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T003)
- Related: R12; T002, T003, T030; AC-12; D-0002, D-0017
- Context/problem: D-0017 asked whether the runtime floor should be lowered for users. This is distinct from the parsed syntax range 3.8–3.14 (D-0002), which T002 handles.
- Options considered: 3.11 (adds `tomllib` and `StrEnum`, which the code uses; widens the audience; no 3.11 interpreter exists on the development host — only 3.10 and 3.12 — so it cannot be tested now); 3.12 (the development interpreter; `pathlib` and `typing` improvements, PEP 695 syntax available if wanted); 3.13 (too new for users).
- Chosen option: 3.12. Classifiers list only `3.12`; `3.13`/`3.14` are added when CI (T030) runs them. Lowering to 3.11 is a one-line change (`requires-python`, `ruff target-version`, `mypy python_version`) that may be made in a new entry once a 3.11 job exists — never before, because the project claims only what it tests.
- Rationale/evidence: SPEC §3.8 (a stage is complete only when tests pass) and the project rule against unverified claims.
- Tradeoffs, risks, limitations: Users on 3.11 cannot install Stage 1 until the floor is revisited. The host interpreter also bounds which grammar stdlib `ast` can parse; that is T002's matrix, not this floor.
- Consequences and follow-up work: T030 adds interpreter matrix; T002 documents per-host parse coverage.
- Verification: `tests/test_t003.py::TestPackageMetadata::test_requires_python_floor_is_consistent`.
- Supersedes: D-0017 (floor "to revisit" note)

### D-0032 — Ruff rule set finalised (PTH, S, ANN, FA, TID and friends); explicit allowlists
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T003)
- Related: R12; T003; AC-12; D-0015, D-0017, D-0026, D-0028
- Context/problem: D-0017 selected `E, W, F, I, B, UP, N, SIM, RUF` and deferred `PTH`, `S`, `ANN`.
- Options considered: Measured each candidate family against the current tree (`ruff check --select ... --statistics`): `PTH` (9 hits, all deliberate `os`-level I/O), `S` (197× `S101` assert in tests, 1× `S105` false positive on a test string), `ANN` (18× `ANN401` `Any` in test doubles), `FA`/`C4`/`PIE`/`RET`/`T20`/`PGH`/`ERA`/`TID` (0–1 hits), `PL` (10 hits: magic numbers, argument counts — opinionated, no safety value), `FBT` (2 hits in a parametrized test; would force keyword-only booleans retroactively), `PERF` (2 stylistic hits in the no-execution scanner), `ISC` (`ISC001` conflicts with the formatter), `D` (docstring style; deferred to the documentation task).
- Chosen option: Add `PTH`, `S`, `ANN`, `FA`, `C4`, `PIE`, `RET`, `T20`, `PGH`, `ERA`, `TID` (with `ban-relative-imports = "all"`, which is architecture rule R3 of D-0028). Not adopted: `PL`, `FBT`, `PERF`, `ISC`, `D`. Allowlists, each with a reason in `pyproject.toml`: `src/code_analysis/discovery/walk.py` ignores `PTH` (descriptor-relative `dir_fd`/`O_NOFOLLOW` I/O has no `pathlib` equivalent, D-0026); `src/code_analysis/cli/*` ignores `T20` (writing to stdout is the CLI's job); `tests/*` ignore `S101` (assert), `ANN401` (test doubles wrapping untyped `os` callables) and `S603` (tests spawn the project's own interpreter with fixed argv). Six individual lines in `tests/test_t001.py` carry targeted `noqa` codes (`PTH211`, `PTH118`, `PTH112`, `PTH208`, `S105`) with the reason inline. One real finding was fixed (`C416` in `core/patterns.py`).
- Rationale/evidence: `S` is the only automated check for the no-execution boundary besides the tests; `PTH` keeps new code on `pathlib` while the one module that must use descriptors is allowlisted as a whole, visibly; `ANN` complements `mypy --strict` for tests (mypy does not require annotations on untyped test helpers unless `disallow_untyped_defs`, which strict does — `ANN` adds the lint-time signal).
- Tradeoffs, risks, limitations: `S` has false positives on strings that look like secrets; they are handled per line, never by disabling the family. `T20` must be allowlisted again if another interface package prints.
- Consequences and follow-up work: `make lint` runs `ruff check .` and `ruff format --check .`.
- Verification: `ruff check .` and `ruff format --check .` clean; `tests/test_t003.py::TestToolingConfig::test_ruff_rule_families_and_allowlists`.
- Supersedes: D-0017 (rule set)

### D-0033 — Coverage tooling: pytest-cov with branch coverage, `fail_under = 90`
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T003)
- Related: R12; T003, T005, T030; AC-11, AC-12; D-0029
- Context/problem: No coverage measurement existed; a recorded threshold is required for phase gates.
- Options considered: `coverage run -m pytest` (no plugin, two commands) vs. `pytest-cov` (MIT; one command, `--cov-fail-under`, subprocess support) vs. no coverage. Threshold: 80 (too loose for a safety-critical walker), 95 (would fail on defensive OS-error branches that cannot be reproduced deterministically), 90, or "current value" (brittle). Always-on via `addopts` vs. a separate target.
- Chosen option: `pytest-cov==7.1.0` + `coverage==7.17.3`, branch coverage on, `fail_under = 90` in `[tool.coverage.report]` and mirrored by `make coverage` (`COV_FAIL_UNDER ?= 90`). Not in `addopts`: plain `pytest` stays fast and `--pdb`-friendly; CI (T030) runs `make coverage`. `__main__.py` (three lines, exercised through a subprocess smoke test) is omitted. Measured baseline on 2026-11-12 before T003's code: 646 statements, 176 branches, 96% (line-only 97%).
- Rationale/evidence: 90 catches an untested module or a dropped test class while tolerating the ~4% of defensive branches identified in `walk.py` (`OSError` handlers, `_NotRegularError`).
- Tradeoffs, risks, limitations: Branch coverage does not prove the hostile-input behaviour; mutation checks (T001 report) and the security suite (T029) do. The threshold is global, so a large well-covered module can mask a small uncovered one; T005 may add per-module reporting.
- Consequences and follow-up work: `.coverage*`/`htmlcov/` already git-ignored.
- Verification: `make coverage` → total ≥ 90% (actual value in the T003 report); `tests/test_t003.py::TestToolingConfig::test_coverage_threshold_is_recorded_consistently`.
- Supersedes: none

### D-0034 — Task runner: `Makefile` (GNU make), no Python-based runner
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T003)
- Related: R12; T003, T030; AC-12; D-0029, D-0030
- Context/problem: Developers and CI need one place that spells out the verification commands (and the editable-install workaround, D-0030).
- Options considered: `Makefile` (GNU make 3.81 ships with macOS and every Linux; no dependency; shell-level) vs. `nox` (MIT; Python sessions, manages its own venvs; another dev dependency and a second venv layer) vs. `tox` (MIT; same, INI-driven) vs. `just` (not installed) vs. shell scripts (no target graph, no `help`).
- Chosen option: `Makefile` with targets `venv`, `install`, `test`, `typecheck`, `lint`, `format`, `coverage`, `licenses`, `check` (= lint + typecheck + coverage), `clean`, and `help`; every tool is invoked from `$(VENV)/bin` (`VENV ?= .venv`). Written for GNU make 3.81 syntax (no `!=`, no `.ONESHELL`).
- Rationale/evidence: Zero new dependencies, matches the "stdlib-friendly" preference of the project, and the T030 CI can call the same targets.
- Tradeoffs, risks, limitations: Windows developers run the commands listed in `README.md` directly (no make); multi-interpreter matrices are CI's job, not make's.
- Consequences and follow-up work: README references `make` targets; T030 uses `make check`.
- Verification: `tests/test_t003.py::TestToolingConfig::test_makefile_declares_expected_targets`; `make check` run in the T003 report.
- Supersedes: none

### D-0035 — Version single source (`code_analysis.__version__`, dynamic metadata), classifiers, changelog
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T003)
- Related: R12; T003, T031; AC-12; D-0017, D-0030
- Context/problem: `pyproject.toml` carried `version = "0.1.0"` and `__init__.py` carried `__version__ = "0.1.0"`: two sources that can drift.
- Options considered: (a) keep both and test equality; (b) `dynamic = ["version"]` with `[tool.setuptools.dynamic] version = {attr = "code_analysis.__version__"}` — setuptools reads the attribute statically (via `ast`) without importing the package at build time; (c) `__version__ = importlib.metadata.version("code-analysis")` — fails whenever the distribution is not installed (exactly the D-0030 situation) and costs a metadata lookup at import; (d) `setuptools-scm` from git tags (extra build dependency; no release tags yet).
- Chosen option: (b). `code_analysis.__version__` is the only place a version is written; the SPEC's "analysis version" stored in snapshots (§5.3) will read it from there. Classifiers: `Development Status :: 2 - Pre-Alpha`, `Environment :: Console`, `Intended Audience :: Developers`, `Programming Language :: Python :: 3 / 3 :: Only / 3.12`, `Topic :: Software Development :: Quality Assurance`, `Typing :: Typed`; no OS classifier until Linux/Windows are tested (T030); no license classifier (D-0037). `project.urls.Repository` points at the configured `origin`. `CHANGELOG.md` follows Keep a Changelog 1.1.0 with an `Unreleased` section; a version bump edits `__init__.py` and the changelog together.
- Rationale/evidence: One write location, no import at build time (keeps the "never import to build" habit even for our own package), works with the inert-install scenario.
- Tradeoffs, risks, limitations: setuptools' static reader handles only simple string assignments — `__version__` must stay a literal.
- Consequences and follow-up work: T031 (docs) owns release notes beyond the changelog.
- Verification: `tests/test_t003.py::TestPackageMetadata::test_version_is_single_sourced`, `::test_installed_distribution_matches_source`, `TestToolingConfig::test_changelog_follows_keep_a_changelog`.
- Supersedes: D-0017 (static version)

### D-0036 — CLI scaffolding: `argparse`, `code-analysis` console script, `python -m code_analysis`, exit codes 0/2
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T003)
- Related: R12; T003, T024; AC-10, AC-12; D-0028, D-0029; SPEC §8
- Context/problem: The package needs its entry point declared so installation produces the `code-analysis` command; the SPEC's twelve commands belong to T024.
- Options considered: Framework — `argparse` (stdlib) vs. `click` (BSD-3) vs. `typer` (MIT, depends on `click`, optional `rich`) — see D-0029. Scope now — no CLI module (entry point would dangle) vs. a stub that only knows `--version`/`--help`. Exit code on no arguments — 0 with help (chosen for the stub; nothing is "missing" yet) vs. 2 (usage error; T024 decides once commands exist).
- Chosen option: `code_analysis.cli.main(argv=None) -> int` built on `argparse`; `--version` prints `code-analysis <version>` and returns 0, `--help` and no arguments print help and return 0, unknown arguments return 2 (`argparse` convention) with the usage on stderr. `ExitCode` is an `IntEnum` with `OK = 0` and `USAGE = 2`; T024 extends it (and documents the full table per SPEC §8) rather than inventing codes ad hoc. `[project.scripts] code-analysis = "code_analysis.cli:main"`; `code_analysis/__main__.py` makes `python -m code_analysis` work without the console script (useful while the editable install is inert, D-0030). `main` catches `argparse`'s `SystemExit` and returns the code so it is testable in-process.
- Rationale/evidence: Keeps the runtime dependency count at zero; argparse subparsers cover the twelve commands, `--json` and `--help` required by SPEC §8.
- Tradeoffs, risks, limitations: No SPEC command exists yet; running the stub does nothing useful by design.
- Consequences and follow-up work: T024 adds subcommands, `--json`, and the exit-code table.
- Verification: `tests/test_t003.py::TestCliStub` (in-process flags and codes; `python -m code_analysis --version` subprocess smoke).
- Supersedes: none

### D-0037 — Project license is undecided: no license claimed in metadata, `LICENSE` absent
- Date (UTC): 2026-11-12
- Status: needs-user
- Author/approver: Claude (developer, T003); decision owner: user
- Related: R12; T003, T031; AC-12; D-0008, D-0035
- Context/problem: `pyproject.toml` declared `license = "MIT"` without a user decision and without a `LICENSE` file. The project's own license is a product/legal decision that Claude must not make.
- Options considered: (a) MIT — shortest, most common for Python tooling, no patent clause; (b) Apache-2.0 — explicit patent grant and contribution terms, requires a `NOTICE` file and license headers are customary; (c) BSD-3-Clause — MIT-like with a no-endorsement clause; (d) proprietary / all rights reserved — default under copyright law when nothing is granted; blocks any redistribution or PyPI publication. All of (a)–(c) are compatible with the permissive-only dependency policy (D-0008).
- Chosen option: None yet. Until the user decides: the `license` field is removed from `pyproject.toml` (no claim), no `License ::` classifier is set, `LICENSE` is absent, and `tests/test_t003.py` asserts exactly this state so the choice cannot be made silently. Proposed default for the user to confirm or change: MIT.
- Rationale/evidence: Inventing a license would be a material, irreversible product decision (B07, D-0016).
- Tradeoffs, risks, limitations: Without a license the code is "all rights reserved" by default; publication to PyPI (T031/T032) is blocked until this is resolved.
- Consequences and follow-up work: When the user answers, a new entry records it, `LICENSE` is added, `license = "<SPDX>"` and `license-files` are set, and the assertion in `tests/test_t003.py` is inverted.
- Verification: `tests/test_t003.py::TestPackageMetadata::test_no_license_is_claimed_until_decided`.
- Supersedes: D-0017 (the `license = "MIT"` line)

### D-0038 — Add `O_BINARY` to the file-open flags (T001 reviewer finding R1)
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T003)
- Related: R01; T001, T003, T030; AC-11; D-0021, D-0026
- Context/problem: `_OPEN_FLAGS` in `discovery/walk.py` lacked `O_BINARY`. On Windows, `os.open` without it opens in text mode and translates CRLF, which would corrupt the raw-byte SHA-256 (D-0021) in the fallback traversal mode.
- Options considered: `getattr(os, "O_BINARY", 0)` ORed into the flags (no-op on POSIX, where the name does not exist) vs. leaving it to T030's Windows CI to discover.
- Chosen option: `_O_BINARY: Final = getattr(os, "O_BINARY", 0)`; `_OPEN_FLAGS = os.O_RDONLY | _O_NOFOLLOW | _O_CLOEXEC | _O_BINARY`. Directory opens are unaffected.
- Rationale/evidence: Zero cost on POSIX; removes a known Windows hazard before any Windows run exists.
- Tradeoffs, risks, limitations: Cannot be executed on this host (no `O_BINARY`); verified structurally.
- Consequences and follow-up work: T030 Windows CI confirms hashes equal the POSIX fixture hashes.
- Verification: `tests/test_t003.py::TestT001FollowUps::test_open_flags_include_o_binary_when_available`.
- Supersedes: none (amends D-0021/D-0026 flag list)

### D-0039 — Clarify D-0025/D-0026 wording: `realpath` uses `lstat`/`readlink` metadata calls; fallback mode has no directory-swap protection
- Date (UTC): 2026-11-12
- Status: accepted
- Author/approver: Claude (developer, T003); T001 tester finding F1/F2 and reviewer finding R2
- Related: R01; T001, T003, T029; AC-11; D-0025, D-0026
- Context/problem: D-0025, `docs/safety-policy.md` §4.1 and `walk.py` said an outside symlink target is "never `stat`-ed". `os.path.realpath` does call `os.lstat`/`os.readlink` on each path component (including components outside the root) to resolve the link; what is true is that the *result does not depend on whether the target exists* and that nothing is opened or `stat`-ed *through* the link. Separately, the fallback mode without `dir_fd` support was described as keeping "final-component protection", which understates the gap: a directory swapped for a link after classification is listed through the link in that mode.
- Options considered: Edit D-0025/D-0026 in place (violates the append-only rule) vs. a clarifying entry plus wording fixes in code and docs vs. changing behaviour (e.g. a `strict`-free manual component walk that stops at the root boundary — more code for a race T029 already owns).
- Chosen option: Clarifying entry; wording fixed in `walk.py` (module docstring and the `_handle_symlink` comment), `docs/safety-policy.md` §4.1 and §4.2. New wording: "resolved by `realpath`, which performs only `lstat`/`readlink` metadata calls; the result does not depend on target existence; the target is never opened or `stat`-ed through the link". Fallback mode: "no directory-swap protection (T029)". Behaviour unchanged.
- Rationale/evidence: Precision in a security document matters more than brevity; `tests/test_t003.py` adds a behavioural check that the escape diagnostic is identical whether or not the outside target exists and that no `os.open` touches an outside path, plus a strict `xfail` test that pins the fallback-mode limitation so T029 must update it when fixing.
- Tradeoffs, risks, limitations: The `xfail` documents a known weakness in the test suite output; it is intentional and reported.
- Consequences and follow-up work: T029 decides whether fallback mode should refuse to run on hostile trees or implement a safer walk; D-0025/D-0026 stand otherwise.
- Verification: `tests/test_t003.py::TestT001FollowUps::test_escape_diagnostic_independent_of_target_existence`, `::test_fallback_mode_has_no_directory_swap_protection` (xfail strict), `::test_safety_policy_wording_is_precise`.
- Supersedes: D-0025 and D-0026 (wording only; rules and behaviour unchanged)

### D-0040 — Editable install root cause corrected: iCloud Drive re-hides `.pth` files; `make install` verifies instead of patching (supersedes the D-0030 root-cause analysis and workaround)
- Date (UTC): 2026-11-13
- Status: accepted (handling); the layout choice it depends on is needs-user (Q14)
- Author/approver: Claude (developer, T003 fix round); root cause established by the T003 tester (finding F1)
- Related: R12; T003, T030; AC-12; D-0030, D-0034; Q14
- Context/problem: D-0030 attributed the inert editable install to "pip's wheel extraction" setting the macOS `UF_HIDDEN` flag on the `.pth` file and had `make install` run `chflags nohidden`. The tester showed that the flag returns about five seconds after it is cleared: the repository lives under `~/Desktop`, which is synced by iCloud Drive ("Desktop & Documents"), and the iCloud daemon applies `UF_HIDDEN` to every dot-path it manages (`.git`, `.gitignore`, `.venv/**`, hence `__editable__.code_analysis-0.1.0.pth`). CPython 3.12.3 `site.py` skips hidden `.pth` files, so the editable install and the `code-analysis` console script are inert whenever the venv is under iCloud. pip does not set the flag; an editable install into a venv outside iCloud works durably. D-0030's backend decision (setuptools, `>=77,<85`) is unaffected and stands.
- Options considered: (1) keep `chflags nohidden` and claim success (wrong: undone within seconds); (2) move the repository out of iCloud; (3) keep the repository and put the venv outside iCloud (`make VENV=~/.venvs/code-analysis install`, which the existing `VENV ?=` override already supports); (4) leave both in place and document that only the pytest path (`pythonpath = ["src"]`) and `PYTHONPATH=src python -m code_analysis` work; (5) have the analyzer package work around it at import time (rejected: the package must stay side-effect free, R6, and this is a host problem, not a package problem).
- Chosen option: Options 2-4 are the user's call and are tracked as Q14; nothing in the repository is moved by Claude. Independently of that choice, `make install` stops claiming a fix: it no longer runs `chflags`, and after `pip install -e .` plus the dev group it runs `scripts/check_install.py` with the venv interpreter. The script (stdlib only, `mypy --strict`, ruff-checked, unit-tested) starts a fresh `python -I` and requires `import code_analysis` to resolve to this repository's `src/`; it reports every `site-packages/*.pth` that carries `UF_HIDDEN`; and it reports when the venv has an ancestor managed by iCloud Drive (xattr `com.apple.icloud.*`, or `~/Library/Mobile Documents`) or another File Provider sync domain (xattr `com.apple.file-provider-domain-id`). Any of the three conditions fails the target with the cause and the options above (including the exact `make VENV=... install` command). A standalone `make check-install` target runs the same check. Tests never depend on the install state (`pythonpath = ["src"]`), so `make check` is unaffected.
- Rationale/evidence: Tester measurement: `.pth` hidden again at t=+5.1 s after `make install`; import fails from `/private/tmp`; editable install into a venv outside iCloud works. Reproduced on 2026-11-13: `ls -lO .venv/lib/python3.12/site-packages/*.pth` shows `hidden`; `xattr ~/Desktop` and `xattr ~/Documents` list `com.apple.icloud.desktop` and `com.apple.file-provider-domain-id`; `.venv/bin/python -c "import code_analysis"` from `/private/tmp` fails with `ModuleNotFoundError`. A verification step cannot be undone by the sync daemon, whereas a flag change can.
- Tradeoffs, risks, limitations: On this host `make install` now exits 1 until Q14 is answered (every package is still installed; only the final check fails) — this is the honest state. The cloud-sync detection is heuristic (xattr names observed on macOS 15; `Library/Mobile Documents` path); other sync tools that hide dot-files are not detected, but the hidden-`.pth` and import checks still catch the symptom. Windows and Linux: the flag and xattr checks are no-ops; only the import check applies.
- Consequences and follow-up work: README "Install" documents the real cause, the `VENV=` override and the three options; `docs/dependencies.md` and `docs/architecture.md` reference this entry. Q14 records the pending user choice; the T003 tracking notes should say that the editable install is unusable on this host until Q14 is resolved. T030 (CI on Linux/Windows runners, no iCloud) verifies a clean `pip install .`.
- Verification: `tests/test_t003.py::TestInstallCheck` (hidden-flag detection via `os.chflags`, cloud-ancestor detection with a stubbed `os.listxattr` and with a `Library/Mobile Documents` path, message content, exit codes), `::TestToolingConfig::test_makefile_declares_expected_targets` (no `chflags`; `install` runs the check), `::test_make_install_recipe`; manual: `make install` on this host fails with the iCloud message; `make VENV=<path outside iCloud> install` succeeds.
- Supersedes: D-0030 (root-cause analysis and the `chflags` workaround only; the setuptools backend decision stands)

### D-0041 — Reproducible, offline wheel builds: pinned `setuptools` in the dev group, `clean-build` before every build, wheel contents checked against `src/`
- Date (UTC): 2026-11-13
- Status: accepted
- Author/approver: Claude (developer, T003 fix round); T003 tester finding F2
- Related: R12; T003, T030; AC-12; D-0029, D-0030, D-0034
- Context/problem: A stale `build/lib/code_analysis/cli/main.py` from an earlier module layout was reused by setuptools' `build_py` (it merges `build/lib` instead of recreating it), so wheels built from the working tree shipped a module that no longer exists in `src/`. Nothing verified wheel contents. Building a wheel offline was not possible: Python 3.12 venvs contain no `setuptools`, so `pip wheel --no-build-isolation` fails, and an isolated build downloads the backend.
- Options considered: (a) rely on `make clean` by convention; (b) make every build-related target depend on a `clean-build` step; (c) add a test that builds a wheel and compares it with `src/` — with the backend obtained by (c1) network/build isolation (not offline, not reproducible), (c2) `python -m build` (adds the `build` distribution and its dependencies), or (c3) the venv's own `setuptools`, pinned exactly in the dev group like every other dev tool (D-0029 pin policy), so `pip wheel --no-deps --no-build-isolation --no-index` runs offline with the same backend version everywhere.
- Chosen option: (b) + (c) with (c3). `Makefile`: `clean-build` removes `build/`, `dist/` and `src/*.egg-info`; `install` and the new `build` target (`pip wheel --no-deps --no-build-isolation --no-index --wheel-dir dist .`) depend on it; `clean` depends on it too. `pyproject.toml`: `setuptools==84.2.1` (MIT; the newest release inside the existing `[build-system] requires` range `>=77,<85`) joins the `dev` group; `[build-system]` is unchanged, so isolated builds (plain `pip install .`, T030) keep the bounded range. `tests/test_t003.py::TestWheelContents` copies `pyproject.toml`, `README.md` and `src/` (without `__pycache__`/egg-info) to a temporary directory, builds a wheel there with the venv's pip and setuptools (`--no-index`, no network), and asserts that the set of `code_analysis/**` entries in the wheel equals the set of files under `src/code_analysis/` (no extras, no missing, `py.typed` included), that the wheel `Version` equals `__version__` and that `entry_points.txt` declares the console script. The test skips with an explicit reason only when `setuptools` or `pip` is not importable. A second test asserts that the dev pin satisfies the build-system range, and the Makefile tests assert the `clean-build` prerequisites.
- Rationale/evidence: Building in a temporary copy keeps the repository clean and makes the test independent of a stale `build/`; the `clean-build` prerequisite closes the stale-artefact path for real builds from the working tree. The sdist is not checked (pip cannot build one; `python -m build` was rejected above); T030's clean `pip install .` covers the sdist path.
- Tradeoffs, risks, limitations: One more dev tool to keep pinned (setuptools releases often; the pin, not the range, decides what the test uses). `pip wheel` of the copy takes about two seconds. The dev-group pin and the build-system range can drift apart; the new test fails when the pin leaves the range.
- Consequences and follow-up work: `docs/dependencies.md` gains the dev row (and now lists `packaging` among the observed transitive packages); README documents `make build`. When the project license is decided (D-0037) the wheel test should also assert the license metadata.
- Verification: `tests/test_t003.py::TestWheelContents`, `::TestDependencyPolicy::test_dev_setuptools_pin_satisfies_build_range`, `::TestToolingConfig::test_makefile_declares_expected_targets`; manual: `make build` produces `dist/code_analysis-0.1.0-py3-none-any.whl` without network.
- Supersedes: none (extends D-0029 dev-tool set and D-0034 targets)

### D-0042 — `make install` upgrades pip to `>=25.1` before installing the dev group
- Date (UTC): 2026-11-13
- Status: accepted
- Author/approver: Claude (developer, T003 fix round)
- Related: R12; T003, T030; AC-12; D-0029, D-0034, D-0040
- Context/problem: `make install` installs the dev tools with `pip install --group dev` (PEP 735 dependency groups), which exists since pip 25.1. The project `.venv` happened to carry pip 26.3, but a venv freshly created by `python3 -m venv` ships the interpreter's bundled pip (24.x on this host), so the documented option `make VENV=~/.venvs/code-analysis install` (D-0040) failed with `no such option: --group` after the editable install had already succeeded.
- Options considered: (a) upgrade pip inside the target (`python -m pip install --upgrade "pip>=25.1"`, a lower bound, not a pin: pip is the installer, not a tool whose behaviour the tests depend on); (b) replace `--group` with a requirements file duplicating the pins (two sources of truth, against D-0029); (c) pin pip exactly in the dev group (circular: the group is installed by pip).
- Chosen option: (a), as the first step of `install`, before `pip install -e .`; README's manual steps show the same command. `docs/dependencies.md` already lists pip as part of the venv.
- Rationale/evidence: `make VENV=<path outside iCloud> install` failed at the `--group` step with the bundled pip and succeeds after the upgrade (T003 fix-round verification). A lower bound keeps the target working with any newer pip while naming the feature floor.
- Tradeoffs, risks, limitations: The upgrade needs network on a fresh venv (as does everything else in `install`). The project venv's pip version is not pinned; dev-tool pins (D-0029) are unaffected.
- Consequences and follow-up work: T030 CI runners use the same target; a pip below 25.1 on a runner is upgraded rather than failing.
- Verification: `tests/test_t003.py::TestToolingConfig::test_makefile_declares_expected_targets` (the upgrade precedes `--group`), `::test_make_build_targets_clean_before_building`; manual run recorded in the T003 fix-round developer report.
- Supersedes: none (amends the D-0034 `install` recipe)
