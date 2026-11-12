"""T001 — workspace scope and safety policy.

Covers: configuration validation (D-0018), pattern semantics (D-0019), deterministic
multi-package discovery, symlink handling (D-0020), size caps and traversal bounds
(D-0021), diagnostics and package identification (D-0022), and the non-execution
boundary (D-0015, D-0023).  Hostile content and symlinks are generated in ``tmp_path``.
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import dataclasses
import errno
import hashlib
import importlib
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from code_analysis import __version__
from code_analysis.core.config import (
    DEFAULT_EXCLUDE_PATTERNS,
    DEFAULT_INCLUDE_PATTERNS,
    DEFAULT_MAX_FILE_SIZE_BYTES,
    ConfigError,
    RootKind,
    SafetyPolicy,
    SymlinkPolicy,
    TraversalLimits,
    WorkspaceConfig,
    WorkspaceRoot,
    derive_root_id,
)
from code_analysis.core.patterns import PatternError, compile_pattern
from code_analysis.discovery import (
    Diagnostic,
    DiagnosticCode,
    DiscoveryResult,
    PackageKind,
    Severity,
    SourceKind,
    discover,
)
from code_analysis.discovery import walk as walk_module

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES = TESTS_DIR / "fixtures"
WORKSPACE_FIXTURE = FIXTURES / "t001_workspace"
SRC_DIR = TESTS_DIR.parent / "src" / "code_analysis"

EXPECTED_FIXTURE_FILES: tuple[str, ...] = (
    "nspkg/inner/__init__.py",
    "nspkg/inner/thing.py",
    "nspkg/mod.py",
    "pkg_a/__init__.py",
    "pkg_a/core.py",
    "pkg_a/sub/__init__.py",
    "pkg_a/sub/leaf.py",
    "pkg_b/__init__.py",
    "pkg_b/api.py",
    "pkg_b/api.pyi",
    "scripts/tool.py",
    "vendor_excluded/__init__.py",
    "vendor_excluded/lib/vendored.py",
)


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------


def _config(root: Path, root_id: str = "ws", **kwargs: Any) -> WorkspaceConfig:
    return WorkspaceConfig(roots=(WorkspaceRoot(root_id=root_id, path=root),), **kwargs)


def _paths(result: DiscoveryResult) -> list[str]:
    return [f.relative_path for f in result.files]


def _diags(result: DiscoveryResult, code: DiagnosticCode) -> list[Diagnostic]:
    return [d for d in result.diagnostics if d.code is code]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, content: str = "x = 1\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _safety(**kwargs: Any) -> SafetyPolicy:
    limits = kwargs.pop("limits", None)
    if limits is not None:
        kwargs["limits"] = TraversalLimits(**limits)
    return SafetyPolicy(**kwargs)


# --------------------------------------------------------------------------------------
# package skeleton
# --------------------------------------------------------------------------------------


def test_package_has_version() -> None:
    assert isinstance(__version__, str) and __version__


# --------------------------------------------------------------------------------------
# configuration (D-0018)
# --------------------------------------------------------------------------------------


class TestConfig:
    def test_single_root_defaults(self, tmp_path: Path) -> None:
        config = WorkspaceConfig.single_root(tmp_path, root_id="repo")
        assert [r.root_id for r in config.roots] == ["repo"]
        assert config.roots[0].path == tmp_path.resolve()
        assert config.roots[0].kind is RootKind.LOCAL_DIRECTORY
        assert config.include_patterns == DEFAULT_INCLUDE_PATTERNS
        assert config.exclude_patterns == DEFAULT_EXCLUDE_PATTERNS
        assert config.safety.symlink_policy is SymlinkPolicy.NEVER
        assert config.safety.max_file_size_bytes == DEFAULT_MAX_FILE_SIZE_BYTES == 2 * 1024 * 1024
        assert config.safety.limits == TraversalLimits(
            max_files=100_000, max_depth=64, max_entries=2_000_000
        )

    def test_root_id_derived_from_directory_name(self, tmp_path: Path) -> None:
        repo = tmp_path / "My Repo.Name"
        repo.mkdir()
        assert derive_root_id(repo) == "my-repo.name"
        assert WorkspaceRoot.from_path(repo).root_id == "my-repo.name"
        assert derive_root_id(Path("/")) == "root"
        assert derive_root_id(tmp_path / "---") == "root"

    @pytest.mark.parametrize(
        "root_id",
        ["", "Upper", "has:colon", "-leading", "a" * 65, "sp ace", "ünïcode", "abc\n", "abc\nd"],
    )
    def test_invalid_root_id_rejected(self, tmp_path: Path, root_id: str) -> None:
        with pytest.raises(ConfigError, match="root_id"):
            WorkspaceRoot(root_id=root_id, path=tmp_path)

    def test_relative_root_rejected(self) -> None:
        with pytest.raises(ConfigError, match="must be absolute"):
            WorkspaceRoot(root_id="r", path=Path("relative/dir"))

    def test_missing_root_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="does not exist"):
            WorkspaceRoot(root_id="r", path=tmp_path / "nope")

    def test_file_root_rejected(self, tmp_path: Path) -> None:
        f = _write(tmp_path / "f.py")
        with pytest.raises(ConfigError, match="not a directory"):
            WorkspaceRoot(root_id="r", path=f)

    def test_non_path_root_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match=r"pathlib\.Path"):
            WorkspaceRoot(root_id="r", path=str(tmp_path))  # type: ignore[arg-type]

    def test_duplicate_root_ids_rejected(self, tmp_path: Path) -> None:
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir()
        b.mkdir()
        with pytest.raises(ConfigError, match="duplicate root_id"):
            WorkspaceConfig(roots=(WorkspaceRoot("r", a), WorkspaceRoot("r", b)))

    def test_overlapping_roots_rejected(self, tmp_path: Path) -> None:
        inner = tmp_path / "inner"
        inner.mkdir()
        with pytest.raises(ConfigError, match="overlap"):
            WorkspaceConfig(roots=(WorkspaceRoot("outer", tmp_path), WorkspaceRoot("inner", inner)))
        with pytest.raises(ConfigError, match="overlap"):
            WorkspaceConfig(roots=(WorkspaceRoot("a", tmp_path), WorkspaceRoot("b", tmp_path)))

    def test_empty_roots_rejected(self) -> None:
        with pytest.raises(ConfigError, match="non-empty"):
            WorkspaceConfig(roots=())

    def test_root_symlink_resolved_to_real_path(self, tmp_path: Path) -> None:
        real = tmp_path / "real"
        real.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real, target_is_directory=True)
        root = WorkspaceRoot("r", link)
        assert root.path == real.resolve()

    @pytest.mark.parametrize(
        "pattern",
        ["!negated", "a//b", "../x", "a/../b", "a\\b", "", "#comment", " padded", "C:/abs"],
    )
    def test_unsupported_patterns_rejected(self, tmp_path: Path, pattern: str) -> None:
        with pytest.raises(ConfigError, match="exclude_patterns"):
            _config(tmp_path, exclude_patterns=(pattern,))

    def test_empty_include_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="include_patterns"):
            _config(tmp_path, include_patterns=())

    def test_patterns_must_be_tuples(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="tuple"):
            _config(tmp_path, exclude_patterns=["x"])

    @pytest.mark.parametrize("value", [0, -1, True, 1.5, "3"])
    def test_limits_validation(self, value: Any) -> None:
        for name in ("max_files", "max_depth", "max_entries"):
            with pytest.raises(ConfigError, match=name):
                TraversalLimits(**{name: value})

    @pytest.mark.parametrize("value", [0, -5, False, "big"])
    def test_size_cap_validation(self, value: Any) -> None:
        with pytest.raises(ConfigError, match="max_file_size_bytes"):
            SafetyPolicy(max_file_size_bytes=value)

    def test_symlink_policy_validation(self) -> None:
        with pytest.raises(ConfigError, match="symlink_policy"):
            SafetyPolicy(symlink_policy="follow_everything")  # type: ignore[arg-type]

    def test_single_root_explicit_keywords(self, tmp_path: Path) -> None:
        safety = _safety(symlink_policy=SymlinkPolicy.WITHIN_ROOT, max_file_size_bytes=10)
        config = WorkspaceConfig.single_root(
            tmp_path, "repo", include_patterns=("*.py",), exclude_patterns=(), safety=safety
        )
        assert config.include_patterns == ("*.py",)
        assert config.exclude_patterns == ()
        assert config.safety is safety

    def test_no_policy_follows_links_outside_root(self) -> None:
        # D-0016: the enum must never gain an "escape allowed" option without a needs-user entry.
        assert {p.value for p in SymlinkPolicy} == {"never", "within_root"}

    def test_config_is_immutable(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.include_patterns = ("*.txt",)  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.roots[0].root_id = "other"  # type: ignore[misc]

    def test_multiple_roots_are_ordered_and_namespaced(self, tmp_path: Path) -> None:
        a, b = tmp_path / "alpha", tmp_path / "beta"
        _write(a / "m.py")
        _write(b / "m.py")
        config = WorkspaceConfig(roots=(WorkspaceRoot("second", b), WorkspaceRoot("first", a)))
        result = discover(config)
        assert [f.workspace_path for f in result.files] == ["second:m.py", "first:m.py"]
        assert result.summary.roots == 2


# --------------------------------------------------------------------------------------
# patterns (D-0019)
# --------------------------------------------------------------------------------------


class TestPatterns:
    @pytest.mark.parametrize(
        ("pattern", "path", "is_dir", "expected"),
        [
            ("*.py", "a/b/c.py", False, True),
            ("*.py", "a/b/c.pyi", False, False),
            ("*.py", "c.py", False, True),
            ("**/*.py", "c.py", False, True),
            ("**/*.py", "a/b/c.py", False, True),
            ("**/*.pyi", "a/b/c.py", False, False),
            ("build", "x/build", True, True),
            ("build", "x/build", False, True),
            ("build/", "x/build", False, False),
            ("build/", "x/build", True, True),
            ("/build", "build", True, True),
            ("/build", "x/build", True, False),
            ("src/**", "src/a/b.py", False, True),
            ("src/**", "src", True, False),
            ("docs/*.md", "docs/a.md", False, True),
            ("docs/*.md", "docs/sub/a.md", False, False),
            ("*.egg-info", "pkg/foo.egg-info", True, True),
            ("a/**/b", "a/b", True, True),
            ("a/**/b", "a/x/y/b", True, True),
            ("a/**/b", "a/x/y/bb", True, False),
            ("?.py", "a.py", False, True),
            ("?.py", "ab.py", False, False),
            ("[abc].py", "b.py", False, True),
            ("[!abc].py", "b.py", False, False),
            ("[a-c].py", "b.py", False, True),
            ("te*st", "a/teXYst", False, True),
            ("*.py", "a/b.py/c", False, False),
            ("*", "a/b", False, True),
            ("*", "a/b", True, True),
            ("Build", "x/build", True, False),
        ],
    )
    def test_match(self, pattern: str, path: str, is_dir: bool, expected: bool) -> None:
        assert compile_pattern(pattern).matches(path, is_dir=is_dir) is expected

    @pytest.mark.parametrize(
        "pattern",
        ["!x", "[abc", "a\\b", "", "./x", "a//b", "[a/b]", "[].py", "[z-a].py", "[!].py"],
    )
    def test_invalid_patterns(self, pattern: str) -> None:
        with pytest.raises(PatternError):
            compile_pattern(pattern)

    def test_malformed_class_is_a_config_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="exclude_patterns"):
            _config(tmp_path, exclude_patterns=("[z-a].py",))

    def test_metacharacters_are_literal(self) -> None:
        assert compile_pattern("a.py").matches("aXpy", is_dir=False) is False
        assert compile_pattern("a+b.py").matches("a+b.py", is_dir=False) is True


# --------------------------------------------------------------------------------------
# positive discovery on the committed multi-package fixture
# --------------------------------------------------------------------------------------


class TestDiscoveryPositive:
    def test_fixture_exists(self) -> None:
        assert WORKSPACE_FIXTURE.is_dir()

    def test_multi_package_fixture_discovered(self) -> None:
        result = discover(_config(WORKSPACE_FIXTURE, "fx"))
        assert _paths(result) == list(EXPECTED_FIXTURE_FILES)
        assert not result.truncated
        assert result.summary.source_files == len(EXPECTED_FIXTURE_FILES)
        for f in result.files:
            on_disk = WORKSPACE_FIXTURE / f.relative_path
            assert f.sha256 == _sha256(on_disk)
            assert f.size_bytes == on_disk.stat().st_size
            assert f.root_id == "fx"
            assert f.workspace_path == f"fx:{f.relative_path}"
            assert f.kind is (SourceKind.PYI if f.relative_path.endswith(".pyi") else SourceKind.PY)
        inits = {f.relative_path for f in result.files if f.is_package_init}
        assert "pkg_a/__init__.py" in inits and "pkg_a/core.py" not in inits

    def test_non_source_files_are_counted_not_diagnosed(self) -> None:
        result = discover(_config(WORKSPACE_FIXTURE, "fx"))
        non_source = [
            p
            for p in WORKSPACE_FIXTURE.rglob("*")
            if p.is_file() and p.suffix not in (".py", ".pyi")
        ]
        assert len(non_source) >= 2  # README.md and data/notes.txt
        assert result.summary.ignored_files == len(non_source)
        assert result.diagnostics == ()  # the benign fixture triggers no diagnostics

    def test_packages_identified(self) -> None:
        result = discover(_config(WORKSPACE_FIXTURE, "fx"))
        by_path = {p.relative_path: p for p in result.packages}
        assert list(by_path) == sorted(by_path)
        assert set(by_path) == {
            "nspkg",
            "nspkg/inner",
            "pkg_a",
            "pkg_a/sub",
            "pkg_b",
            "scripts",
            "vendor_excluded",
            "vendor_excluded/lib",
        }
        assert by_path["pkg_a"].kind is PackageKind.REGULAR
        assert by_path["pkg_a/sub"].kind is PackageKind.REGULAR
        assert by_path["nspkg"].kind is PackageKind.NAMESPACE_CANDIDATE
        assert by_path["nspkg/inner"].kind is PackageKind.REGULAR
        assert by_path["scripts"].kind is PackageKind.NAMESPACE_CANDIDATE
        assert all(p.importable_name for p in result.packages)
        assert "data" not in by_path  # no sources -> not a package candidate
        assert "." not in by_path  # root without __init__.py is not asserted as a package

    def test_exclude_pattern_prunes_directory_with_single_diagnostic(self) -> None:
        config = _config(
            WORKSPACE_FIXTURE, "fx", exclude_patterns=(*DEFAULT_EXCLUDE_PATTERNS, "vendor_excluded")
        )
        result = discover(config)
        assert not any(p.startswith("vendor_excluded") for p in _paths(result))
        assert not any(p.relative_path.startswith("vendor_excluded") for p in result.packages)
        excluded = _diags(result, DiagnosticCode.EXCLUDED_BY_PATTERN)
        assert [(d.path, d.severity) for d in excluded] == [("vendor_excluded", Severity.INFO)]
        assert "'vendor_excluded'" in excluded[0].message
        assert excluded[0].workspace_path == "fx:vendor_excluded"

    def test_exclude_pattern_on_file(self) -> None:
        config = _config(
            WORKSPACE_FIXTURE, "fx", exclude_patterns=(*DEFAULT_EXCLUDE_PATTERNS, "*.pyi")
        )
        result = discover(config)
        assert "pkg_b/api.pyi" not in _paths(result)
        assert [d.path for d in _diags(result, DiagnosticCode.EXCLUDED_BY_PATTERN)] == [
            "pkg_b/api.pyi"
        ]

    def test_default_excludes_prune_tool_directories(self, tmp_path: Path) -> None:
        _write(tmp_path / "keep.py")
        for name in (".git", "__pycache__", ".venv", "node_modules", "foo.egg-info"):
            _write(tmp_path / name / "hidden.py")
        result = discover(_config(tmp_path))
        assert _paths(result) == ["keep.py"]
        pruned = sorted(d.path for d in _diags(result, DiagnosticCode.EXCLUDED_BY_PATTERN))
        assert pruned == [".git", ".venv", "__pycache__", "foo.egg-info", "node_modules"]

    def test_build_and_dist_are_not_excluded_by_default(self, tmp_path: Path) -> None:
        _write(tmp_path / "build" / "__init__.py")
        _write(tmp_path / "dist" / "x.py")
        assert _paths(discover(_config(tmp_path))) == ["build/__init__.py", "dist/x.py"]

    def test_to_dict_is_json_serializable_and_stable(self) -> None:
        result = discover(_config(WORKSPACE_FIXTURE, "fx"))
        encoded = json.dumps(result.to_dict(), sort_keys=True)
        assert json.dumps(discover(_config(WORKSPACE_FIXTURE, "fx")).to_dict(), sort_keys=True) == (
            encoded
        )
        decoded = json.loads(encoded)
        assert decoded["files"][0]["workspace_path"] == "fx:nspkg/inner/__init__.py"
        assert decoded["summary"]["truncated"] is False


# --------------------------------------------------------------------------------------
# determinism (SPEC 3.6)
# --------------------------------------------------------------------------------------


class TestDeterminism:
    def test_two_runs_are_equal(self) -> None:
        config = _config(WORKSPACE_FIXTURE, "fx")
        first, second = discover(config), discover(config)
        assert first == second
        assert first.content_fingerprint() == second.content_fingerprint()
        assert [f.sha256 for f in first.files] == [f.sha256 for f in second.files]

    def test_output_order_independent_of_creation_order(self, tmp_path: Path) -> None:
        names = ["z.py", "m/b.py", "m/a.py", "a.py", "m.py", "a-b.py", "a_b.py"]
        for name in reversed(names):
            _write(tmp_path / name)
        result = discover(_config(tmp_path))
        assert _paths(result) == sorted(names)

    def test_fingerprint_independent_of_absolute_location(self, tmp_path: Path) -> None:
        copy = tmp_path / "copy"
        shutil.copytree(WORKSPACE_FIXTURE, copy)
        original = discover(_config(WORKSPACE_FIXTURE, "fx"))
        copied = discover(_config(copy, "fx"))
        assert original.content_fingerprint() == copied.content_fingerprint()
        assert original.files == copied.files
        assert original.packages == copied.packages

    def test_fingerprint_changes_with_content(self, tmp_path: Path) -> None:
        target = _write(tmp_path / "m.py", "a = 1\n")
        before = discover(_config(tmp_path)).content_fingerprint()
        target.write_text("a = 2\n", encoding="utf-8")
        assert discover(_config(tmp_path)).content_fingerprint() != before

    def test_hash_is_raw_bytes_sha256(self, tmp_path: Path) -> None:
        target = tmp_path / "crlf.py"
        target.write_bytes(b"x = 1\r\n")
        (f,) = discover(_config(tmp_path)).files
        assert f.sha256 == hashlib.sha256(b"x = 1\r\n").hexdigest()
        assert f.size_bytes == 7


# --------------------------------------------------------------------------------------
# symlinks (D-0020, SPEC 9 "symlink escape")
# --------------------------------------------------------------------------------------


def _linked_tree(base: Path) -> tuple[Path, Path]:
    """A root with in-root content and an *outside* directory with secrets."""
    root = base / "root"
    outside = base / "outside"
    _write(root / "pkg" / "__init__.py")
    _write(root / "pkg" / "real.py", "REAL = 1\n")
    _write(outside / "secret.py", "TOKEN = 'outside-secret'\n")
    _write(outside / "deep" / "more.py", "MORE = 1\n")
    return root, outside


@pytest.fixture
def linked_tree(tmp_path: Path) -> tuple[Path, Path]:
    return _linked_tree(tmp_path)


class TestSymlinks:
    @pytest.mark.parametrize("policy", list(SymlinkPolicy))
    def test_symlink_to_outside_file_rejected(
        self, linked_tree: tuple[Path, Path], policy: SymlinkPolicy
    ) -> None:
        root, outside = linked_tree
        (root / "pkg" / "leak.py").symlink_to(outside / "secret.py")
        result = discover(_config(root, safety=_safety(symlink_policy=policy)))
        assert "pkg/leak.py" not in _paths(result)
        assert _sha256(outside / "secret.py") not in {f.sha256 for f in result.files}
        escapes = _diags(result, DiagnosticCode.SYMLINK_ESCAPES_ROOT)
        assert [(d.path, d.severity) for d in escapes] == [("pkg/leak.py", Severity.WARNING)]
        assert "outside-secret" not in escapes[0].message

    @pytest.mark.parametrize("policy", list(SymlinkPolicy))
    def test_symlink_to_outside_directory_rejected(
        self, linked_tree: tuple[Path, Path], policy: SymlinkPolicy
    ) -> None:
        root, outside = linked_tree
        (root / "escape").symlink_to(outside, target_is_directory=True)
        # Also a relative '..'-style link, which is the classic escape vector.
        os.symlink(os.path.join("..", "..", "outside", "deep"), root / "pkg" / "rel_escape")
        result = discover(_config(root, safety=_safety(symlink_policy=policy)))
        assert _paths(result) == ["pkg/__init__.py", "pkg/real.py"]
        assert sorted(d.path for d in _diags(result, DiagnosticCode.SYMLINK_ESCAPES_ROOT)) == [
            "escape",
            "pkg/rel_escape",
        ]
        assert result.summary.directories_visited == 2  # root and pkg only

    def test_in_root_symlink_not_followed_by_default(self, linked_tree: tuple[Path, Path]) -> None:
        root, _ = linked_tree
        (root / "alias.py").symlink_to(root / "pkg" / "real.py")
        (root / "pkg_alias").symlink_to(root / "pkg", target_is_directory=True)
        result = discover(_config(root))
        assert _paths(result) == ["pkg/__init__.py", "pkg/real.py"]
        assert sorted(d.path for d in _diags(result, DiagnosticCode.SYMLINK_NOT_FOLLOWED)) == [
            "alias.py",
            "pkg_alias",
        ]
        assert all(d.severity is Severity.INFO for d in result.diagnostics)

    def test_in_root_symlinks_followed_under_within_root_policy(
        self, linked_tree: tuple[Path, Path]
    ) -> None:
        root, _ = linked_tree
        (root / "alias.py").symlink_to(root / "pkg" / "real.py")
        (root / "pkg_alias").symlink_to(root / "pkg", target_is_directory=True)
        # Cycle: pkg/up -> root.
        (root / "pkg" / "up").symlink_to(root, target_is_directory=True)
        result = discover(_config(root, safety=_safety(symlink_policy=SymlinkPolicy.WITHIN_ROOT)))
        assert _paths(result) == [
            "alias.py",
            "pkg/__init__.py",
            "pkg/real.py",
        ]
        by_path = {f.relative_path: f for f in result.files}
        assert by_path["alias.py"].sha256 == by_path["pkg/real.py"].sha256
        # Directory links are never traversed (D-0025): the real directory keeps its path.
        (cycle,) = _diags(result, DiagnosticCode.SYMLINK_CYCLE)
        assert cycle.path == "pkg/up" and cycle.severity is Severity.INFO
        (alias,) = _diags(result, DiagnosticCode.SYMLINK_ALIAS)
        assert alias.path == "pkg_alias" and alias.severity is Severity.INFO
        assert "'pkg'" in alias.message
        assert [p.relative_path for p in result.packages] == ["pkg"]
        assert result.summary.directories_visited == 2
        assert not result.truncated

    @pytest.mark.parametrize("policy", list(SymlinkPolicy))
    def test_directory_alias_link_does_not_change_canonical_paths(
        self, tmp_path: Path, policy: SymlinkPolicy
    ) -> None:
        """R1: an alias link sorting *before* the real directory must not rename anything."""
        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "m.py", "M = 1\n")
        config = _config(tmp_path, "r", safety=_safety(symlink_policy=policy))
        baseline = discover(config)
        assert [f.workspace_path for f in baseline.files] == [
            "r:src/pkg/__init__.py",
            "r:src/pkg/m.py",
        ]
        assert baseline.diagnostics == ()

        link = tmp_path / "pkg"
        link.symlink_to(tmp_path / "src" / "pkg", target_is_directory=True)
        linked = discover(config)
        assert linked.files == baseline.files
        assert linked.packages == baseline.packages
        assert linked.content_fingerprint() == baseline.content_fingerprint()
        expected_code = (
            DiagnosticCode.SYMLINK_ALIAS
            if policy is SymlinkPolicy.WITHIN_ROOT
            else DiagnosticCode.SYMLINK_NOT_FOLLOWED
        )
        assert [(d.code, d.path) for d in linked.diagnostics] == [(expected_code, "pkg")]
        if policy is SymlinkPolicy.WITHIN_ROOT:
            assert "'src/pkg'" in linked.diagnostics[0].message
        assert linked.summary.directories_visited == baseline.summary.directories_visited

        link.unlink()
        assert discover(config) == baseline

    @pytest.mark.parametrize("policy", list(SymlinkPolicy))
    def test_excluded_symlink_is_not_resolved(self, tmp_path: Path, policy: SymlinkPolicy) -> None:
        """R2: configured exclusions apply to a link's own path before it is resolved."""
        outside = tmp_path / "virtualenvs" / "foo"
        _write(outside / "lib" / "site.py", "SITE = 1\n")
        root = tmp_path / "root"
        _write(root / "app.py")
        (root / ".venv").symlink_to(outside, target_is_directory=True)
        (root / "build").symlink_to(outside, target_is_directory=True)  # dir-only pattern
        config = _config(
            root,
            exclude_patterns=(*DEFAULT_EXCLUDE_PATTERNS, "build/"),
            safety=_safety(symlink_policy=policy),
        )
        resolved: list[str] = []
        real_realpath = os.path.realpath

        def recording_realpath(path: Any, *, strict: Any = False) -> Any:
            resolved.append(os.fspath(path))
            return real_realpath(path, strict=strict)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(os.path, "realpath", recording_realpath)
            result = discover(config)
        assert _paths(result) == ["app.py"]
        assert [(d.code, d.path) for d in result.diagnostics] == [
            (DiagnosticCode.EXCLUDED_BY_PATTERN, ".venv"),
            (DiagnosticCode.EXCLUDED_BY_PATTERN, "build"),
        ]
        assert "not resolved" in result.diagnostics[0].message
        assert not any(p.endswith((".venv", "build")) for p in resolved)

    @pytest.mark.parametrize("policy", list(SymlinkPolicy))
    def test_dangling_link_to_outside_is_reported_as_escape(
        self, tmp_path: Path, policy: SymlinkPolicy
    ) -> None:
        """R8: the within-root check precedes any existence check of the target."""
        root = tmp_path / "root"
        _write(root / "ok.py")
        (root / "gone.py").symlink_to(tmp_path / "elsewhere" / "nothing.py")
        (root / "loop").symlink_to(Path("loop"))  # self-referential: ELOOP
        stat_calls: list[str] = []
        real_stat = os.stat

        def recording_stat(path: Any, *args: Any, **kwargs: Any) -> Any:
            if isinstance(path, str | bytes | os.PathLike):
                stat_calls.append(os.fspath(path) if isinstance(path, str) else "")
            return real_stat(path, *args, **kwargs)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(os, "stat", recording_stat)
            result = discover(_config(root, safety=_safety(symlink_policy=policy)))
        assert _paths(result) == ["ok.py"]
        assert [(d.code, d.path) for d in result.diagnostics] == [
            (DiagnosticCode.SYMLINK_ESCAPES_ROOT, "gone.py"),
            (DiagnosticCode.SYMLINK_TARGET_MISSING, "loop"),
        ]
        assert not any("elsewhere" in p for p in stat_calls)

    def test_file_link_into_excluded_directory_is_not_followed(self, tmp_path: Path) -> None:
        _write(tmp_path / ".venv" / "lib" / "site.py", "SITE = 1\n")
        _write(tmp_path / "ok.py")
        (tmp_path / "alias.py").symlink_to(tmp_path / ".venv" / "lib" / "site.py")
        result = discover(
            _config(tmp_path, safety=_safety(symlink_policy=SymlinkPolicy.WITHIN_ROOT))
        )
        assert _paths(result) == ["ok.py"]
        assert [(d.code, d.path) for d in result.diagnostics] == [
            (DiagnosticCode.EXCLUDED_BY_PATTERN, ".venv"),
            (DiagnosticCode.EXCLUDED_BY_PATTERN, "alias.py"),
        ]
        assert "'.venv/lib/site.py'" in result.diagnostics[1].message

    def test_symlink_alias_code_is_stable(self) -> None:
        assert DiagnosticCode.SYMLINK_ALIAS.value == "symlink_alias"

    @pytest.mark.parametrize("policy", list(SymlinkPolicy))
    def test_dangling_symlink_reported(self, tmp_path: Path, policy: SymlinkPolicy) -> None:
        _write(tmp_path / "ok.py")
        (tmp_path / "dangling.py").symlink_to(tmp_path / "missing.py")
        result = discover(_config(tmp_path, safety=_safety(symlink_policy=policy)))
        assert _paths(result) == ["ok.py"]
        assert [d.path for d in _diags(result, DiagnosticCode.SYMLINK_TARGET_MISSING)] == [
            "dangling.py"
        ]


# --------------------------------------------------------------------------------------
# size cap and traversal bounds (D-0021, SPEC 9 "huge files")
# --------------------------------------------------------------------------------------


class TestSizeAndLimits:
    def test_oversized_file_skipped_with_diagnostic(self, tmp_path: Path) -> None:
        cap = 100
        (tmp_path / "exact.py").write_bytes(b"#" * cap)
        (tmp_path / "big.py").write_bytes(b"#" * (cap + 1))
        result = discover(_config(tmp_path, safety=_safety(max_file_size_bytes=cap)))
        assert _paths(result) == ["exact.py"]
        (diag,) = _diags(result, DiagnosticCode.FILE_TOO_LARGE)
        assert diag.path == "big.py" and diag.severity is Severity.WARNING
        assert f"{cap + 1}" in diag.message and f"max_file_size_bytes={cap}" in diag.message
        assert not result.truncated

    def test_huge_file_default_cap(self, tmp_path: Path) -> None:
        big = tmp_path / "huge.py"
        with big.open("wb") as fh:
            fh.truncate(DEFAULT_MAX_FILE_SIZE_BYTES + 1)  # sparse; no real I/O cost
        _write(tmp_path / "small.py")
        result = discover(_config(tmp_path))
        assert _paths(result) == ["small.py"]
        assert [d.path for d in _diags(result, DiagnosticCode.FILE_TOO_LARGE)] == ["huge.py"]

    def test_cap_enforced_while_reading_even_if_stat_lies(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "grow.py"
        target.write_bytes(b"x" * 50)
        real_fstat = os.fstat

        def lying_fstat(fd: int) -> os.stat_result:
            st = real_fstat(fd)
            return os.stat_result((*st[:6], 1, *st[7:]))  # claims st_size == 1

        monkeypatch.setattr(os, "fstat", lying_fstat)  # walk.py uses the same os module
        with pytest.raises(walk_module._TooLargeError):
            walk_module._hash_regular_file(str(target), cap=10)

    def test_max_files_truncates_deterministically(self, tmp_path: Path) -> None:
        for name in ("e.py", "d.py", "c.py", "b.py", "a.py"):
            _write(tmp_path / name)
        result = discover(_config(tmp_path, safety=_safety(limits={"max_files": 2})))
        assert _paths(result) == ["a.py", "b.py"]
        assert result.truncated and result.summary.truncated
        (diag,) = _diags(result, DiagnosticCode.LIMIT_REACHED)
        assert diag.severity is Severity.ERROR and diag.path == "c.py"
        assert "max_files=2" in diag.message
        assert discover(_config(tmp_path, safety=_safety(limits={"max_files": 2}))) == result

    def test_max_entries_truncates(self, tmp_path: Path) -> None:
        for i in range(10):
            _write(tmp_path / f"f{i}.py")
        result = discover(_config(tmp_path, safety=_safety(limits={"max_entries": 3})))
        assert len(result.files) == 3 and result.truncated
        assert "max_entries=3" in _diags(result, DiagnosticCode.LIMIT_REACHED)[0].message

    def test_limit_reached_marks_later_roots_unvisited(self, tmp_path: Path) -> None:
        a, b = tmp_path / "a", tmp_path / "b"
        _write(a / "x.py")
        _write(a / "y.py")
        _write(b / "z.py")
        config = WorkspaceConfig(
            roots=(WorkspaceRoot("a", a), WorkspaceRoot("b", b)),
            safety=_safety(limits={"max_files": 1}),
        )
        result = discover(config)
        assert [f.workspace_path for f in result.files] == ["a:x.py"]
        assert [(d.root_id, d.path) for d in _diags(result, DiagnosticCode.LIMIT_REACHED)] == [
            ("a", "y.py"),
            ("b", "."),
        ]

    def test_max_depth_stops_descent(self, tmp_path: Path) -> None:
        _write(tmp_path / "d1" / "d2" / "d3" / "d4" / "deep.py")
        _write(tmp_path / "d1" / "d2" / "shallow.py")
        result = discover(_config(tmp_path, safety=_safety(limits={"max_depth": 2})))
        assert _paths(result) == ["d1/d2/shallow.py"]
        (diag,) = _diags(result, DiagnosticCode.MAX_DEPTH_EXCEEDED)
        assert diag.path == "d1/d2/d3" and "max_depth=2" in diag.message
        assert not result.truncated

    def test_pathological_nesting_does_not_recurse(self, tmp_path: Path) -> None:
        # 150 levels (300 chars) stays under macOS PATH_MAX but exceeds a naive recursion
        # budget if the walker were recursive with a small limit; bounds are explicit.
        leaf = tmp_path.joinpath(*(["n"] * 150))
        _write(leaf / "leaf.py")
        result = discover(_config(tmp_path, safety=_safety(limits={"max_depth": 1000})))
        assert len(result.files) == 1 and result.files[0].relative_path.endswith("/leaf.py")

    @pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX only")
    def test_fifo_is_not_opened(self, tmp_path: Path) -> None:
        os.mkfifo(tmp_path / "pipe.py")  # opening this for reading would block forever
        _write(tmp_path / "ok.py")
        result = discover(_config(tmp_path))
        assert _paths(result) == ["ok.py"]
        (diag,) = _diags(result, DiagnosticCode.NOT_REGULAR_FILE)
        assert diag.path == "pipe.py" and diag.severity is Severity.WARNING

    @pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX only")
    def test_non_included_special_file_is_only_counted(self, tmp_path: Path) -> None:
        os.mkfifo(tmp_path / "pipe.txt")  # R9: never a source candidate, so no warning
        _write(tmp_path / "ok.py")
        result = discover(_config(tmp_path))
        assert _paths(result) == ["ok.py"]
        assert result.diagnostics == ()
        assert result.summary.ignored_files == 1

    @pytest.mark.skipif(
        os.name != "posix" or (hasattr(os, "geteuid") and os.geteuid() == 0),
        reason="needs POSIX permissions and a non-root user",
    )
    def test_unreadable_directory_diagnosed(self, tmp_path: Path) -> None:
        locked = tmp_path / "locked"
        _write(locked / "x.py")
        _write(tmp_path / "ok.py")
        locked.chmod(0)
        try:
            result = discover(_config(tmp_path))
        finally:
            locked.chmod(0o755)
        assert _paths(result) == ["ok.py"]
        (diag,) = _diags(result, DiagnosticCode.UNREADABLE)
        assert diag.path == "locked"

    @pytest.mark.skipif(
        os.name != "posix" or (hasattr(os, "geteuid") and os.geteuid() == 0),
        reason="needs POSIX permissions and a non-root user",
    )
    def test_unreadable_file_diagnosed(self, tmp_path: Path) -> None:
        locked = _write(tmp_path / "locked.py", "SECRET = 1\n")
        _write(tmp_path / "ok.py")
        locked.chmod(0)
        try:
            result = discover(_config(tmp_path))
        finally:
            locked.chmod(0o644)
        assert _paths(result) == ["ok.py"]
        (diag,) = _diags(result, DiagnosticCode.UNREADABLE)
        assert (diag.path, diag.severity) == ("locked.py", Severity.WARNING)
        assert "SECRET" not in diag.message

    def test_invalid_name_helper(self) -> None:
        assert walk_module._valid_name("plain.py")
        assert walk_module._valid_name("ünïcode.py")
        assert not walk_module._valid_name("\udcff.py")  # surrogate-escaped undecodable byte
        assert not walk_module._valid_name("nul\x00.py")

    def test_undecodable_name_diagnosed(self, tmp_path: Path) -> None:
        raw = os.path.join(os.fsencode(tmp_path), b"\xff\xfe.py")
        try:
            fd = os.open(raw, os.O_WRONLY | os.O_CREAT, 0o644)
        except OSError as exc:  # e.g. APFS rejects non-UTF-8 names
            pytest.skip(f"filesystem rejects non-UTF-8 file names ({exc.strerror})")
        os.close(fd)
        _write(tmp_path / "ok.py")
        result = discover(_config(tmp_path))
        assert _paths(result) == ["ok.py"]
        (diag,) = _diags(result, DiagnosticCode.INVALID_FILENAME)
        assert diag.path.endswith(".py")


# --------------------------------------------------------------------------------------
# open-file / open-directory hardening (D-0026)
# --------------------------------------------------------------------------------------


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="O_NOFOLLOW not available")
class TestNoFollow:
    def test_hash_refuses_symlink_by_path(self, tmp_path: Path) -> None:
        target = _write(tmp_path / "real.py")
        link = tmp_path / "link.py"
        link.symlink_to(target)
        with pytest.raises(OSError) as info:
            walk_module._hash_regular_file(str(link), cap=1024)
        assert info.value.errno in (errno.ELOOP, errno.EMLINK)
        assert walk_module._hash_regular_file(str(target), cap=1024) == (6, _sha256(target))

    @pytest.mark.skipif(not walk_module._FD_TRAVERSAL, reason="needs dir_fd support")
    def test_hash_refuses_symlink_relative_to_dir_fd(self, tmp_path: Path) -> None:
        target = _write(tmp_path / "real.py")
        (tmp_path / "link.py").symlink_to(target)
        fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            with pytest.raises(OSError) as info:
                walk_module._hash_regular_file("link.py", cap=1024, dir_fd=fd)
            assert info.value.errno in (errno.ELOOP, errno.EMLINK)
            assert walk_module._hash_regular_file("real.py", cap=1024, dir_fd=fd)[1] == _sha256(
                target
            )
        finally:
            os.close(fd)

    @pytest.mark.skipif(not walk_module._FD_TRAVERSAL, reason="needs dir_fd support")
    def test_directory_swapped_for_link_after_classification_is_not_followed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R3: a directory replaced by a symlink between lstat and open is refused."""
        outside = tmp_path / "outside"
        _write(outside / "leak.py", "LEAK = 1\n")
        root = tmp_path / "root"
        _write(root / "a.py")
        swap = root / "swap"
        _write(swap / "inner.py")
        real_open_dir = walk_module._RootWalker._open_dir

        def racing_open_dir(abs_path: str, name: str, parent_fd: int | None) -> int | None:
            if name == "swap":
                shutil.rmtree(swap)
                swap.symlink_to(outside, target_is_directory=True)
            return real_open_dir(abs_path, name, parent_fd)

        monkeypatch.setattr(walk_module._RootWalker, "_open_dir", staticmethod(racing_open_dir))
        result = discover(_config(root, safety=_safety(symlink_policy=SymlinkPolicy.WITHIN_ROOT)))
        assert _paths(result) == ["a.py"]
        assert _sha256(outside / "leak.py") not in {f.sha256 for f in result.files}
        (diag,) = result.diagnostics
        assert (diag.code, diag.path) == (DiagnosticCode.UNREADABLE, "swap")

    @pytest.mark.skipif(not os.path.isdir("/dev/fd"), reason="needs /dev/fd to count descriptors")
    def test_no_descriptor_leak_even_when_truncated(self, tmp_path: Path) -> None:
        for name in ("a/b/c/x.py", "a/b/y.py", "a/z.py", "d/e/w.py"):
            _write(tmp_path / name)
        before = set(os.listdir("/dev/fd"))
        discover(_config(tmp_path))
        discover(_config(tmp_path, safety=_safety(limits={"max_files": 2})))
        assert set(os.listdir("/dev/fd")) == before

    def test_path_fallback_matches_descriptor_traversal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, _ = _linked_tree(tmp_path)
        (root / "alias.py").symlink_to(root / "pkg" / "real.py")
        (root / "pkg" / "up").symlink_to(root, target_is_directory=True)
        config = _config(root, safety=_safety(symlink_policy=SymlinkPolicy.WITHIN_ROOT))
        with_fds = discover(config)
        monkeypatch.setattr(walk_module, "_FD_TRAVERSAL", False)
        assert discover(config) == with_fds
        assert discover(_config(WORKSPACE_FIXTURE, "fx")).summary.source_files == len(
            EXPECTED_FIXTURE_FILES
        )


# --------------------------------------------------------------------------------------
# diagnostics (D-0022)
# --------------------------------------------------------------------------------------


class TestDiagnostics:
    def test_root_unavailable_after_config_built(self, tmp_path: Path) -> None:
        gone = tmp_path / "gone"
        _write(gone / "x.py")
        _write(tmp_path / "stay" / "y.py")
        config = WorkspaceConfig(
            roots=(WorkspaceRoot("gone", gone), WorkspaceRoot("stay", tmp_path / "stay"))
        )
        shutil.rmtree(gone)
        result = discover(config)
        assert [f.workspace_path for f in result.files] == ["stay:y.py"]
        (diag,) = _diags(result, DiagnosticCode.ROOT_UNAVAILABLE)
        assert (diag.root_id, diag.path, diag.severity) == ("gone", ".", Severity.ERROR)

    def test_messages_never_contain_file_content(self, tmp_path: Path) -> None:
        secret = "SECRET_TOKEN_abc123"
        (tmp_path / "big.py").write_text(secret * 100, encoding="utf-8")
        (tmp_path / "link.py").symlink_to(tmp_path / "big.py")
        result = discover(_config(tmp_path, safety=_safety(max_file_size_bytes=10)))
        assert result.diagnostics  # both entries produce diagnostics
        serialized = json.dumps(result.to_dict())
        assert "SECRET_TOKEN" not in serialized

    def test_diagnostics_sorted_and_counted(self, tmp_path: Path) -> None:
        _write(tmp_path / "b" / ".git" / "x.py")
        _write(tmp_path / "a" / "__pycache__" / "y.py")
        (tmp_path / "a" / "z.py").symlink_to(tmp_path / "missing")
        result = discover(_config(tmp_path))
        assert [d.path for d in result.diagnostics] == ["a/__pycache__", "a/z.py", "b/.git"]
        assert result.summary.diagnostics == 3
        assert all(d.root_id == "ws" for d in result.diagnostics)

    def test_diagnostic_codes_are_stable_strings(self) -> None:
        assert DiagnosticCode.SYMLINK_ESCAPES_ROOT.value == "symlink_escapes_root"
        assert str(DiagnosticCode.FILE_TOO_LARGE) == "file_too_large"
        assert json.dumps(DiagnosticCode.LIMIT_REACHED) == '"limit_reached"'


# --------------------------------------------------------------------------------------
# package identification: unknown / ambiguous cases (D-0022)
# --------------------------------------------------------------------------------------


class TestPackages:
    def test_directory_without_init_is_candidate_not_package(self, tmp_path: Path) -> None:
        _write(tmp_path / "maybe" / "mod.py")
        (pkg,) = discover(_config(tmp_path)).packages
        assert pkg.relative_path == "maybe"
        assert pkg.kind is PackageKind.NAMESPACE_CANDIDATE
        assert not pkg.has_init_py and not pkg.has_init_pyi
        assert pkg.importable_name

    def test_parent_of_package_is_candidate(self, tmp_path: Path) -> None:
        _write(tmp_path / "src" / "pkg" / "__init__.py")
        kinds = {p.relative_path: p.kind for p in discover(_config(tmp_path)).packages}
        assert kinds == {
            "src": PackageKind.NAMESPACE_CANDIDATE,
            "src/pkg": PackageKind.REGULAR,
        }

    def test_non_identifier_and_keyword_names_flagged(self, tmp_path: Path) -> None:
        _write(tmp_path / "my-pkg" / "__init__.py")
        _write(tmp_path / "class" / "x.py")
        _write(tmp_path / "ok_pkg" / "x.py")
        flags = {p.relative_path: p.importable_name for p in discover(_config(tmp_path)).packages}
        assert flags == {"my-pkg": False, "class": False, "ok_pkg": True}

    def test_stub_only_init_is_not_asserted_regular(self, tmp_path: Path) -> None:
        _write(tmp_path / "stubs" / "__init__.pyi")
        (pkg,) = discover(_config(tmp_path)).packages
        assert pkg.kind is PackageKind.NAMESPACE_CANDIDATE
        assert pkg.has_init_pyi and not pkg.has_init_py

    def test_root_with_own_init_reported_as_dot(self, tmp_path: Path) -> None:
        _write(tmp_path / "__init__.py")
        _write(tmp_path / "m.py")
        (pkg,) = discover(_config(tmp_path, "r")).packages
        assert (pkg.relative_path, pkg.kind, pkg.workspace_path) == (
            ".",
            PackageKind.REGULAR,
            "r:.",
        )

    def test_excluded_directory_is_not_a_package(self, tmp_path: Path) -> None:
        _write(tmp_path / "__pycache__" / "__init__.py")
        assert discover(_config(tmp_path)).packages == ()


# --------------------------------------------------------------------------------------
# non-execution boundary (D-0015, D-0023, SPEC 3.1 and 9)
# --------------------------------------------------------------------------------------


SENTINEL_NAME = "EXECUTED.sentinel"

HOSTILE_SETUP_PY = f"""\
import pathlib
pathlib.Path(__file__).with_name({SENTINEL_NAME!r}).write_text("setup.py ran")
from setuptools import setup
setup(name="hostile")
"""

HOSTILE_MODULE = f"""\
import pathlib
pathlib.Path(__file__).with_name({SENTINEL_NAME!r}).write_text("module imported")
raise SystemExit("side effect")
"""

HOSTILE_PYPROJECT = """\
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"
"""


def build_hostile_tree(base: Path) -> Path:
    """A repository whose setup.py / modules write a sentinel file when executed."""
    root = base / "hostile"
    _write(root / "setup.py", HOSTILE_SETUP_PY)
    _write(root / "pyproject.toml", HOSTILE_PYPROJECT)
    _write(root / "side_effect.py", HOSTILE_MODULE)
    _write(root / "pkg" / "__init__.py", HOSTILE_MODULE)
    _write(root / "pkg" / "conftest.py", HOSTILE_MODULE)
    _write(root / "pkg" / "__main__.py", HOSTILE_MODULE)
    _write(root / "pkg" / "evil.pth", "import side_effect\n")
    _write(root / "pathological.py", "(" * 100_000 + ")" * 100_000 + "\n")
    _write(root / "not_utf8.py", "")
    (root / "not_utf8.py").write_bytes(b"\xff\xfe\x00 invalid utf-8 \x80\n")
    return root


@contextlib.contextmanager
def tripwires() -> Iterator[list[str]]:
    """Patch every Python-level execution entry point to record and fail.

    Used as a ``with`` block around the ``discover`` call only, so the builtins are
    restored before assertions run and before pytest formats any failure (otherwise a
    failing assertion would trip ``compile`` inside pytest itself and abort the session).
    """
    fired: list[str] = []

    def trap(name: str) -> Callable[..., Any]:
        def _trap(*args: Any, **kwargs: Any) -> Any:
            fired.append(name)
            raise AssertionError(f"forbidden execution primitive called: {name}")

        return _trap

    real_import = builtins.__import__

    def guarded_import(
        name: str,
        globals_: Any = None,
        locals_: Any = None,
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        if level != 0 or name not in sys.modules:
            fired.append(f"__import__:{name}")
            raise AssertionError(f"import of not-yet-loaded module during discovery: {name}")
        return real_import(name, globals_, locals_, fromlist, level)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(builtins, "exec", trap("exec"))
        mp.setattr(builtins, "eval", trap("eval"))
        mp.setattr(builtins, "compile", trap("compile"))
        mp.setattr(builtins, "__import__", guarded_import)
        mp.setattr(subprocess, "Popen", trap("subprocess.Popen"))
        mp.setattr(subprocess, "run", trap("subprocess.run"))
        mp.setattr(os, "system", trap("os.system"))
        for name in ("posix_spawn", "posix_spawnp", "spawnv", "spawnve", "execv", "execve", "fork"):
            if hasattr(os, name):
                mp.setattr(os, name, trap(f"os.{name}"))
        mp.setattr(importlib, "import_module", trap("importlib.import_module"))
        mp.setattr(runpy, "run_path", trap("runpy.run_path"))
        mp.setattr(runpy, "run_module", trap("runpy.run_module"))
        yield fired


class TestNonExecution:
    def test_tripwires_are_restored_after_the_block(self) -> None:
        real_compile = builtins.compile
        with tripwires() as fired:
            assert builtins.compile is not real_compile
            with pytest.raises(AssertionError, match="forbidden execution primitive"):
                compile("1", "<x>", "eval")
        assert builtins.compile is real_compile
        assert fired == ["compile"]

    def test_hostile_tree_discovered_without_side_effects(self, tmp_path: Path) -> None:
        root = build_hostile_tree(tmp_path)
        modules_before = set(sys.modules)
        with tripwires() as fired:
            result = discover(_config(root, "hostile"))
        assert fired == []
        assert _paths(result) == [
            "not_utf8.py",
            "pathological.py",
            "pkg/__init__.py",
            "pkg/__main__.py",
            "pkg/conftest.py",
            "setup.py",
            "side_effect.py",
        ]
        assert result.diagnostics == ()
        assert not list(root.rglob(SENTINEL_NAME)), "target code was executed"
        assert not list(root.rglob("__pycache__")), "target code was compiled"
        assert not list(root.rglob("*.pyc"))
        assert set(sys.modules) == modules_before
        assert {"side_effect", "setup", "pkg", "hostile"}.isdisjoint(sys.modules)

    def test_hostile_tree_with_symlinks_and_within_root_policy(self, tmp_path: Path) -> None:
        root = build_hostile_tree(tmp_path)
        (root / "loop").symlink_to(root, target_is_directory=True)
        (root / "out.py").symlink_to(TESTS_DIR / "fixtures" / "t001_outside_module.py")
        with tripwires() as fired:
            result = discover(
                _config(root, "hostile", safety=_safety(symlink_policy=SymlinkPolicy.WITHIN_ROOT))
            )
        assert fired == []
        assert "out.py" not in _paths(result)
        assert {d.code for d in result.diagnostics} == {
            DiagnosticCode.SYMLINK_CYCLE,
            DiagnosticCode.SYMLINK_ESCAPES_ROOT,
        }
        assert not list(root.rglob(SENTINEL_NAME))

    def test_analyzer_source_uses_no_execution_or_network_primitives(self) -> None:
        """Static self-check of the analyzer's own code (parsing our own source is allowed)."""
        forbidden_modules = {
            "subprocess",
            "importlib",
            "runpy",
            "socket",
            "urllib",
            "http",
            "ssl",
            "ctypes",
            "multiprocessing",
            "pty",
        }
        forbidden_calls = {"exec", "eval", "compile", "__import__", "open"}
        forbidden_os_attrs = {"system", "popen", "fork", "forkpty", "execl", "execv", "execve"}
        forbidden_os_prefixes = ("spawn", "posix_spawn", "exec")

        def forbidden_os_name(attr: str) -> bool:
            return attr in forbidden_os_attrs or attr.startswith(forbidden_os_prefixes)

        sources = sorted(SRC_DIR.rglob("*.py"))
        assert sources, "analyzer sources not found"
        offenders: list[str] = []
        for path in sources:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in forbidden_modules:
                            offenders.append(f"{path.name}:{node.lineno} import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module.split(".")[0] in forbidden_modules:
                        offenders.append(f"{path.name}:{node.lineno} from {module}")
                    # `from os import system` / `from builtins import exec` style imports.
                    for alias in node.names:
                        if (module == "os" and forbidden_os_name(alias.name)) or (
                            module == "builtins" and alias.name in forbidden_calls
                        ):
                            offenders.append(
                                f"{path.name}:{node.lineno} from {module} import {alias.name}"
                            )
                elif isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id in forbidden_calls:
                        offenders.append(f"{path.name}:{node.lineno} {func.id}()")
                    elif (
                        isinstance(func, ast.Attribute)
                        and isinstance(func.value, ast.Name)
                        and func.value.id == "os"
                        and forbidden_os_name(func.attr)
                    ):
                        offenders.append(f"{path.name}:{node.lineno} os.{func.attr}()")
        assert offenders == []

    def test_fixture_trees_are_excluded_from_every_tool(self) -> None:
        """The committed fixture tree is data: pytest, mypy and ruff must all skip it."""
        pyproject = tomllib.loads((TESTS_DIR.parent / "pyproject.toml").read_text("utf-8"))
        tool = pyproject["tool"]
        assert "fixtures" in tool["pytest"]["ini_options"]["norecursedirs"]
        assert FIXTURES.is_relative_to(TESTS_DIR.parent)
        fixtures_rel = FIXTURES.relative_to(TESTS_DIR.parent).as_posix() + "/"
        assert any(re.match(pattern, fixtures_rel) for pattern in tool["mypy"]["exclude"])
        assert fixtures_rel.rstrip("/") in tool["ruff"]["extend-exclude"]
        # Belt and braces: nothing in the fixture tree looks like a test module, and the
        # fixture's packages were never imported into this process.
        assert not any(p.name.startswith("test_") for p in FIXTURES.rglob("*.py"))
        assert {"pkg_a", "pkg_b", "nspkg", "scripts"}.isdisjoint(sys.modules)
