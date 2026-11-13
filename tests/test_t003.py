"""T003 — package architecture, tooling and licenses.

Covers: the layered import rules (D-0028), the dependency/license/pin policy (D-0029),
build backend and installability (D-0030), the runtime floor (D-0031), the ruff, mypy
and coverage configuration (D-0032, D-0033), the task runner (D-0034), version
single-sourcing (D-0035), the CLI stub (D-0036), the undecided project license (D-0037),
the T001 follow-ups (D-0038, D-0039), the editable-install check that replaces the
``chflags`` workaround (D-0040) and offline wheel builds whose contents must equal
``src/`` (D-0041).  Everything here runs offline and reads only the repository's own
files; the wheel build uses the venv's pinned setuptools with ``--no-index``.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.metadata
import importlib.util
import os
import re
import shutil
import stat
import subprocess
import sys
import tomllib
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import pytest

import check_install
from code_analysis import __version__
from code_analysis.cli import ExitCode, build_parser, main
from code_analysis.core.config import SafetyPolicy, WorkspaceConfig
from code_analysis.discovery import DiagnosticCode, DiscoveryResult, discover
from code_analysis.discovery import walk as walk_module

TESTS_DIR: Final = Path(__file__).resolve().parent
REPO: Final = TESTS_DIR.parent
SRC: Final = REPO / "src"
PACKAGE: Final = SRC / "code_analysis"
PYPROJECT: Final = REPO / "pyproject.toml"
ARCHITECTURE_DOC: Final = REPO / "docs" / "architecture.md"
DEPENDENCIES_DOC: Final = REPO / "docs" / "dependencies.md"
SAFETY_DOC: Final = REPO / "docs" / "safety-policy.md"
MAKEFILE: Final = REPO / "Makefile"
CHANGELOG: Final = REPO / "CHANGELOG.md"
CHECK_INSTALL: Final = REPO / "scripts" / "check_install.py"
DISTRIBUTION: Final = "code-analysis"
CONSOLE_SCRIPT: Final = "code_analysis.cli:main"


def _pyproject() -> dict[str, Any]:
    return tomllib.loads(PYPROJECT.read_text("utf-8"))


# --------------------------------------------------------------------------------------
# import layering (D-0028) — the map below is normative and must match docs/architecture.md
# --------------------------------------------------------------------------------------

LAYERS: Final[tuple[tuple[str, frozenset[str]], ...]] = (
    ("foundation", frozenset({"core"})),
    ("records", frozenset({"graph.schema", "evidence", "diagnostics"})),
    ("input", frozenset({"discovery", "syntax"})),
    ("structure", frozenset({"scopes", "imports", "symbols"})),
    ("semantics", frozenset({"resolution", "dataflow"})),
    ("dependency", frozenset({"metadata", "compat"})),
    ("persistence", frozenset({"graph"})),
    ("queries", frozenset({"graph.query", "impact", "snapshots"})),
    ("interfaces", frozenset({"cli", "api", "viewer", "__main__"})),
)
ROOT_MODULE: Final = ""
"""``code_analysis/__init__.py``; it may be imported by anyone and imports no subpackage."""


@dataclass(frozen=True, slots=True)
class ImportRef:
    """One import of something inside ``code_analysis``."""

    lineno: int
    module: str
    """Dotted path relative to ``code_analysis`` (``""`` for the package root)."""

    name: str | None
    """Attribute imported from ``module`` (``None`` when a module itself is imported)."""


def _layer_of(module: str) -> tuple[int, str] | None:
    """Longest-prefix layer lookup: ``(layer index, matched package prefix)``."""
    parts = module.split(".") if module else []
    for length in range(len(parts), 0, -1):
        prefix = ".".join(parts[:length])
        for index, (_, packages) in enumerate(LAYERS):
            if prefix in packages:
                return index, prefix
    return None


def _layer_violations(importer: str, refs: Iterable[ImportRef]) -> list[str]:
    """Pure rule checker (R1, R2, R4, R6) so it can be tested on synthetic input."""
    source = _layer_of(importer)
    found: list[str] = []
    for ref in refs:
        where = f"{importer or '__init__'}:{ref.lineno}"
        if importer == ROOT_MODULE:
            found.append(f"{where} R6: package root imports {ref.module!r}")
            continue
        if source is None:
            found.append(f"{where} R4: module {importer!r} is not assigned to a layer")
            continue
        if ref.module == ROOT_MODULE:
            continue  # ``from code_analysis import __version__`` is always fine
        target = _layer_of(ref.module)
        if target is None:
            found.append(f"{where} R4: import target {ref.module!r} is not assigned to a layer")
            continue
        if target[0] > source[0]:
            found.append(
                f"{where} R1: {LAYERS[source[0]][0]} module imports {ref.module!r} "
                f"from higher layer {LAYERS[target[0]][0]}"
            )
        if target[1] != source[1]:
            private = [seg for seg in ref.module.split(".") if seg.startswith("_")]
            if ref.name is not None and ref.name.startswith("_"):
                private.append(ref.name)
            if private:
                found.append(f"{where} R2: private cross-package import of {private}")
    return found


def _source_modules() -> dict[str, Path]:
    """Every module under ``src/code_analysis`` keyed by its dotted path relative to it."""
    modules: dict[str, Path] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        parts = list(path.relative_to(PACKAGE).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        modules[".".join(parts)] = path
    return modules


def _is_module(dotted: str) -> bool:
    location = PACKAGE.joinpath(*dotted.split(".")) if dotted else PACKAGE
    return location.is_dir() or location.with_suffix(".py").is_file()


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text("utf-8"), filename=str(path))


def _internal_imports(tree: ast.Module) -> list[ImportRef]:
    refs: list[ImportRef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top, _, rest = alias.name.partition(".")
                if top == "code_analysis":
                    refs.append(ImportRef(node.lineno, rest, None))
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            top, _, rest = (node.module or "").partition(".")
            if top != "code_analysis":
                continue
            for alias in node.names:
                candidate = f"{rest}.{alias.name}" if rest else alias.name
                if _is_module(candidate):
                    refs.append(ImportRef(node.lineno, candidate, None))
                else:
                    refs.append(ImportRef(node.lineno, rest, alias.name))
    return refs


def _external_imports(tree: ast.Module) -> list[tuple[int, str]]:
    """Top-level names of imported modules that are neither stdlib nor ``code_analysis``."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            top = name.partition(".")[0]
            if top != "code_analysis" and top not in sys.stdlib_module_names:
                found.append((node.lineno, top))
    return found


def _relative_imports(tree: ast.Module) -> list[int]:
    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level > 0]


def _doc_layer_table() -> dict[int, tuple[str, frozenset[str]]]:
    """Parse the normative layer table from docs/architecture.md."""
    row = re.compile(r"^\|\s*(\d+)\s*\|\s*`?(\w+)`?\s*\|([^|]*)\|")
    table: dict[int, tuple[str, frozenset[str]]] = {}
    for line in ARCHITECTURE_DOC.read_text("utf-8").splitlines():
        match = row.match(line)
        if match:
            packages = frozenset(re.findall(r"`([A-Za-z_.]+)`", match.group(3)))
            table[int(match.group(1))] = (match.group(2), packages)
    return table


class TestImportLayering:
    def test_every_module_is_assigned_to_a_layer(self) -> None:
        modules = _source_modules()
        assert ROOT_MODULE in modules
        unmapped = sorted(m for m in modules if m != ROOT_MODULE and _layer_of(m) is None)
        assert unmapped == [], f"add these to LAYERS and docs/architecture.md: {unmapped}"

    def test_layer_map_matches_architecture_doc(self) -> None:
        documented = _doc_layer_table()
        expected = {i: (name, pkgs) for i, (name, pkgs) in enumerate(LAYERS)}
        assert documented == expected

    def test_no_module_breaks_the_layer_rules(self) -> None:
        violations: list[str] = []
        for module, path in _source_modules().items():
            violations.extend(_layer_violations(module, _internal_imports(_parse(path))))
        assert violations == []

    def test_only_absolute_imports(self) -> None:
        offenders = {
            module: lines
            for module, path in _source_modules().items()
            if (lines := _relative_imports(_parse(path)))
        }
        assert offenders == {}

    def test_only_declared_third_party_imports(self) -> None:
        declared = {_requirement(r)[0] for r in _pyproject()["project"]["dependencies"]}
        allowed_import_names = {RUNTIME_IMPORT_NAMES.get(d, d.replace("-", "_")) for d in declared}
        offenders = {
            module: imports
            for module, path in _source_modules().items()
            if (
                imports := [
                    (line, top)
                    for line, top in _external_imports(_parse(path))
                    if top not in allowed_import_names
                ]
            )
        }
        assert offenders == {}

    def test_package_root_imports_no_subpackage(self) -> None:
        tree = _parse(PACKAGE / "__init__.py")
        assert _internal_imports(tree) == []
        assert _external_imports(tree) == []

    def test_stub_packages_contain_only_documentation(self) -> None:
        for stub in ("syntax", "graph"):
            body = _parse(PACKAGE / stub / "__init__.py").body
            assert len(body) == 1
            assert isinstance(body[0], ast.Expr)
            assert isinstance(body[0].value, ast.Constant)
            assert isinstance(body[0].value.value, str)
            assert "planned" in body[0].value.value

    def test_existing_layout_is_as_documented(self) -> None:
        layers = {m: _layer_of(m) for m in _source_modules() if m != ROOT_MODULE}
        assert layers["core.config"] == (0, "core")
        assert layers["discovery.walk"] == (2, "discovery")
        assert layers["syntax"] == (2, "syntax")
        assert layers["graph"] == (6, "graph")
        assert layers["cli.app"] == (8, "cli")
        assert layers["__main__"] == (8, "__main__")

    def test_longest_prefix_wins(self) -> None:
        assert _layer_of("graph.schema.ids") == (1, "graph.schema")
        assert _layer_of("graph.store.sqlite") == (6, "graph")
        assert _layer_of("graph.query") == (7, "graph.query")
        assert _layer_of("nonexistent.thing") is None

    def test_checker_flags_synthetic_violations(self) -> None:
        upward = _layer_violations("core.config", [ImportRef(1, "cli.main", None)])
        assert len(upward) == 1 and "R1" in upward[0]
        private = _layer_violations("cli.main", [ImportRef(2, "graph.query", "_internal")])
        assert len(private) == 1 and "R2" in private[0]
        private_module = _layer_violations("cli.main", [ImportRef(3, "graph.query._impl", None)])
        assert len(private_module) == 1 and "R2" in private_module[0]
        root = _layer_violations(ROOT_MODULE, [ImportRef(4, "core", None)])
        assert len(root) == 1 and "R6" in root[0]
        unmapped = _layer_violations("mystery", [ImportRef(5, "core", None)])
        assert len(unmapped) == 1 and "R4" in unmapped[0]
        # Allowed: same layer, lower layer, private within the same package, the root.
        assert (
            _layer_violations(
                "discovery.walk",
                [
                    ImportRef(6, "core.config", None),
                    ImportRef(7, "discovery.models", "_helper"),
                    ImportRef(8, "syntax", None),
                    ImportRef(9, ROOT_MODULE, "__version__"),
                ],
            )
            == []
        )


# --------------------------------------------------------------------------------------
# dependency, license and pin policy (D-0029)
# --------------------------------------------------------------------------------------

ALLOWED_LICENSES: Final = frozenset(
    {
        "MIT",
        "MIT-0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "0BSD",
        "Apache-2.0",
        "PSF-2.0",
        "Python-2.0",
        "ISC",
        "Zlib",
    }
)
RUNTIME_IMPORT_NAMES: Final[dict[str, str]] = {"packaging": "packaging"}
"""Distribution name -> import name for declared runtime dependencies."""

_REQUIREMENT: Final = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?P<extras>\[[^\]]*\])?\s*(?P<spec>[^;]*?)\s*(?:;.*)?$"
)


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement(text: str) -> tuple[str, str]:
    """``(normalized distribution name, version specifier)`` of a PEP 508 string."""
    match = _REQUIREMENT.match(text.strip())
    assert match is not None, f"unparsable requirement {text!r}"
    return _normalize(match.group("name")), match.group("spec").replace(" ", "")


def _pin_kind(spec: str) -> str:
    """``exact`` (``==X``), ``bounded`` (upper and lower bound or ``~=``) or ``unbounded``."""
    clauses = [c for c in spec.split(",") if c]
    if any(c.startswith("==") and not c.endswith(".*") for c in clauses):
        return "exact"
    if any(c.startswith("~=") for c in clauses):
        return "bounded"
    lower = any(c.startswith(">") for c in clauses)
    upper = any(c.startswith("<") for c in clauses)
    return "bounded" if lower and upper else "unbounded"


_CLAUSE: Final = re.compile(r"^(~=|==|!=|<=|>=|<|>)(\d+(?:\.\d+)*)$")


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def _padded(a: tuple[int, ...], b: tuple[int, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Zero-pad to equal length so that ``1 == 1.0`` as PEP 440 requires."""
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)), b + (0,) * (width - len(b))


def _satisfies(version: str, spec: str) -> bool:
    """PEP 440 subset on dotted-integer versions.

    Operators: ``>=``, ``>``, ``<=``, ``<``, ``==``, ``!=`` and ``~=``.
    """
    for clause in (c for c in spec.split(",") if c):
        match = _CLAUSE.match(clause)
        assert match is not None, f"unsupported clause {clause!r}"
        op, raw_wanted = match.group(1), _version_tuple(match.group(2))
        actual, wanted = _padded(_version_tuple(version), raw_wanted)
        if op == "~=":
            prefix = len(raw_wanted) - 1
            ok = actual >= wanted and actual[:prefix] == wanted[:prefix]
        else:
            ok = {
                "==": actual == wanted,
                "!=": actual != wanted,
                "<=": actual <= wanted,
                ">=": actual >= wanted,
                "<": actual < wanted,
                ">": actual > wanted,
            }[op]
        if not ok:
            return False
    return True


def _license_allowed(expression: str) -> bool:
    expression = expression.strip()
    if not expression or "(" in expression:
        return False
    if " OR " in expression:
        return any(_license_allowed(part) for part in expression.split(" OR "))
    if " AND " in expression:
        return all(_license_allowed(part) for part in expression.split(" AND "))
    return expression in ALLOWED_LICENSES


def _installed_license(distribution: str) -> str | None:
    """License text from installed metadata (expression, then field, then classifier)."""
    try:
        meta = importlib.metadata.metadata(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None
    if "License-Expression" in meta:
        return str(meta["License-Expression"])
    if "License" in meta:
        field = str(meta["License"])
        if field and field != "UNKNOWN" and "\n" not in field:
            return field
    for classifier in meta.get_all("Classifier") or []:
        text = str(classifier)
        if text.startswith("License :: OSI Approved :: "):
            return text.rsplit(" :: ", 1)[-1]
    return None


def _same_license_family(documented: str, installed: str) -> bool:
    """``Apache-2.0`` matches ``Apache Software License``; ``MIT`` matches ``MIT License``."""
    families = {re.split(r"[-\s]", part.strip())[0].lower() for part in documented.split(" OR ")}
    return any(family in installed.lower() for family in families)


def _doc_table(doc: Path, heading: str) -> list[dict[str, str]]:
    """Rows of the first markdown table under ``heading`` as ``{column: cell}`` dicts."""
    lines = doc.read_text("utf-8").splitlines()
    assert heading in lines, f"{heading!r} missing from {doc.name}"
    rows: list[list[str]] = []
    for line in lines[lines.index(heading) + 1 :]:
        if line.startswith("#"):
            break
        if line.startswith("|"):
            rows.append([cell.strip().strip("`") for cell in line.strip().strip("|").split("|")])
        elif rows:
            break
    assert len(rows) >= 2, f"no table under {heading!r}"
    header, body = rows[0], rows[2:]
    return [dict(zip(header, row, strict=True)) for row in body]


def _documented(section: str) -> dict[str, dict[str, str]]:
    rows = _doc_table(DEPENDENCIES_DOC, section)
    return {_normalize(r["Distribution"]): r for r in rows if r["Distribution"] != "_none_"}


class TestDependencyPolicy:
    def test_runtime_dependencies_are_pinned_documented_and_permissive(self) -> None:
        declared = [_requirement(r) for r in _pyproject()["project"]["dependencies"]]
        documented = _documented("## Runtime dependencies")
        assert {name for name, _ in declared} == set(documented)
        for name, spec in declared:
            assert _pin_kind(spec) in ("exact", "bounded"), f"{name}: {spec!r} is unbounded"
            row = documented[name]
            assert _requirement(row["Requirement"]) == (name, spec)
            assert _license_allowed(row["License (SPDX)"]), f"{name}: {row['License (SPDX)']}"
            assert row["Alternative considered"] and row["Why chosen"]

    def test_dev_dependencies_are_exact_pins_documented_and_permissive(self) -> None:
        group = _pyproject()["dependency-groups"]["dev"]
        assert all(isinstance(entry, str) for entry in group)
        declared = [_requirement(entry) for entry in group]
        documented = _documented("## Development dependencies")
        assert {name for name, _ in declared} == set(documented)
        for name, spec in declared:
            assert _pin_kind(spec) == "exact", f"{name}: {spec!r} must be an exact pin"
            row = documented[name]
            assert _requirement(row["Requirement"]) == (name, spec)
            assert row["Tested version"] == spec.removeprefix("==")
            assert _license_allowed(row["License (SPDX)"]), f"{name}: {row['License (SPDX)']}"

    def test_build_requirements_are_bounded_documented_and_permissive(self) -> None:
        declared = [_requirement(r) for r in _pyproject()["build-system"]["requires"]]
        documented = _documented("## Build dependencies")
        assert {name for name, _ in declared} == set(documented)
        for name, spec in declared:
            assert _pin_kind(spec) == "bounded", f"{name}: {spec!r}"
            assert _requirement(documented[name]["Requirement"]) == (name, spec)
            assert _license_allowed(documented[name]["License (SPDX)"])

    def test_dev_setuptools_pin_satisfies_build_range(self) -> None:
        """D-0041: the backend used for offline builds is one the build-system range allows."""
        data = _pyproject()
        (build_spec,) = [spec for name, spec in map(_requirement, data["build-system"]["requires"])]
        (dev_spec,) = [
            spec
            for name, spec in map(_requirement, data["dependency-groups"]["dev"])
            if name == "setuptools"
        ]
        assert _pin_kind(dev_spec) == "exact"
        assert _satisfies(dev_spec.removeprefix("=="), build_spec), (dev_spec, build_spec)

    @pytest.mark.parametrize(
        ("version", "spec", "expected"),
        [
            ("84.2.1", ">=77,<85", True),
            ("85.0.0", ">=77,<85", False),
            ("76.9", ">=77,<85", False),
            ("77", ">=77,<85", True),
            ("1.2.5", "~=1.2", True),
            ("1.3", "~=1.2", True),
            ("2.0", "~=1.2", False),
            ("1.0", "==1.0", True),
            ("1.0", "!=1.0", False),
            ("1.0", "<=1.0,>1", False),
            ("1.0", ">1", False),
            ("1", "~=1.0", True),
            ("1.0", "", True),
        ],
    )
    def test_satisfies(self, version: str, spec: str, expected: bool) -> None:
        assert _satisfies(version, spec) is expected

    def test_pre_approved_candidates_are_permissive(self) -> None:
        for name, row in _documented("## Pre-approved runtime candidates (not yet added)").items():
            assert _license_allowed(row["License (SPDX)"]), name
            assert _pin_kind(_requirement(row["Planned requirement"])[1]) == "bounded", name

    def test_documented_policy_lists_the_same_allowed_licenses(self) -> None:
        text = DEPENDENCIES_DOC.read_text("utf-8")
        match = re.search(r"Allowed SPDX identifiers:(.*?)\.\n", text, re.DOTALL)
        assert match is not None
        assert frozenset(re.findall(r"`([^`]+)`", match.group(1))) == ALLOWED_LICENSES

    @pytest.mark.parametrize("section", ["## Development dependencies", "## Build dependencies"])
    def test_documented_license_matches_installed_metadata(self, section: str) -> None:
        checked = 0
        for name, row in _documented(section).items():
            installed = _installed_license(name)
            if installed is None:
                continue
            assert _same_license_family(row["License (SPDX)"], installed), (name, installed)
            checked += 1
        if checked == 0:
            pytest.skip(f"none of the {section!r} distributions is installed here")

    def test_installed_dev_tool_versions_match_the_pins(self) -> None:
        mismatches: dict[str, tuple[str, str]] = {}
        for entry in _pyproject()["dependency-groups"]["dev"]:
            name, spec = _requirement(entry)
            try:
                installed = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                continue
            if installed != spec.removeprefix("=="):
                mismatches[name] = (spec, installed)
        assert mismatches == {}

    @pytest.mark.parametrize(
        ("spec", "kind"),
        [
            ("==1.2.3", "exact"),
            (">=1.2,<2", "bounded"),
            ("~=1.2", "bounded"),
            (">=1.2,<=1.9", "bounded"),
            (">=1.2", "unbounded"),
            ("<2", "unbounded"),
            ("", "unbounded"),
            ("==1.*", "unbounded"),
            ("!=1.0", "unbounded"),
        ],
    )
    def test_pin_kind(self, spec: str, kind: str) -> None:
        assert _pin_kind(spec) == kind

    @pytest.mark.parametrize(
        ("expression", "allowed"),
        [
            ("MIT", True),
            ("Apache-2.0 OR BSD-2-Clause", True),
            ("MPL-2.0 OR MIT", True),
            ("MIT AND BSD-3-Clause", True),
            ("MIT AND GPL-3.0-only", False),
            ("MPL-2.0", False),
            ("GPL-3.0-or-later", False),
            ("LGPL-2.1", False),
            ("", False),
            ("(MIT OR GPL-2.0)", False),
            ("mit", False),
        ],
    )
    def test_license_expression_policy(self, expression: str, allowed: bool) -> None:
        assert _license_allowed(expression) is allowed

    def test_requirement_parsing(self) -> None:
        assert _requirement("Pytest-Cov [toml] >= 7, < 8 ; python_version < '4'") == (
            "pytest-cov",
            ">=7,<8",
        )
        assert _requirement("ruff==0.17.5") == ("ruff", "==0.17.5")


# --------------------------------------------------------------------------------------
# package metadata (D-0030, D-0031, D-0035, D-0037)
# --------------------------------------------------------------------------------------

_PEP440_SIMPLE: Final = re.compile(r"^\d+(\.\d+)+((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?$")


def _version_literal() -> str:
    """``__version__`` read statically, the way setuptools' ``attr:`` reader does."""
    for node in _parse(PACKAGE / "__init__.py").body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets
        ):
            assert isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
            return node.value.value
    raise AssertionError("__version__ literal not found")


class TestPackageMetadata:
    def test_version_is_single_sourced(self) -> None:
        project = _pyproject()["project"]
        assert project["dynamic"] == ["version"]
        assert "version" not in project
        dynamic = _pyproject()["tool"]["setuptools"]["dynamic"]
        assert dynamic["version"] == {"attr": "code_analysis.__version__"}
        assert _version_literal() == __version__
        assert _PEP440_SIMPLE.match(__version__), __version__

    def test_installed_distribution_matches_source(self) -> None:
        try:
            installed = importlib.metadata.version(DISTRIBUTION)
        except importlib.metadata.PackageNotFoundError:
            pytest.skip("code-analysis is not installed in this interpreter")
        assert installed == __version__
        meta = importlib.metadata.metadata(DISTRIBUTION)
        assert str(meta["Requires-Python"]) == _pyproject()["project"]["requires-python"]
        scripts = importlib.metadata.entry_points(group="console_scripts").select(name=DISTRIBUTION)
        assert [ep.value for ep in scripts] == [CONSOLE_SCRIPT]

    def test_console_script_entry_point_declared(self) -> None:
        assert _pyproject()["project"]["scripts"] == {DISTRIBUTION: CONSOLE_SCRIPT}
        assert build_parser().prog == DISTRIBUTION

    def test_build_backend_is_setuptools(self) -> None:
        build = _pyproject()["build-system"]
        assert build["build-backend"] == "setuptools.build_meta"
        assert [_requirement(r)[0] for r in build["requires"]] == ["setuptools"]
        tool = _pyproject()["tool"]["setuptools"]
        assert tool["package-dir"] == {"": "src"}
        assert tool["packages"]["find"]["where"] == ["src"]
        assert tool["package-data"] == {"code_analysis": ["py.typed"]}
        assert (PACKAGE / "py.typed").is_file()

    def test_requires_python_floor_is_consistent(self) -> None:
        data = _pyproject()
        assert data["project"]["requires-python"] == ">=3.12"
        assert "Programming Language :: Python :: 3.12" in data["project"]["classifiers"]
        assert data["tool"]["ruff"]["target-version"] == "py312"
        assert data["tool"]["mypy"]["python_version"] == "3.12"
        assert sys.version_info >= (3, 12)

    def test_no_license_is_claimed_until_decided(self) -> None:
        """D-0037 (needs-user): invert this test when the user picks a license."""
        project = _pyproject()["project"]
        assert "license" not in project
        assert "license-files" not in project
        assert not any(c.startswith("License ::") for c in project["classifiers"])
        assert not list(REPO.glob("LICENSE*"))
        assert "D-0037" in (REPO / "README.md").read_text("utf-8")

    def test_metadata_basics(self) -> None:
        project = _pyproject()["project"]
        assert project["name"] == DISTRIBUTION
        assert project["readme"] == "README.md"
        assert project["dependencies"] == []
        assert "Typing :: Typed" in project["classifiers"]
        assert project["urls"]["Repository"].startswith("https://")


# --------------------------------------------------------------------------------------
# CLI stub (D-0036)
# --------------------------------------------------------------------------------------


class TestCliStub:
    def test_version_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--version"]) == 0
        out, err = capsys.readouterr()
        assert out == f"{DISTRIBUTION} {__version__}\n"
        assert err == ""

    def test_help_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--help"]) == 0
        out, _ = capsys.readouterr()
        assert out.startswith(f"usage: {DISTRIBUTION}")
        assert "never imported or executed" in out
        assert "T024" in out

    def test_no_arguments_prints_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main([]) == int(ExitCode.OK) == 0
        out, _ = capsys.readouterr()
        assert out.startswith(f"usage: {DISTRIBUTION}")

    def test_unknown_argument_is_a_usage_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--bogus"]) == int(ExitCode.USAGE) == 2
        out, err = capsys.readouterr()
        assert out == ""
        assert "usage:" in err and "--bogus" in err

    def test_no_spec_command_exists_yet(self) -> None:
        for command in ("index", "status", "search", "symbol", "impact", "export"):
            assert main([command]) == ExitCode.USAGE

    def test_system_exit_codes_are_normalised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``SystemExit(None)`` means success, a non-int code is reported as a usage error."""
        cli_module = importlib.import_module("code_analysis.cli.app")

        class FakeParser:
            def __init__(self, code: object) -> None:
                self.code = code

            def parse_args(self, argv: object) -> None:
                raise SystemExit(self.code)

        for code, expected in ((None, 0), (7, 7), ("message", 2)):
            monkeypatch.setattr(cli_module, "build_parser", lambda code=code: FakeParser(code))
            assert main([]) == expected

    def test_exit_codes_are_stable(self) -> None:
        assert [(c.name, int(c)) for c in ExitCode] == [("OK", 0), ("USAGE", 2)]

    def test_python_dash_m_entry_point(self) -> None:
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        run = subprocess.run(
            [sys.executable, "-m", "code_analysis", "--version"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=60,
        )
        assert (run.returncode, run.stdout, run.stderr) == (
            0,
            f"{DISTRIBUTION} {__version__}\n",
            "",
        )
        usage = subprocess.run(
            [sys.executable, "-m", "code_analysis", "--nope"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=60,
        )
        assert usage.returncode == 2


# --------------------------------------------------------------------------------------
# tooling configuration (D-0032, D-0033, D-0034, D-0035)
# --------------------------------------------------------------------------------------


class TestToolingConfig:
    def test_ruff_rule_families_and_allowlists(self) -> None:
        ruff = _pyproject()["tool"]["ruff"]
        selected = set(ruff["lint"]["select"])
        assert {"E", "W", "F", "I", "B", "UP", "N", "SIM", "RUF"} <= selected  # D-0017
        assert {"PTH", "S", "ANN", "FA", "TID", "T20"} <= selected  # D-0032
        assert ruff["lint"]["flake8-tidy-imports"]["ban-relative-imports"] == "all"
        ignores = ruff["lint"]["per-file-ignores"]
        assert ignores["src/code_analysis/discovery/walk.py"] == ["PTH"]
        assert ignores["src/code_analysis/cli/*"] == ["T20"]
        assert set(ignores["tests/*"]) == {"S101", "ANN401", "S603"}
        assert set(ignores["scripts/*"]) == {"T20", "S603"}
        assert ruff["src"] == ["src", "tests", "scripts"]
        # No src allowlist disables the bandit family.
        assert not any("S" in codes and path.startswith("src/") for path, codes in ignores.items())
        assert ruff["line-length"] == 100

    def test_mypy_strict_and_fixtures_excluded_everywhere(self) -> None:
        tool = _pyproject()["tool"]
        assert tool["mypy"]["strict"] is True
        assert tool["mypy"]["warn_unreachable"] is True
        fixtures_rel = (TESTS_DIR / "fixtures").relative_to(REPO).as_posix() + "/"
        assert any(re.match(pattern, fixtures_rel) for pattern in tool["mypy"]["exclude"])
        assert fixtures_rel.rstrip("/") in tool["ruff"]["extend-exclude"]
        assert "fixtures" in tool["pytest"]["ini_options"]["norecursedirs"]
        assert tool["pytest"]["ini_options"]["xfail_strict"] is True
        # Development tooling is held to the same gates as the package (D-0040).
        assert tool["mypy"]["files"] == ["src", "tests", "scripts"]
        assert "scripts" in tool["mypy"]["mypy_path"].split(":")
        # Tests never depend on the install state (D-0040).
        assert tool["pytest"]["ini_options"]["pythonpath"] == ["src", "scripts"]

    def test_coverage_threshold_is_recorded_consistently(self) -> None:
        coverage = _pyproject()["tool"]["coverage"]
        assert coverage["run"]["branch"] is True
        assert coverage["run"]["source"] == ["code_analysis"]
        assert coverage["report"]["fail_under"] == 90
        makefile = MAKEFILE.read_text("utf-8")
        match = re.search(r"^COV_FAIL_UNDER \?= (\d+)$", makefile, re.MULTILINE)
        assert match is not None and int(match.group(1)) == coverage["report"]["fail_under"]
        assert "--cov-branch" in makefile and "--cov-fail-under=$(COV_FAIL_UNDER)" in makefile
        # Plain ``pytest`` stays coverage-free (D-0033).
        assert "--cov" not in _pyproject()["tool"]["pytest"]["ini_options"]["addopts"]

    def test_makefile_declares_expected_targets(self) -> None:
        makefile = MAKEFILE.read_text("utf-8")
        targets = set(re.findall(r"^([a-z-]+):", makefile, re.MULTILINE))
        expected = {
            "help",
            "venv",
            "install",
            "check-install",
            "build",
            "test",
            "typecheck",
            "lint",
            "format",
            "coverage",
            "licenses",
            "check",
            "clean-build",
            "clean",
        }
        assert expected <= targets
        phony = re.search(r"^\.PHONY: (.*)$", makefile, re.MULTILINE)
        assert phony is not None and expected <= set(phony.group(1).split())
        # D-0040: no flag patching; the install is verified and the failure explained.
        assert "chflags" not in makefile
        assert makefile.count("$(BIN)/python scripts/check_install.py") == 2
        # D-0042: PEP 735 groups need pip >= 25.1; the upgrade precedes `--group`.
        upgrade = makefile.index('pip install --upgrade "pip>=25.1"')
        assert upgrade < makefile.index("pip install -e .") < makefile.index("--group dev")
        # D-0041: everything that builds from the working tree cleans build/ first.
        assert re.search(r"^install:.*\bclean-build\b", makefile, re.MULTILINE)
        assert re.search(r"^build:.*\bclean-build\b", makefile, re.MULTILINE)
        assert re.search(r"^clean:.*\bclean-build\b", makefile, re.MULTILINE)
        assert "--no-deps --no-build-isolation --no-index" in makefile
        assert "mypy --strict src tests scripts" in makefile
        assert "ruff format --check ." in makefile

    def test_make_is_available_or_documented(self) -> None:
        make = shutil.which("make")
        if make is None:
            pytest.skip("make not installed; README lists the manual commands")
        run = subprocess.run(
            [make, "-n", "lint"], capture_output=True, text=True, check=False, cwd=REPO
        )
        assert run.returncode == 0, run.stderr
        assert "ruff check ." in run.stdout

    @pytest.mark.parametrize(
        ("target", "build_step"),
        [("install", "pip install -e ."), ("build", "pip wheel --no-deps")],
    )
    def test_make_build_targets_clean_before_building(self, target: str, build_step: str) -> None:
        """Dry-run the recipe: ``rm -rf build dist ...`` precedes the build (D-0041)."""
        make = shutil.which("make")
        if make is None:
            pytest.skip("make not installed; README lists the manual commands")
        run = subprocess.run(
            [make, "-n", target], capture_output=True, text=True, check=False, cwd=REPO
        )
        assert run.returncode == 0, run.stderr
        lines = run.stdout.splitlines()
        (clean_index,) = [i for i, line in enumerate(lines) if "rm -rf build dist" in line]
        (build_index,) = [i for i, line in enumerate(lines) if build_step in line]
        assert clean_index < build_index
        assert "chflags" not in run.stdout
        if target == "install":
            assert lines[-1].endswith("scripts/check_install.py")

    def test_changelog_follows_keep_a_changelog(self) -> None:
        text = CHANGELOG.read_text("utf-8")
        assert text.startswith("# Changelog")
        assert "keepachangelog.com" in text
        assert "## [Unreleased]" in text
        assert "### Added" in text

    def test_architecture_doc_describes_the_rules(self) -> None:
        text = ARCHITECTURE_DOC.read_text("utf-8")
        for rule in ("R1", "R2", "R3", "R4", "R5", "R6"):
            assert f"**{rule} " in text
        for topic in ("storage adapter", "root_id", "planned", "StrEnum", "D-0028"):
            assert topic in text


# --------------------------------------------------------------------------------------
# wheel contents equal src/ (D-0041)
# --------------------------------------------------------------------------------------


def _source_files() -> frozenset[str]:
    """Wheel-relative names of every file that lives under ``src/code_analysis``."""
    return frozenset(
        f"code_analysis/{path.relative_to(PACKAGE).as_posix()}"
        for path in PACKAGE.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )


@pytest.fixture(scope="module")
def wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a wheel from a clean copy of the project, offline, with the venv's backend."""
    for module in ("setuptools", "pip"):
        if importlib.util.find_spec(module) is None:
            pytest.skip(f"{module} is not importable here; `make install` adds the dev group")
    work = tmp_path_factory.mktemp("wheel")
    project = work / "project"
    project.mkdir()
    shutil.copytree(
        SRC,
        project / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"),
    )
    for name in ("pyproject.toml", "README.md"):
        shutil.copy(REPO / name, project / name)
    out = work / "dist"
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--no-index",
            "--wheel-dir",
            str(out),
            str(project),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=work,
        timeout=300,
        env={**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
    )
    assert run.returncode == 0, run.stdout + run.stderr
    (built,) = out.glob("*.whl")
    return built


class TestWheelContents:
    def test_wheel_contains_exactly_the_source_files(self, wheel: Path) -> None:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
        shipped = frozenset(n for n in names if n.startswith("code_analysis/"))
        expected = _source_files()
        assert shipped - expected == frozenset(), "stale or undeclared files in the wheel"
        assert expected - shipped == frozenset(), "source files missing from the wheel"
        assert "code_analysis/py.typed" in shipped
        assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)

    def test_wheel_metadata_matches_pyproject(self, wheel: Path) -> None:
        assert wheel.name == f"code_analysis-{__version__}-py3-none-any.whl"
        with zipfile.ZipFile(wheel) as archive:
            (info,) = {n.split("/")[0] for n in archive.namelist() if ".dist-info/" in n}
            metadata = archive.read(f"{info}/METADATA").decode("utf-8")
            entry_points = archive.read(f"{info}/entry_points.txt").decode("utf-8")
        assert f"\nVersion: {__version__}\n" in metadata
        requires_python = _pyproject()["project"]["requires-python"]
        assert f"\nRequires-Python: {requires_python}\n" in metadata
        assert "\nRequires-Dist:" not in metadata  # zero runtime dependencies (D-0029)
        assert "\nLicense-Expression:" not in metadata  # undecided (D-0037)
        assert "[console_scripts]" in entry_points
        assert f"{DISTRIBUTION} = {CONSOLE_SCRIPT}" in entry_points


# --------------------------------------------------------------------------------------
# editable-install check replacing the chflags workaround (D-0040)
# --------------------------------------------------------------------------------------

_ICLOUD_XATTRS: Final = ["com.apple.icloud.desktop", "com.apple.file-provider-domain-id"]


def _fake_listxattr(synced: Path, names: list[str]) -> Any:
    """``os.listxattr`` stand-in reporting ``names`` on ``synced`` only."""

    def listxattr(
        path: str | bytes | os.PathLike[str], *, follow_symlinks: bool = True
    ) -> list[str]:
        return list(names) if Path(os.fsdecode(path)) == synced else []

    return listxattr


class TestInstallCheck:
    def test_hidden_pth_detection(self, tmp_path: Path) -> None:
        visible = tmp_path / "visible.pth"
        visible.write_text("src\n", encoding="utf-8")
        assert check_install.is_hidden(visible) is False
        assert check_install.hidden_pth_files(tmp_path) == ()
        if not hasattr(os, "chflags") or not hasattr(stat, "UF_HIDDEN"):
            pytest.skip("UF_HIDDEN is a BSD/macOS file flag")
        hidden = tmp_path / "__editable__.hidden.pth"
        hidden.write_text("src\n", encoding="utf-8")
        os.chflags(hidden, stat.UF_HIDDEN)
        other = tmp_path / "notes.txt"
        other.write_text("", encoding="utf-8")
        os.chflags(other, stat.UF_HIDDEN)
        assert check_install.is_hidden(hidden) is True
        assert check_install.hidden_pth_files(tmp_path) == (hidden,)

    def test_cloud_sync_provider_icloud_xattr(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        synced = (tmp_path / "Desktop").resolve()
        venv = synced / "repo" / ".venv" / "lib" / "site-packages"
        venv.mkdir(parents=True)
        monkeypatch.setattr(os, "listxattr", _fake_listxattr(synced, _ICLOUD_XATTRS), raising=False)
        assert check_install.cloud_sync_provider(venv) == (synced, "iCloud Drive")
        assert check_install.cloud_sync_provider(synced) == (synced, "iCloud Drive")
        assert check_install.cloud_sync_provider(tmp_path / "elsewhere") is None

    def test_cloud_sync_provider_generic_file_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        synced = (tmp_path / "Dropbox").resolve()
        venv = synced / ".venv"
        venv.mkdir(parents=True)
        monkeypatch.setattr(
            os, "listxattr", _fake_listxattr(synced, [_ICLOUD_XATTRS[1]]), raising=False
        )
        assert check_install.cloud_sync_provider(venv) == (
            synced,
            "a File Provider cloud-sync service",
        )

    def test_cloud_sync_provider_mobile_documents_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(os, "listxattr", _fake_listxattr(tmp_path, []), raising=False)
        container = tmp_path / "Library" / "Mobile Documents"
        venv = container / "com~apple~CloudDocs" / "repo" / ".venv"
        venv.mkdir(parents=True)
        assert check_install.cloud_sync_provider(venv) == (container.resolve(), "iCloud Drive")

    def test_darwin_xattr_names_reads_real_attributes(self, tmp_path: Path) -> None:
        """macOS has no ``os.listxattr``; the ctypes path must see what ``xattr -w`` wrote."""
        if sys.platform != "darwin":
            pytest.skip("listxattr(2) through ctypes is the macOS path")
        target = tmp_path / "file"
        target.write_text("", encoding="utf-8")
        assert check_install._darwin_xattr_names(target) == frozenset()
        subprocess.run(
            ["/usr/bin/xattr", "-w", "com.example.check-install", "1", str(target)],
            check=True,
            timeout=60,
        )
        assert check_install._darwin_xattr_names(target) == {"com.example.check-install"}
        assert check_install._xattr_names(target) == {"com.example.check-install"}
        assert check_install._darwin_xattr_names(tmp_path / "missing") == frozenset()

    def test_cloud_sync_provider_without_xattr_support(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delattr(os, "listxattr", raising=False)
        assert check_install.cloud_sync_provider(tmp_path) is None

        def failing(path: object, *, follow_symlinks: bool = True) -> list[str]:
            raise OSError("not supported")

        monkeypatch.setattr(os, "listxattr", failing, raising=False)
        assert check_install.cloud_sync_provider(tmp_path) is None

    def test_assess_ok(self, tmp_path: Path) -> None:
        report = check_install.assess(
            python=tmp_path / "bin" / "python",
            site_packages=tmp_path / "lib" / "site-packages",
            repo_src=SRC,
            location=PACKAGE / "__init__.py",
            import_error="",
            hidden=(),
            provider=None,
        )
        assert report.ok is True
        text = "\n".join(report.lines)
        assert "editable install usable" in text
        assert "ERROR" not in text and "Cause" not in text and "Options" not in text

    def test_assess_reports_every_cause_and_the_options(self, tmp_path: Path) -> None:
        site = tmp_path / "Desktop" / "repo" / ".venv" / "lib" / "site-packages"
        pth = site / "__editable__.code_analysis-0.1.0.pth"
        report = check_install.assess(
            python=tmp_path / "Desktop" / "repo" / ".venv" / "bin" / "python",
            site_packages=site,
            repo_src=SRC,
            location=None,
            import_error="Traceback\nModuleNotFoundError: No module named 'code_analysis'",
            hidden=(pth,),
            provider=(tmp_path / "Desktop", "iCloud Drive"),
        )
        assert report.ok is False
        text = "\n".join(report.lines)
        assert "ERROR: `import code_analysis` fails" in text
        assert "ModuleNotFoundError" in text
        assert str(pth) in text and "UF_HIDDEN" in text
        assert "managed by iCloud Drive" in text and "D-0040" in text
        assert "chflags nohidden` does not last" in text
        assert "make VENV=~/.venvs/code-analysis install" in text
        assert "Move the repository" in text
        assert "pytest puts src/ on" in text and "console" in text

    def test_assess_rejects_a_foreign_location(self, tmp_path: Path) -> None:
        elsewhere = tmp_path / "site-packages" / "code_analysis" / "__init__.py"
        report = check_install.assess(
            python=tmp_path / "python",
            site_packages=tmp_path / "site-packages",
            repo_src=SRC,
            location=elsewhere,
            import_error="",
            hidden=(),
            provider=None,
        )
        assert report.ok is False
        assert any("resolves to" in line and str(elsewhere) in line for line in report.lines)
        assert report.lines[-len(check_install._OPTIONS) :] == check_install._OPTIONS

    def test_assess_hidden_pth_alone_fails(self, tmp_path: Path) -> None:
        pth = tmp_path / "x.pth"
        report = check_install.assess(
            python=tmp_path / "python",
            site_packages=tmp_path,
            repo_src=SRC,
            location=PACKAGE / "__init__.py",
            import_error="",
            hidden=(pth,),
            provider=None,
        )
        assert report.ok is False
        assert any(str(pth) in line for line in report.lines)

    def test_import_location_uses_a_fresh_isolated_interpreter(self, tmp_path: Path) -> None:
        if os.name != "posix":
            pytest.skip("fake interpreters are POSIX shell scripts")
        good = tmp_path / "good-python"
        good.write_text(
            '#!/bin/sh\n[ "$1" = -I ] || exit 9\necho /fake/code_analysis/__init__.py\n'
        )
        good.chmod(0o700)
        bad = tmp_path / "bad-python"
        bad.write_text("#!/bin/sh\necho 'ModuleNotFoundError: nope' >&2\nexit 1\n")
        bad.chmod(0o700)
        assert check_install.import_location(good) == (Path("/fake/code_analysis/__init__.py"), "")
        assert check_install.import_location(bad) == (None, "ModuleNotFoundError: nope")
        # The real interpreter: either outcome is valid here, but the shape is fixed.
        location, error = check_install.import_location(Path(sys.executable))
        assert (location is None) == bool(error)

    def test_main_exit_codes(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(
            check_install, "import_location", lambda python: (PACKAGE / "__init__.py", "")
        )
        monkeypatch.setattr(check_install, "hidden_pth_files", lambda site: ())
        monkeypatch.setattr(check_install, "cloud_sync_provider", lambda site: None)
        assert check_install.main([]) == 0
        out, err = capsys.readouterr()
        assert "editable install usable" in out and err == ""

        monkeypatch.setattr(
            check_install,
            "cloud_sync_provider",
            lambda site: (Path("/Users/x/Desktop"), "iCloud Drive"),
        )
        assert check_install.main(None) == 1
        out, err = capsys.readouterr()
        assert out == "" and "iCloud Drive" in err and "make VENV=" in err

        assert check_install.main(["--bogus"]) == 2
        _, err = capsys.readouterr()
        assert "usage" in err

    def test_script_runs_as_a_program(self) -> None:
        usage = subprocess.run(
            [sys.executable, str(CHECK_INSTALL), "--bogus"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert usage.returncode == 2 and "usage" in usage.stderr
        run = subprocess.run(
            [sys.executable, str(CHECK_INSTALL)],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        # The outcome depends on the host (D-0040, Q14); the contract does not.
        assert run.returncode in (0, 1)
        report = run.stdout if run.returncode == 0 else run.stderr
        assert "import code_analysis" in report
        if run.returncode == 1:
            assert "make VENV=" in report

    def test_script_is_stdlib_only_and_documented(self) -> None:
        tree = _parse(CHECK_INSTALL)
        assert _external_imports(tree) == []
        assert _internal_imports(tree) == []  # never imports the package it checks
        assert "D-0040" in (ast.get_docstring(tree) or "")
        readme = (REPO / "README.md").read_text("utf-8")
        for phrase in (
            "iCloud Drive",
            "UF_HIDDEN",
            "VENV=",
            'pythonpath = ["src"]',
            "D-0040",
            "Q14",
        ):
            assert phrase in readme, phrase
        assert "wheel extraction" not in readme  # the D-0030 misdiagnosis is gone


# --------------------------------------------------------------------------------------
# T001 follow-ups (D-0038, D-0039)
# --------------------------------------------------------------------------------------


def _write(path: Path, content: str = "x = 1\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _paths(result: DiscoveryResult) -> list[str]:
    return [f.relative_path for f in result.files]


class TestT001FollowUps:
    def test_open_flags_include_o_binary_when_available(self) -> None:
        source = (PACKAGE / "discovery" / "walk.py").read_text("utf-8")
        assert 'getattr(os, "O_BINARY", 0)' in source
        # The flag must take part in the _OPEN_FLAGS expression, not merely be defined.
        (assignment,) = [
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "_OPEN_FLAGS"
        ]
        assert assignment.value is not None
        used = {n.id for n in ast.walk(assignment.value) if isinstance(n, ast.Name)}
        assert {"_O_BINARY", "_O_NOFOLLOW", "_O_CLOEXEC"} <= used
        flags = walk_module._OPEN_FLAGS
        assert flags & os.O_RDONLY == os.O_RDONLY
        assert flags & getattr(os, "O_NOFOLLOW", 0) == getattr(os, "O_NOFOLLOW", 0)
        if hasattr(os, "O_BINARY"):
            assert flags & os.O_BINARY == os.O_BINARY
        else:
            assert walk_module._O_BINARY == 0

    def test_stale_decision_references_removed(self) -> None:
        for path in (PACKAGE / "core" / "config.py", TESTS_DIR / "test_t001.py"):
            assert "D-0020" not in path.read_text("utf-8"), path.name

    def test_safety_policy_wording_is_precise(self) -> None:
        text = SAFETY_DOC.read_text("utf-8")
        assert "never `stat`-ed, so" not in text
        assert "`lstat`/`readlink` metadata" in text
        assert "does not depend on whether the target exists" in text
        assert "**no directory-swap protection**" in text
        assert "D-0039" in text and "D-0038" in text
        walk_doc = ast.get_docstring(_parse(PACKAGE / "discovery" / "walk.py")) or ""
        assert "no directory-swap protection" in walk_doc
        assert "lstat" in walk_doc and "readlink" in walk_doc

    @pytest.mark.parametrize("target_exists", [True, False])
    def test_escape_diagnostic_independent_of_target_existence(
        self, tmp_path: Path, target_exists: bool
    ) -> None:
        """realpath only resolves metadata; an outside target is never opened."""
        outside = tmp_path / "outside"
        outside.mkdir()
        if target_exists:
            _write(outside / "secret.py", "TOKEN = 1\n")
        root = tmp_path / "root"
        _write(root / "ok.py")
        (root / "leak.py").symlink_to(outside / "secret.py")
        opened: list[str] = []
        real_open = os.open

        def recording_open(
            path: str | bytes, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
        ) -> int:
            opened.append(os.fsdecode(path))
            return real_open(path, flags, mode, dir_fd=dir_fd)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(os, "open", recording_open)
            result = discover(WorkspaceConfig.single_root(root, "r", safety=SafetyPolicy()))
        assert _paths(result) == ["ok.py"]
        assert [(d.code, d.path) for d in result.diagnostics] == [
            (DiagnosticCode.SYMLINK_ESCAPES_ROOT, "leak.py")
        ]
        assert opened, "the walk opens at least the root directory"
        assert not any("outside" in p for p in opened)

    @pytest.mark.xfail(
        strict=True,
        reason="known limitation (D-0039, T029): the no-dir_fd fallback mode cannot detect a "
        "directory swapped for a symlink after classification",
    )
    def test_fallback_mode_has_no_directory_swap_protection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

        monkeypatch.setattr(walk_module, "_FD_TRAVERSAL", False)
        monkeypatch.setattr(walk_module._RootWalker, "_open_dir", staticmethod(racing_open_dir))
        result = discover(WorkspaceConfig.single_root(root, "r"))
        # Desired behaviour (what descriptor-relative traversal guarantees, D-0026):
        assert "swap/leak.py" not in _paths(result)
        assert _sha256(outside / "leak.py") not in {f.sha256 for f in result.files}
