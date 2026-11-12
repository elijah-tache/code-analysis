# code-analysis

A deterministic, offline, **non-executing** Python code intelligence engine
(Stage 1: static analysis only). It indexes a repository into a provenance-rich graph
and answers where symbols come from, how they are used and what may break when they
change. See `SPEC.md` for the full contract and `docs/safety-policy.md` for the safety
boundary.

Current state: P0 foundation. Implemented so far: workspace configuration and safe,
deterministic file discovery (`code_analysis.core.config`, `code_analysis.discovery`).

## Requirements

- Python 3.12 or newer (analyzer runtime; the *analyzed* syntax range is a separate
  matter, see `DECISIONS.md` D-0002).
- No runtime dependencies.

## Install (development)

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pip install --group dev        # pytest, mypy, ruff (pinned in pyproject.toml)
```

## Test, type-check, lint

```sh
.venv/bin/pytest -q
.venv/bin/mypy --strict src tests
.venv/bin/ruff check .
```

`tests/fixtures/` contains data trees used by tests; they are excluded from
collection, type checking and linting and must never be imported.

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
`REQUIREMENTS_TRACEABILITY.md`, `DECISIONS.md` (append-only decision log).
