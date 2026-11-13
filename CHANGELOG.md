# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The single source of the version number is `code_analysis.__version__` (D-0035).

## [Unreleased]

### Added
- T001: workspace configuration (`code_analysis.core.config`), gitignore-style pattern
  subset (`code_analysis.core.patterns`) and safe, deterministic, non-executing file
  discovery (`code_analysis.discovery`) with diagnostics and a content fingerprint.
- T003: layered package architecture with an enforced import rule
  (`docs/architecture.md`), dependency and license policy (`docs/dependencies.md`),
  `Makefile` task runner, branch-coverage gate (90%), extended ruff rule set, dynamic
  single-source version, `code-analysis` console script and `python -m code_analysis`
  stub (`--version`, `--help`), stub packages `syntax`, `graph`, `cli`.

### Changed
- T003: `pyproject.toml` no longer claims a license; the project license is a pending
  user decision (D-0037).
- T003: file opens in discovery add `O_BINARY` where the platform defines it (D-0038).
- T003: safety documentation states precisely what `realpath` does on outside symlink
  targets and that the no-`dir_fd` fallback mode has no directory-swap protection
  (D-0039).
- T003: `make install` no longer runs `chflags nohidden`; it ends with
  `scripts/check_install.py`, which fails with the real cause (iCloud Drive re-hides the
  editable `.pth` file; CPython skips hidden `.pth` files) and the documented options
  (D-0040, supersedes the D-0030 root-cause analysis).
- T003: `make install` and the new `make build` run `clean-build` first so stale
  `build/` contents are never swept into a wheel; `setuptools==84.2.1` joins the dev
  group so wheels build offline; a test checks wheel contents against `src/` (D-0041).

### Security
- T001: analyzed trees are never imported or executed; symlink escapes are rejected;
  descriptor-relative traversal closes the directory lstat/open race on POSIX.
