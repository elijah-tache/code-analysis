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
