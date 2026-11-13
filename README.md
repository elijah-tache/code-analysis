# code-analysis

A deterministic, offline, **non-executing** Python code intelligence engine
(Stage 1: static analysis only). It indexes a repository into a provenance-rich graph
and answers where symbols come from, how they are used and what may break when they
change. See `SPEC.md` for the full contract, `docs/architecture.md` for the layered
design and `docs/safety-policy.md` for the safety boundary.

Current state: P0 foundation. Implemented so far: workspace configuration and safe,
deterministic file discovery (`code_analysis.core.config`, `code_analysis.discovery`),
the package architecture and tooling (T003), and a CLI stub that only knows
`--version`/`--help` (the SPEC commands arrive with T024).

## Requirements

- Python 3.12 or newer for the analyzer runtime (D-0031). The *analyzed* syntax range
  (3.8-3.14, D-0002) is a separate matter decided in T002.
- No runtime dependencies (D-0029; policy and tables in `docs/dependencies.md`).

## License

Not yet decided: the project license is a pending user decision (`DECISIONS.md`
D-0037). Until then no license is claimed in the package metadata and there is no
`LICENSE` file; the code may not be redistributed.

## Install (development)

```sh
make install                               # venv + editable install + pinned dev tools, then checks the install
make VENV=~/.venvs/code-analysis install   # same, with the virtualenv outside the repository
```

Equivalent manual steps:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade "pip>=25.1"   # `--group` needs pip 25.1+ (D-0042)
.venv/bin/pip install -e .
.venv/bin/pip install --group dev        # pytest, mypy, ruff, pytest-cov, coverage, pip-licenses, setuptools
.venv/bin/python scripts/check_install.py
```

`scripts/check_install.py` (also `make check-install`) verifies, in a fresh `python -I`,
that `import code_analysis` resolves to this repository's `src/`; it fails with the cause
and the options below instead of reporting success when the editable install is inert.

**Keep the repository and its virtualenv out of iCloud Drive** and of any other
cloud-sync folder that hides dot-files. With "Desktop & Documents" sync on, that
includes `~/Desktop` and `~/Documents`. iCloud Drive sets the macOS `UF_HIDDEN` flag on
every dot-path it manages (`.git`, `.venv/**`, the `__editable__*.pth` file) a few
seconds after the path is written, and CPython's `site.py` skips hidden `.pth` files,
so an editable install becomes inert within seconds; `chflags nohidden` does not last
(D-0040). Options:

1. move the repository (with its virtualenv) out of the synced folder;
2. keep the repository where it is and create the virtualenv elsewhere:
   `make VENV=~/.venvs/code-analysis install`, then pass the same `VENV=` to every
   `make` target (`PYTHON=` selects the interpreter used to create it);
3. leave both where they are: the test suite never depends on the install (pytest adds
   `src/` to `sys.path` itself, `pythonpath = ["src"]` in `pyproject.toml`) and
   `PYTHONPATH=src python -m code_analysis` works; only `import code_analysis` outside
   the repository and the `code-analysis` console script stay broken.

Which option applies to this repository is an open user decision (Q14).

## Test, type-check, lint, coverage

```sh
make check            # lint + typecheck + coverage (the CI gate, T030)
make test             # .venv/bin/pytest -q
make typecheck        # .venv/bin/mypy --strict src tests scripts
make lint             # .venv/bin/ruff check . && .venv/bin/ruff format --check .
make coverage         # pytest with branch coverage, fails below 90% (D-0033)
make licenses         # license report of everything installed in the venv
make build            # wheel into dist/ with the venv's pinned setuptools, offline (D-0041)
make help             # all targets
```

`make build` and `make install` first run `make clean-build` (removes `build/`, `dist/`
and `src/*.egg-info`) so that no stale module from an earlier layout is swept into a
wheel; `tests/test_t003.py::TestWheelContents` builds a wheel from a clean copy and
checks that it contains exactly the files under `src/code_analysis/`.

`tests/fixtures/` contains data trees used by tests; they are excluded from
collection, type checking and linting and must never be imported. Known limitations
are pinned with strict `xfail` tests (currently: no directory-swap protection in the
no-`dir_fd` fallback mode, D-0039, owned by T029).

## Command line

```sh
code-analysis --version        # after a usable `make install` (see "Install")
python -m code_analysis --help # works from the repository with PYTHONPATH=src as well
```

Exit codes: `0` success (including `--help`/`--version`), `2` usage error. The full
table is defined with the commands in T024.

## Quick example

```python
from pathlib import Path

from code_analysis.core.config import WorkspaceConfig
from code_analysis.discovery import discover

config = WorkspaceConfig.single_root(Path("/abs/path/to/repo"), root_id="repo")
result = discover(config)
for f in result.files:
    print(f.workspace_path, f.sha256)
for d in result.diagnostics:
    print(d.code, d.path, d.message)
```

Discovery only reads bytes to hash files. It never imports or executes anything from
the analyzed tree.

## Project documents

`SPEC.md`, `IMPLEMENTATION_PLAN.md`, `tasks.json`, `OPEN_QUESTIONS.md`,
`REQUIREMENTS_TRACEABILITY.md`, `DECISIONS.md` (append-only decision log),
`CHANGELOG.md`, `docs/architecture.md`, `docs/dependencies.md`, `docs/safety-policy.md`.
