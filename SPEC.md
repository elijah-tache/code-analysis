# SPEC.md — Code Impact & Migration / Stage 1

Version: 1.0 | Status: implementation baseline | Scope: Python static analysis only

## 1. Mission
Build a deterministic, offline-capable, non-executing Python code intelligence engine that indexes a repository and its explicitly selected dependency environments into a persistent, provenance-rich graph. Answer where a symbol comes from, how it is used, what may break when it changes, and what compatibility/deprecation evidence exists. No LLM, agents, generated migrations, automatic code edits, or execution of analyzed code in Stage 1.

**Non-negotiable:** every material implementation/design decision made by Claude must be documented in `DECISIONS.md`, with rationale, alternatives, consequences, verification, and relevant requirement/task IDs. Keep the log append-only (corrections are new entries). All analysis results must expose evidence, confidence/resolution state, and limitations. Never present potential impact as certain breakage.

## 2. Users and use cases
- Engineer selects repository, Python target versions, optional lockfiles, and analysis environment; obtains a reproducible graph.
- Engineer navigates from a function/class/module to callers, callees, imports, implementations, instances/constructors, and dependent symbols.
- Engineer asks what could be affected by editing/removing/renaming a symbol or changing a function signature, dependency version, or target Python version.
- Engineer checks dependency compatibility, deprecated/removed APIs, and the evidence behind findings.
- Engineer compares two analysis snapshots to see added/removed/changed nodes, edges, and compatibility findings.

## 3. Hard boundaries and correctness principles
1. Parse source; **never import, execute, evaluate, install, or build target project code**. Treat repository contents, dependency metadata, stubs, and documentation as untrusted. Do not run setup.py, plugins, arbitrary shell commands from repository, or project test suites as part of indexing. Tests of the analyzer itself may execute controlled fixtures.
2. Python-only first release; explicit supported syntax range decided via a documented compatibility matrix. Syntax unsupported by the parser must produce a diagnostic, not silent omission.
3. No AI/LLM, embedding-based inference, network-dependent indexing, automatic fixes, or speculative certainty.
4. Soundness is limited by Python's dynamic semantics. Represent edges as `resolved`, `candidate`, `unknown`, or `external_unresolved` with evidence and reason codes. Confidence must not be fabricated as a probability.
5. Each query must distinguish direct dependencies, transitive reachability, and *possible* behavioral impact. No claim that graph reachability proves a bug.
6. All generated output must be reproducible for the same inputs, tool version, configuration, and metadata snapshot (stable identifiers and deterministic ordering).
7. Protect secrets and paths: avoid persisting source contents unnecessarily; redact credentials in logs; no telemetry by default; ignore configured exclusions.
8. A stage is complete only when automated tests and documented acceptance gates pass; unsupported cases must be visible.

## 4. Inputs and environments
- Source tree and workspace roots; include/exclude patterns; optional multiple local packages and editable/path dependencies.
- `pyproject.toml` (PEP 621, dependency groups where recognizable, tool sections), `requirements*.txt` (supported pip requirement syntax with diagnostics for unsupported directives), `setup.cfg`, `Pipfile.lock`, `poetry.lock`, `uv.lock`, `pdm.lock`, `requirements` constraints, installed distribution metadata, and wheel `METADATA`/`RECORD` where supplied. Support is phased and format-specific; never claim all lockfile dialects are complete without fixture coverage.
- Python target version(s), platform/environment markers, extras, dependency groups, and chosen resolver snapshot. Keep declared constraints, resolved/installed versions, and candidate versions separate.
- Offline first: installed dist-info, local wheel caches, vendored stubs, and user-provided metadata snapshots. Optional later explicit metadata sync using a controlled fetcher (disabled by default; no executing packages), with source URL, retrieval timestamp, hashes, cache and provenance.
- Package names are not import names; map distributions to top-level modules using `top_level.txt`, `RECORD`, known namespaces and fallback evidence, retaining ambiguity.

## 5. Graph contract
### 5.1 Node types
Workspace, distribution, distribution-version, environment, Python-version, package, module, import-binding, class, function, method, parameter, variable/binding, attribute, property, protocol/interface, type-alias, overload, call-site, reference-site, object-allocation-site, decorator-application, external-symbol, unresolved-symbol, compatibility-rule, deprecation-record, diagnostic, source-file and snapshot. A node may represent a syntactic site versus a semantic symbol; do not collapse them.

### 5.2 Edge types
`CONTAINS`, `DEFINES`, `IMPORTS_MODULE`, `IMPORTS_SYMBOL`, `ALIASES`, `REEXPORTS`, `REFERENCES`, `CALLS`, `POSSIBLY_CALLS`, `CONSTRUCTS`, `READS`, `WRITES`, `ASSIGNS_FROM`, `RETURNS`, `PASSES_AS_ARGUMENT`, `DECORATED_BY`, `INHERITS`, `IMPLEMENTS_CANDIDATE`, `OVERRIDES`, `RESOLVES_TO`, `HAS_TYPE`, `DEPENDS_ON`, `REQUIRES_PYTHON`, `REQUIRES_DISTRIBUTION`, `COMPATIBLE_WITH`, `INCOMPATIBLE_WITH`, `DEPRECATED_IN`, `REMOVED_IN`, `HAS_DIAGNOSTIC`, `CHANGED_IN_SNAPSHOT`. Add new edge kinds only with schema migrations, tests, and decision entries.

### 5.3 Mandatory metadata
Stable symbol/site ID; node/edge kind; snapshot ID; normalized path, source span (line/column), qualified name, lexical scope; originating syntax/evidence and analyzer rule ID; resolution status and reason; target environment and metadata provenance where relevant. Multiple possible targets must remain separate candidates. Edge identity includes site, relation, target and environment. Preserve edges across import aliases, namespace packages, relative imports, and re-exports. Store file hashes and analysis version.

### 5.4 Persistence and query API
Use an explicit storage adapter. Default candidate: SQLite tables with indexed nodes, edges, sites, evidence, snapshots, diagnostics, compatibility facts and reachability support; optionally expose graph-native backend later. Do not require Neo4j or an external service. Schema must be versioned/migratable, support transactional snapshot publication, bounded paginated traversals, reverse-edge indexes, search by name/path/kind, and filtering by environment, status, edge type, source and snapshot. Graph traversal must be fast without loading the whole graph into memory. API outputs JSON-compatible stable structures, with cursor pagination and deterministic ordering.

## 6. Static analysis pipeline
1. Discover files safely (symlink policy, exclusions, size caps), identify packages and namespace packages; hash and cache.
2. Parse syntax with Python AST for selected interpreter grammar; use a concrete-syntax/token layer only when source fidelity is needed. Maintain spans; diagnose parse failures and grammar mismatches.
3. Build lexical scopes, definitions, binding tables, global/nonlocal behavior, imports, aliases, shadowing, exports and `__all__` when statically resolvable. Understand conditional definitions and TYPE_CHECKING blocks.
4. Resolve relative/absolute imports, star imports where exports are statically known, package/module boundaries, namespace packages, local vs third-party modules and distribution-to-import mappings. Flag unresolved/ambiguous imports.
5. Index functions, async functions, generators, lambdas, nested functions, parameters, defaults, decorators, annotations, overloads, classes, nested classes, dataclasses, properties, descriptors where statically recognizable, methods (instance/class/static), inheritance, MRO when determinable, overrides, protocols and abstract methods.
6. Build reference/call graph: direct names, qualified attributes, constructor calls, super(), bound/unbound methods, imports/re-exports, function values and simple aliases. Implement conservative intra-procedural points-to/type propagation and optionally bounded interprocedural summaries. Support common assignments, returns, arguments, closures, unions, and branch joins; mark dynamic/ambiguous dispatch as candidates. Do not assert exact runtime objects or values.
7. Build coarse data-flow/def-use: assignments, reads/writes, parameter-to-argument and return-to-assignment edges, attribute accesses, globals/nonlocals, comprehensions and exception bindings. Distinguish flow facts from proven execution order. Advanced alias/heap analysis is optional and must have explicit limits.
8. Model decorators, descriptors, metaclasses, dynamic getattr/getattribute, monkey-patching, exec/eval, importlib, conditional imports and native extensions as bounded recognizers plus uncertainty diagnostics; never silently assume a static resolution.
9. Capture source evidence for every edge, including why each candidate was generated and why an edge is unresolved. Provide explain-path and explain-impact results.
10. Build reverse dependencies and change-impact traversal, including symbol signatures, import/export changes, inheritance/override changes, and dependency compatibility. Limit traversal depth and node count; return truncation metadata. Use edge semantics and risk categories rather than treating all reachability equally.
11. Snapshot comparison: stable symbol identity where possible, file/symbol hashes, signature/annotation changes, edge additions/removals, metadata changes; report renames as heuristic candidates, not proven identity.

## 7. Dependency, version, and compatibility intelligence
- Parse requirement specifiers, markers, extras, constraints, dependency groups, environment markers and `Requires-Python`; distinguish source-declared, locked, installed and hypothetical versions.
- For **a specified distribution version and target environment**, determine compatibility only when supported by evidence: Python version requirement, wheel tags/platform/ABI, dependency constraints and selected environment markers. Metadata absence means `unknown`, not compatible. `Requires-Python` is necessary but not sufficient for installability/runtime behavior.
- Maintain an explicit catalog of available releases only from locally supplied metadata or opt-in fetched snapshots. Do not claim exhaustive knowledge of every library version or API from metadata alone.
- Public API discovery from local source, `.pyi` stubs, exports, metadata, and optional offline docs/rule packs. Record whether evidence comes from a particular installed/release version. Cross-version API comparison requires both versions' artifacts or trusted versioned API records.
- Deprecation evidence: `warnings.warn(DeprecationWarning/FutureWarning)` with statically recognizable sites, `@deprecated` (PEP 702 / typing_extensions), documented deprecation markers in structured rule packs, and versioned changelog entries if curated. Track introduced/deprecated/removed versions only when explicitly evidenced; avoid inferring dates/versions from source absence. Absence in a later API snapshot can be reported as missing, not automatically as formally removed.
- Findings: incompatible Python target, unsatisfiable/contradictory declared constraints (when determinable), unavailable package version in selected snapshot, missing API in inspected version, deprecated API usage, potentially removed API usage, signature mismatch with statically known signatures, ambiguous import/distribution mapping. Findings carry severity, affected environment, source evidence, and certainty.
- Distinguish resolver feasibility from actual package resolution; Stage 1 need not implement a complete pip resolver. Optional dependency-solver integration is separately gated, non-executing and reproducible.
- Maintain release metadata provenance, snapshot date, hashes, completeness, platform, extras and artifact type. Explicitly document blind spots such as C extensions, runtime-generated APIs and metadata drift.

## 8. Queries and user interface
Required CLI: `index`, `status`, `search`, `symbol`, `neighbors`, `path`, `impact`, `compat`, `diagnostics`, `diff`, `explain`, `export`. Use `--help`, documented flags, machine-readable `--json`, and meaningful exit codes. Optional read-only local HTTP API with OpenAPI specification, no arbitrary execution. Graph output: typed node/edge JSON plus GraphML export; optional lightweight browser viewer **only if** core performance and correctness gates pass. Viewer must support search, expand/collapse neighborhoods, direction/edge filters, breadcrumbs, source locations, evidence panel, unknown/candidate styling, and environment/snapshot selection. Never render an entire huge graph by default; fetch neighborhoods on demand.

## 9. Nonfunctional acceptance targets (measure on reference hardware; document it)
- Index 10,000 Python source files / ~1 million LOC on a defined reference fixture in <= 10 minutes warm-independent baseline; publish actual results and machine details. This is a target, not an assumed guarantee.
- Warm incremental reindex after a single isolated file change <= 10 seconds for representative fixture; correct dependent invalidation is more important than latency.
- Local indexed neighborhood query (<= 1000 edges) p95 <= 250 ms and name search p95 <= 200 ms on reference dataset, measured separately from UI render/network.
- Bounded memory, cancellation, progress reporting, crash-safe snapshots, stable results across two runs, deterministic exports, and index schema migration tests.
- Security tests: malicious `setup.py`, pathological source, symlink escape, corrupted metadata, huge files, malformed locks; none may trigger target-code execution.
- Coverage: curated golden fixtures for each supported syntax/relationship and negative/ambiguous cases; no unexplained missing edge in fixtures. Add benchmark and integration suites to CI.

## 10. Acceptance criteria
AC-01 End-to-end index of representative multi-package repo with deterministic, queryable graph.
AC-02 Imports, aliases, relative imports, re-exports, namespace packages, cycles and ambiguous imports traced with evidence.
AC-03 Functions, nested functions, classes, constructors, inheritance, overrides, properties and basic decorators represented correctly.
AC-04 Call/reference edges and bounded points-to resolution correctly separate resolved, candidate and unknown cases.
AC-05 Def-use/read-write/argument-return links supported for documented subset with branch joins and uncertainty.
AC-06 Declared/locked/installed dependency identities, constraints, markers, extras and Python compatibility tracked by environment.
AC-07 API availability and deprecation/removal findings supported only by version-specific evidence; unknowns explicit.
AC-08 Impact/path queries show why, direct vs transitive, uncertainty, filters, truncation and source spans.
AC-09 Incremental indexing, snapshots, diff, schema migration and crash recovery pass tests.
AC-10 CLI, graph export, fast navigation/query API, diagnostics and explanation endpoints documented.
AC-11 Security, determinism, scalability, benchmark and CI gates met or documented as blockers.
AC-12 Every design/implementation decision logged in `DECISIONS.md`, linked to tasks and verified; open questions tracked.

## 11. Deliverables and definition of done
Installable Python package; versioned graph schema and migration mechanism; CLI and optional local API/viewer; typed graph export; fixture corpus; unit/integration/golden/performance/security tests; CI pipeline; Dockerfile for the analyzer (not for executing inspected code); user guide, architecture, graph schema, evidence/uncertainty model, compatibility limitations, benchmark report; `DECISIONS.md`, updated `OPEN_QUESTIONS.md`, `tasks.json` status and `REQUIREMENTS_TRACEABILITY.md`. No completion claim while any mandatory acceptance criterion fails; explicitly report unsupported Python behaviors.
