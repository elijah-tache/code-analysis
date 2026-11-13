# Dependencies and licenses

Status: in force (T003, D-0029; policy from the user, D-0008 / Q07). The tables below are
machine-checked by `tests/test_t003.py::TestDependencyPolicy` against `pyproject.toml`
and, where a distribution is installed, against its metadata. Updating `pyproject.toml`
without updating this file fails the tests.

## License policy

- The analyzer is offline (D-0006) and treats analyzed code as untrusted (D-0015); every
  third-party package that runs inside it widens the audit surface, so **zero runtime
  dependencies** is the default and each addition needs a decision entry.
- Runtime dependencies and anything vendored must carry a permissive license.
  Allowed SPDX identifiers: `MIT`, `MIT-0`, `BSD-2-Clause`, `BSD-3-Clause`, `0BSD`,
  `Apache-2.0`, `PSF-2.0`, `Python-2.0`, `ISC`, `Zlib`.
  An `OR` expression is acceptable when any branch is allowed; an `AND` expression only
  when every branch is. Not acceptable for runtime use: MPL, LGPL, GPL, AGPL, EUPL, SSPL,
  BUSL, CC-BY-SA or any source-available/non-commercial license.
- Development-only tools are held to the same preference; a copyleft *transitive* tool
  dependency (e.g. `pathspec`, MPL-2.0, pulled in by mypy) is tolerated because it is
  neither imported by nor shipped with the analyzer, and it is listed below.

## Pin policy

| Kind | Requirement form | Why |
|---|---|---|
| runtime (`[project] dependencies`) | `name==X` or bounded range `name>=a,<b` / `name~=a.b` | co-installable with other tools, protected from breaking majors; the tested version is recorded here |
| development (`[dependency-groups] dev`) | exact `name==X` | reproducible local and CI runs |
| build (`[build-system] requires`) | bounded range | reproducible builds without blocking patch releases |

## Runtime dependencies

| Distribution | Import name | Requirement | Tested version | License (SPDX) | Purpose | Alternative considered | Why chosen |
|---|---|---|---|---|---|---|---|
| _none_ | | | | | | | |

Standard-library modules carry the load: `tomllib` (TOML manifests and locks),
`argparse` (CLI), `dataclasses` (frozen records), `sqlite3` (storage adapter, SQLite
3.45.1 on the development host), `ast` (parsing), `hashlib` (SHA-256), `json`, `re`,
`os`/`pathlib`.

## Pre-approved runtime candidates (not yet added)

| Distribution | Import name | Planned requirement | License (SPDX) | Purpose | Alternative considered | Decision |
|---|---|---|---|---|---|---|
| packaging | packaging | `packaging>=26.3,<27` | Apache-2.0 OR BSD-2-Clause | PEP 440 versions/specifiers, PEP 508 requirements and markers, wheel tags (SPEC §7) | hand-written parser (large, subtle; rejected) | approved for T016; add with a decision entry and a row above |

## Evaluated and not adopted

| Candidate | License (SPDX) | Would replace | Decision and rationale |
|---|---|---|---|
| tomli | MIT | `tomllib` | not needed: runtime floor is 3.12 (D-0031), `tomllib` is in the stdlib since 3.11 |
| any lockfile parser | — | hand-written adapters | not needed: `poetry.lock`/`uv.lock`/`pdm.lock` are TOML, `Pipfile.lock` is JSON; adapters with diagnostics are T017/T018 (D-0005) |
| libcst | MIT (parser portions derived from CPython, PSF-2.0) | stdlib `ast` | license acceptable; kept out until T002 decides the multi-version parsing strategy (D-0002) |
| parso | MIT (grammar files PSF-2.0) | stdlib `ast` | license acceptable; same deferral to T002; note: version-selectable grammars but no 3.13+/3.14 grammar guarantee |
| click | BSD-3-Clause | `argparse` | not needed: argparse covers subcommands, `--help`, `--json`, exit codes (D-0036) |
| typer | MIT (depends on click; rich optional) | `argparse` | same as click; adds two transitive dependencies |
| pydantic | MIT (compiled core, `pydantic-core`) | frozen dataclasses | not needed: validation lives in `__post_init__`; avoids a compiled dependency in the trust boundary |
| pathspec | MPL-2.0 | `core.patterns` | rejected in D-0019 (copyleft); documented gitignore subset implemented with `re` |
| import-linter | BSD-2-Clause | layering test | not needed: the rule fits in one `ast`-based test (D-0028) |
| nox / tox | MIT / MIT | `Makefile` | not needed: GNU make is present everywhere the project runs (D-0034) |
| hatchling / flit-core | MIT / BSD-3-Clause | setuptools | not adopted: setuptools is already configured and the editable-install problem was not backend-related (D-0030; real cause: iCloud Drive hides the `.pth` file, D-0040) |
| build | MIT | `pip wheel` | not needed: `pip wheel --no-build-isolation` with the venv's pinned setuptools builds the wheel offline (D-0041); the sdist path is covered by T030's clean `pip install .` |
| Neo4j or other graph service | GPL-3.0 (community server) / proprietary | SQLite adapter | excluded by SPEC §5.4 ("do not require Neo4j or an external service") |

## Development dependencies

| Distribution | Import name | Requirement | Tested version | License (SPDX) | Purpose | Alternative considered | Why chosen |
|---|---|---|---|---|---|---|---|
| pytest | pytest | pytest==9.2.0 | 9.2.0 | MIT | test runner | unittest (stdlib) | fixtures, parametrisation, strict markers/xfail |
| mypy | mypy | mypy==2.4.1 | 2.4.1 | MIT | strict static typing | pyright (MIT, needs Node.js) | pure Python toolchain, `--strict` already in use |
| ruff | ruff | ruff==0.17.5 | 0.17.5 | MIT | lint + format | flake8 + isort + black (MIT) | one fast tool, rule families recorded in D-0032 |
| pytest-cov | pytest_cov | pytest-cov==7.1.0 | 7.1.0 | MIT | coverage integration for pytest | `coverage run -m pytest` | `--cov-fail-under`, single command (D-0033) |
| coverage | coverage | coverage==7.17.3 | 7.17.3 | Apache-2.0 | branch coverage measurement | none maintained | the only maintained implementation |
| pip-licenses | piplicenses | pip-licenses==5.5.5 | 5.5.5 | MIT | license report (`make licenses`) | a hand-written `importlib.metadata` script | ready-made report formats and `--fail-on`; transitive: prettytable (BSD-3-Clause), wcwidth (MIT) |
| setuptools | setuptools | setuptools==84.2.1 | 84.2.1 | MIT | build backend present in the venv so `make build` and the wheel-contents test run offline without build isolation (D-0041) | `build` (MIT; needs network for isolated builds) | same distribution as the build requirement; the exact pin satisfies `setuptools>=77,<85` (checked by the tests) |

## Build dependencies

| Distribution | Requirement | License (SPDX) | Purpose | Alternative considered | Why chosen |
|---|---|---|---|---|---|
| setuptools | setuptools>=77,<85 | MIT | build backend (`setuptools.build_meta`) | hatchling (MIT), flit-core (BSD-3-Clause) | D-0030 |

## Transitive development-only packages observed in `.venv/` (2026-11-13)

For transparency; none are imported by the analyzer: pluggy (MIT), iniconfig (MIT),
packaging (Apache-2.0 OR BSD-2-Clause), Pygments (BSD-2-Clause), typing_extensions
(PSF-2.0), mypy_extensions (MIT), pathspec (MPL-2.0), librt (MIT), ast_serialize (MIT),
prettytable (BSD-3-Clause), wcwidth (MIT). `pip` itself (MIT) is part of the venv.
Regenerate with `make licenses`.
