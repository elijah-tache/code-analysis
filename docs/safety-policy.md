# Safety policy — workspace scope and non-execution boundary

Status: in force for Stage 1 (T001). Decisions: D-0015, D-0016, D-0018, D-0019, D-0021 – D-0023,
D-0025 (symlinks; supersedes D-0020), D-0026 (descriptor-relative traversal), D-0027 (output shape).
Normative source: `SPEC.md` §3 (hard boundaries), §4 (inputs), §6 step 1, §9 (security tests).

## 1. Non-execution boundary

The analyzer **never imports, executes, evaluates, compiles-for-execution, installs or
builds** code from an analyzed workspace, and never runs `setup.py`, build backends,
plugins, hooks, project test suites, or any subprocess on target content.

Concretely, for discovery (`code_analysis.discovery`):

- Files are read as **bytes only**, exclusively to compute a SHA-256 content hash.
  The bytes are discarded; they are not decoded, parsed, stored, or passed anywhere.
- The implementation contains no use of `exec`, `eval`, `compile`, `importlib`,
  `runpy`, `subprocess`, `os.system`, `os.spawn*`, `os.exec*` or `os.fork`.
- Later stages (parsing, T006) will use `ast.parse` only. Parsing never executes
  code; `compile(..., "exec")` followed by execution is prohibited project-wide.
- Changing any of this requires a `needs-user` decision entry (D-0016).

There is deliberately **no configuration option** that relaxes this boundary.

## 2. Untrusted-input stance

Everything under a workspace root — source, stubs, `setup.py`, `pyproject.toml`,
lockfiles, metadata, symlinks, file names — is treated as hostile input:

- Pathological layouts (deep nesting, millions of entries, huge files, link cycles,
  links escaping the root, FIFOs/devices, undecodable names) must degrade into
  **diagnostics and bounded results**, never into hangs, crashes or execution.
- Nothing discovered influences how the analyzer itself runs (no plugin loading,
  no configuration read from the target tree in this stage).

## 3. Workspace model

- A workspace is an **ordered tuple of roots**. Each root has a stable `root_id`
  (`[a-z0-9][a-z0-9_.-]{0,63}`, matched in full, unique per workspace, defaulting to a
  sanitized directory name) and an **absolute** path that is resolved to its real path.
- Roots must exist, be directories, and must not overlap.
- Every discovered item is identified by its canonical workspace path
  `"<root_id>:<posix relative path>"`. Stable graph IDs derive from it (T004).
- **Canonical paths never depend on symbolic links** (D-0025): only real directories
  are traversed, so adding or removing an alias link anywhere in a root leaves every
  existing file's and package's canonical path unchanged.
- Future cross-repository support adds new `RootKind` members and optional fields;
  the tuple-of-roots shape does not change (D-0010, D-0018).

## 4. Discovery rules

| Rule | Default | Behaviour when triggered |
|---|---|---|
| Include patterns | `**/*.py`, `**/*.pyi` | Files not matching are counted in `summary.ignored_files`, not reported individually (this includes sockets/FIFOs with non-source names). |
| Exclude patterns | `.git .hg .svn __pycache__ .venv venv .tox .nox .mypy_cache .pytest_cache .ruff_cache node_modules *.egg-info` | Matching directories are pruned with one `excluded_by_pattern` diagnostic; matching source files get one each. Matching **symlinks** get one and are **never resolved** (a directory-only pattern such as `build/` also matches a link named `build`, because an unresolved link's type is unknown). |
| Symlink policy | `never` | See §4.1. Escapes are rejected under every policy. |
| File size cap | 2 MiB | `file_too_large`; the file is not hashed. Checked via `lstat`, then again on the open descriptor, and enforced while reading (at most cap+1 bytes consumed). |
| Non-regular files | — | `not_regular_file` for a source candidate that is a device, socket or FIFO; never opened (prevents blocking). Non-candidates are only counted. |
| Max files | 100 000 | `limit_reached` (error), `result.truncated = True`, walk stops deterministically. |
| Max depth | 64 | `max_depth_exceeded`; deeper directories are not entered. |
| Max entries | 2 000 000 | `limit_reached`, truncated. |
| Unreadable entries | — | `unreadable` with the OS error text (no content). Also emitted when a directory or file was replaced by a link after classification (see §4.2). |
| Undecodable names | — | `invalid_filename`. |

### 4.1 Symbolic links (D-0025)

Links are handled in this order; the first matching rule wins and nothing later runs:

1. The link's own path matches an exclusion → `excluded_by_pattern`; the target is not
   resolved.
2. The link resolves (`realpath`, link metadata only) outside the root's real path →
   `symlink_escapes_root` (warning). The outside target is never `stat`-ed, so the
   analyzer does not learn whether it exists.
3. The in-root target does not exist (or the link loops onto itself) →
   `symlink_target_missing`.
4. `symlink_policy = never` → `symlink_not_followed` (info).
5. `symlink_policy = within_root` and the target is a **directory** → never traversed.
   `symlink_cycle` when the target is an ancestor of the link's own directory, otherwise
   `symlink_alias`; the message names the real root-relative path, under which the
   directory is reported anyway.
6. `symlink_policy = within_root` and the target is a **file** inside an excluded
   directory (or itself excluded) → `excluded_by_pattern` on the link.
7. Otherwise (`within_root`, file target) the real file is hashed under the link's
   logical path *in addition to* its own path; identical hashes make the alias visible.

### 4.2 Open-file and open-directory hardening (D-0026)

Directories are opened with `O_DIRECTORY | O_NOFOLLOW` relative to the already-open
descriptor of their parent (`dir_fd`) and listed with `os.scandir(fd)`; every type check is
descriptor-relative with `follow_symlinks=False`. Files are opened with `O_NOFOLLOW`
relative to the same descriptor and re-checked with `fstat` for type and size. An entry
that is swapped for a symlink after it was classified therefore fails with
`ELOOP`/`ENOTDIR` and is reported as `unreadable` instead of being followed. At most
`max_depth + 1` descriptors are open at any time.

Known residual limitations (handed to T029): a file link followed under `within_root` is
opened by its resolved absolute path, so a *component* of that path swapped for a link in
the same instant is not detected (the final component still has `O_NOFOLLOW`); on
platforms without `dir_fd` support (Windows) the walk runs on absolute paths with only
the final-component protection; `realpath` itself is not atomic with respect to the
later `stat` of an in-root target.

### Pattern syntax (gitignore-style subset, D-0019)

- Matched against the root-relative POSIX path.
- Contains `/` → anchored at the root (leading `/` optional); otherwise matches the
  basename at any depth.
- `*` within a segment, `?` one character, `[...]` class, `**` zero or more segments,
  trailing `/` = directories only.
- Not supported and rejected at configuration time: negation `!`, backslash escapes,
  comments, absolute patterns, `.`/`..` segments, malformed classes (`[]`, `[z-a]`).
- Case-sensitive everywhere.

### Package identification (D-0022)

Directories that directly contain a source file or a package directory are reported:
`regular` when `__init__.py` is present, otherwise `namespace_candidate`.
`has_init_pyi` and `importable_name` (valid non-keyword identifier) are reported as
facts. Whether a candidate is really importable depends on the search path and is
decided by import resolution (T008), not asserted by discovery. The root directory is
reported only if it has its own `__init__.py`.

## 5. Determinism and output shape

Entries are processed in sorted name order, roots in configured order, and results
are sorted by `(root order, relative path)`; diagnostics by `(root order, path, code,
message)`. Two runs over the same tree and configuration yield equal `DiscoveryResult`
objects and the same `content_fingerprint()` — a SHA-256 over the ordered
`workspace_path NUL sha256 LF` lines of all files (D-0027). `to_dict()` is the stable
JSON shape (`files`, `packages`, `diagnostics`, `summary`; enums as their string values).

## 6. Secrets, paths and content

- No file content is kept in any result record; only paths, sizes, hashes and flags.
- Diagnostic messages contain paths, pattern text and numbers only.
- Later stages that keep short evidence excerpts (D-0012) must apply redaction rules
  defined in T004; logs must never print credentials; there is no telemetry.
- Excluded paths are honoured everywhere: an excluded subtree is never read, an
  excluded link is never resolved, and a file link into an excluded subtree is not
  followed.

## 7. How tests enforce this (`tests/test_t001.py`)

- **Non-execution**: a hostile fixture (a `setup.py` and a module whose top-level code
  writes a sentinel file) is generated in a temporary directory and discovered inside a
  `tripwires()` block that patches `exec`, `eval`, `compile`, `subprocess.Popen`,
  `os.system`, `os.posix_spawn`, `os.spawnv`, `os.execv`, `os.fork`,
  `importlib.import_module`, `runpy.run_path` and `__import__` (for not-yet-loaded
  modules) to fail. The patches are scoped to the `discover` call only, so a failing
  assertion is reported normally. The sentinel must be absent and no `__pycache__` may
  appear.
- **Symlink escape**: links to a file and a directory outside the root are rejected
  with `symlink_escapes_root` under both policies and their contents never appear;
  a dangling link to an outside path is an escape, not a "missing" report.
- **Canonical-path independence**: adding an alias link (`pkg -> src/pkg`) and
  removing it again leaves files, packages and the fingerprint identical.
- **Excluded links**: `.venv -> <outside>` yields `excluded_by_pattern` and `realpath`
  is never called on it.
- **TOCTOU**: a directory replaced by a link between classification and open is
  reported `unreadable`; `_hash_regular_file` refuses a link (`ELOOP`); no descriptor
  leaks even when the walk is truncated.
- **Huge files**: a file over the cap yields `file_too_large` and no hash.
- **Exclusions**: excluded directories are pruned with a diagnostic.
- **Determinism**: two runs are equal, with identical hashes and fingerprint.
- **Unknown cases**: a directory without `__init__.py` is a `namespace_candidate`.
- The analyzer source is also parsed for forbidden execution primitives, including
  `from os import system` style imports.

## 8. Deferred verification

CI gates (T030) and the 10k-file performance benchmark (T028) are deferred to those
tasks; T001 verified AC-11 locally with `pytest`, `mypy --strict`, `ruff` and the
mutation checks listed in the T001 developer report (escape, cap, ordering, policy,
`O_NOFOLLOW` on files and directories, tripwire reporting).
