# Task runner for code-analysis (D-0034).  GNU make 3.81 (the macOS default) is enough.
# Every target runs the tools of the project virtualenv; override the location with
# `make VENV=path/to/venv <target>` (keep the venv outside iCloud Drive, D-0040).
# Windows users run the same commands by hand (README).

VENV ?= .venv
PYTHON ?= python3
BIN := $(VENV)/bin
# Mirrors [tool.coverage.report] fail_under in pyproject.toml (D-0033).
COV_FAIL_UNDER ?= 90

.PHONY: help venv install check-install build test typecheck lint format coverage licenses check clean-build clean

help:  ## Show the available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

venv:  ## Create the virtualenv if it does not exist
	@test -x $(BIN)/python || $(PYTHON) -m venv $(VENV)

install: venv clean-build  ## Editable install plus pinned dev tools, then verify the install is usable (D-0040)
	@# `pip install --group` (PEP 735) needs pip >= 25.1; `python -m venv` may ship an older one (D-0042).
	$(BIN)/python -m pip install --upgrade "pip>=25.1"
	$(BIN)/pip install -e .
	$(BIN)/pip install --group dev
	$(BIN)/python scripts/check_install.py

check-install:  ## Verify `import code_analysis` works from the venv; explain the cause if not (D-0040)
	$(BIN)/python scripts/check_install.py

build: venv clean-build  ## Build a wheel into dist/ with the venv's pinned setuptools, offline (D-0041)
	$(BIN)/pip wheel --no-deps --no-build-isolation --no-index --wheel-dir dist .

test:  ## Run the test suite
	$(BIN)/pytest -q

typecheck:  ## mypy --strict over src, tests and scripts
	$(BIN)/mypy --strict src tests scripts

lint:  ## ruff lint and format check
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format:  ## Apply ruff formatting and safe autofixes
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .

coverage:  ## Tests with branch coverage; fails below $(COV_FAIL_UNDER)% (D-0033)
	$(BIN)/pytest -q --cov=code_analysis --cov-branch --cov-report=term-missing --cov-fail-under=$(COV_FAIL_UNDER)

licenses:  ## Licenses of everything installed in the venv (policy: docs/dependencies.md, D-0029)
	$(BIN)/pip-licenses --format=markdown --with-urls --order=name

check: lint typecheck coverage  ## All local gates (what CI runs, T030)

clean-build:  ## Remove build/, dist/ and egg-info so no stale module is swept into a wheel (D-0041)
	rm -rf build dist src/*.egg-info

clean: clean-build  ## Remove caches and build artefacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage .coverage.* htmlcov coverage.xml
	find . -name __pycache__ -type d -prune -not -path './.venv/*' -exec rm -rf {} +
