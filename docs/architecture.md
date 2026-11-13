# Architecture

Status: in force for Stage 1 (T003, D-0028). Everything marked **planned** describes the
intended shape and the owning task; only `core`, `discovery` and the `cli` stub exist as
code today. Normative sources: `SPEC.md` §3, §5, §6, §8, §11; `IMPLEMENTATION_PLAN.md`
"Architecture"; decisions D-0010, D-0012, D-0015, D-0018, D-0028, D-0029, D-0036.

## 1. Pipeline

```
discovery -> syntax -> scopes/bindings -> import resolution -> symbols
          -> type/points-to -> data flow -> dependency metadata -> compatibility facts
          -> graph records -> graph persistence -> queries/impact/snapshots -> CLI / API / viewer
```

Every stage is a function from immutable inputs to immutable records plus diagnostics.
Nothing in the pipeline imports, executes, compiles-for-execution or installs analyzed
code (D-0015, `docs/safety-policy.md`); the analyzer performs no network I/O (D-0006).

## 2. Layers and the dependency rule

Packages live under `src/code_analysis/`. Each module is assigned to exactly one layer by
the **longest dotted prefix** in the table (so `graph.schema` is in layer 1 even though
`graph` is in layer 6). The table is normative; `tests/test_t003.py::TestImportLayering`
parses it and checks the same map against every module's imports.

| Layer | Name | Packages | Status | Contents |
|---|---|---|---|---|
| 0 | foundation | `core` | implemented (T001) | configuration, pattern matching, shared primitives; stdlib only |
| 1 | records | `graph.schema`, `evidence`, `diagnostics` | planned (T004) | immutable node/edge/evidence/diagnostic dataclasses, stable-ID derivation, schema version; no I/O |
| 2 | input | `discovery`, `syntax` | `discovery` implemented (T001); `syntax` stub (T002/T006) | safe file discovery and hashing; parsing into trees with spans and parse diagnostics |
| 3 | structure | `scopes`, `imports`, `symbols` | planned (T007–T009) | lexical scopes and bindings, import resolution, definitions and class structure |
| 4 | semantics | `resolution`, `dataflow` | planned (T011–T015) | reference/call resolution, bounded points-to, def-use flow, uncertainty states |
| 5 | dependency | `metadata`, `compat` | planned (T016–T021) | manifests, locks, installed metadata, environments, API inventories, compatibility findings |
| 6 | persistence | `graph` | stub (T004/T022) | `graph.store`: the storage adapter (SQLite default) and migrations |
| 7 | queries | `graph.query`, `impact`, `snapshots` | planned (T022–T025) | bounded paginated traversals, search, impact, snapshot diff |
| 8 | interfaces | `cli`, `api`, `viewer`, `__main__` | `cli` stub (T003); T024/T026/T027 | argparse CLI, optional loopback HTTP API, optional viewer |

Rules (all enforced by the test):

- **R1 — downward only.** A module imports only from its own layer or a lower one.
  Consequences: `graph.store` never imports `syntax` or any analysis package; analysis
  packages never import storage; `graph/__init__.py` cannot re-export `graph.query`.
- **R2 — public API across packages.** No module imports an underscore-prefixed module or
  name from another layer package. `cli` therefore depends on `graph.query`, `impact`
  and `snapshots` only through what they export.
- **R3 — absolute imports only** (`from code_analysis.x import y`; ruff `TID252`).
- **R4 — every module is mapped.** A new package must be added to the table (and to the
  test's map) in the same change, with a decision entry.
- **R5 — third-party imports in `src/` are limited to declared runtime dependencies**
  (currently none, D-0029).
- **R6 — `code_analysis/__init__.py` imports no subpackage**; importing the package is
  cheap and side-effect free. It exposes `__version__`, the single source of the version
  (D-0035).

Same-layer imports are allowed; keep cycles out by review.

## 3. Records versus storage

- **Immutable records** (`@dataclass(frozen=True, slots=True)`, validated in
  `__post_init__`) are the only values that cross layer boundaries: `WorkspaceConfig`,
  `SourceFile`, `PackageInfo`, `Diagnostic`, `DiscoveryResult` today; graph nodes, edges,
  evidence and findings from T004 on. Collections inside records are tuples, sorted
  deterministically (SPEC §3.6).
- **Mutable state** is confined to the inside of one stage (e.g. `_State`/`_Frame` in
  `discovery.walk`) and is converted to records before it leaves.
- **Storage** (`graph.store`, planned) is an explicit adapter behind which SQLite is the
  default candidate (SPEC §5.4; no Neo4j, no external service). Analysis stages never see
  a connection; they produce records that a publisher writes transactionally per
  snapshot. The adapter is the extension point for a graph-native backend later.
- **Queries** (`graph.query`, planned) read through the adapter with cursor pagination,
  bounded traversal depth/node counts and truncation metadata; they never load the whole
  graph.

## 4. Stable identities

- A workspace is an ordered tuple of roots with stable `root_id`s (D-0018).
- The canonical workspace path of anything on disk is `"<root_id>:<posix relative
  path>"`; it is a pure function of the real tree (symlinks never change it, D-0025).
- T004 extends this into graph IDs: `workspace_path` + node kind + lexical location /
  qualified name, with collision handling and explicit rules for edits (planned;
  SPEC §5.3). Snapshot IDs, file hashes (SHA-256 of raw bytes, D-0021) and the analyzer
  version are stored with every snapshot.

## 5. Diagnostics and evidence conventions

Established by discovery (D-0022) and to be generalised by T004/T010:

- A diagnostic is a frozen record `(code, severity, root_id, path, message)` where `code`
  is a `StrEnum` whose string value is part of the public JSON output and never renamed
  without a schema entry; `severity` is `info | warning | error`.
- "No silent omission": every skipped, rejected, truncated or unresolved item yields a
  diagnostic or an explicit aggregate counter.
- Messages contain paths, pattern text and numbers only — never file content or
  secrets (SPEC §3.7). Later evidence excerpts (D-0012) are short and redacted (T004).
- Resolution states on edges are `resolved | candidate | unknown | external_unresolved`
  with a reason code and evidence; impact categories are `certain | possible | unknown`
  (D-0009). Confidence is never a fabricated probability (SPEC §3.4).

## 6. Extension points

- **Roots and cross-repository graphs** (D-0010): `RootKind` gains members and optional
  fields; the tuple-of-roots shape and the `root_id:` namespace do not change.
- **Storage adapter** (SPEC §5.4): `graph.store` is the only module that knows the
  backend; a second backend implements the same adapter interface.
- **Optional interfaces** (D-0003, D-0013): a read-only loopback HTTP API with an OpenAPI
  document (`api`, T026) and a browser viewer (`viewer`, T027) sit in layer 8 and consume
  only `graph.query`/`impact`/`snapshots`.
- **Parsers** (D-0002): the `syntax` layer isolates the choice between stdlib `ast` on
  the host interpreter and a version-independent parser (T002); nothing above it sees
  parser-specific types except through the records it emits.
- **Compatibility rule packs and metadata snapshots** (D-0006, D-0011): `metadata` and
  `compat` read only local artifacts and user-supplied snapshots with provenance.

## 7. Module layout today

```
src/code_analysis/
  __init__.py        __version__ only (R6)
  __main__.py        python -m code_analysis
  core/              config.py, patterns.py
  discovery/         models.py (records), walk.py (safe walk), __init__.py (public API)
  syntax/            stub: parser boundary (T002/T006)
  graph/             stub: schema/store/query layout (T004/T022/T024)
  cli/               app.py: argparse stub (--version, --help; T024 adds commands)
```

Tooling (`pyproject.toml`, `Makefile`): setuptools backend (D-0030), Python >= 3.12
(D-0031), ruff rule set (D-0032), mypy `--strict`, pytest with branch coverage >= 90%
(D-0033), `make` targets (D-0034), offline wheel builds checked against `src/` (D-0041).
`scripts/` holds development-only tooling outside the package (`check_install.py`,
which verifies the editable install and explains the iCloud Drive hidden-`.pth`
problem, D-0040); it is type-checked and linted like `src/` and `tests/` but never
shipped. Dependencies and licenses: `docs/dependencies.md`.
