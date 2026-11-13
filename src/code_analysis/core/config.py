"""Typed, immutable workspace configuration (D-0018, D-0019, D-0021, D-0025).

A workspace is an *ordered* set of roots, each with a stable ``root_id``.  Every
path produced by the analyzer is namespaced by its root (D-0010) so that further
roots (including, later, other repositories) can be added without changing the
schema.  All records are frozen dataclasses validated in ``__post_init__``;
invalid input raises :class:`ConfigError` with a message naming the field.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from code_analysis.core.patterns import PatternError, PatternSet

__all__ = [
    "DEFAULT_EXCLUDE_PATTERNS",
    "DEFAULT_INCLUDE_PATTERNS",
    "DEFAULT_MAX_FILE_SIZE_BYTES",
    "ConfigError",
    "RootKind",
    "SafetyPolicy",
    "SymlinkPolicy",
    "TraversalLimits",
    "WorkspaceConfig",
    "WorkspaceRoot",
    "derive_root_id",
]


class ConfigError(ValueError):
    """Raised when a workspace configuration is invalid."""


ROOT_ID_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}")
"""Allowed shape of a root ID (matched with ``fullmatch``, so no trailing newline sneaks in).

``:`` is excluded so ``root_id:relative/path`` is unambiguous.
"""

DEFAULT_INCLUDE_PATTERNS: Final[tuple[str, ...]] = ("**/*.py", "**/*.pyi")
"""Files considered Python source candidates."""

DEFAULT_EXCLUDE_PATTERNS: Final[tuple[str, ...]] = (
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "*.egg-info",
)
"""Entries that are never project source (D-0019).  ``build``/``dist`` are deliberately absent."""

DEFAULT_MAX_FILE_SIZE_BYTES: Final = 2 * 1024 * 1024
"""2 MiB per source file (D-0021)."""


class RootKind(enum.StrEnum):
    """What a root refers to.  New kinds (e.g. remote repositories) extend this enum."""

    LOCAL_DIRECTORY = "local_directory"


class SymlinkPolicy(enum.StrEnum):
    """How symbolic links encountered during discovery are handled (D-0025).

    There is intentionally no policy that follows links outside a root (D-0016).
    """

    NEVER = "never"
    """Never follow symlinks; each one is reported with a diagnostic (default)."""

    WITHIN_ROOT = "within_root"
    """Follow a link only if its real target lies inside the same root; escapes are rejected."""


def derive_root_id(path: Path) -> str:
    """Derive a default root ID from a directory name (lowercased, unsafe chars -> ``-``)."""
    name = path.name or "root"
    candidate = re.sub(r"[^a-z0-9_.-]+", "-", name.lower()).strip("-")[:64]
    if not candidate or not ROOT_ID_PATTERN.fullmatch(candidate):
        candidate = "root"
    return candidate


@dataclass(frozen=True, slots=True)
class WorkspaceRoot:
    """One root of the workspace.

    ``path`` must be absolute and point at an existing directory; it is resolved to its
    real path at construction so that symlinked roots have exactly one canonical path.
    """

    root_id: str
    path: Path
    kind: RootKind = RootKind.LOCAL_DIRECTORY

    def __post_init__(self) -> None:
        if not isinstance(self.root_id, str) or not ROOT_ID_PATTERN.fullmatch(self.root_id):
            raise ConfigError(
                f"root_id {self.root_id!r} is invalid: must match {ROOT_ID_PATTERN.pattern}"
            )
        if not isinstance(self.path, Path):
            raise ConfigError(f"root {self.root_id!r}: path must be a pathlib.Path")
        if not self.path.is_absolute():
            raise ConfigError(f"root {self.root_id!r}: path {str(self.path)!r} must be absolute")
        try:
            resolved = self.path.resolve(strict=True)
        except OSError as exc:
            raise ConfigError(
                f"root {self.root_id!r}: path {str(self.path)!r} does not exist ({exc})"
            ) from exc
        if not resolved.is_dir():
            raise ConfigError(f"root {self.root_id!r}: path {str(self.path)!r} is not a directory")
        if self.kind is not RootKind.LOCAL_DIRECTORY:
            raise ConfigError(f"root {self.root_id!r}: unsupported root kind {self.kind!r}")
        # Frozen dataclass: assign the canonical path through object.__setattr__.
        object.__setattr__(self, "path", resolved)

    @classmethod
    def from_path(cls, path: Path, root_id: str | None = None) -> WorkspaceRoot:
        """Build a root, deriving ``root_id`` from the directory name when not given."""
        return cls(root_id=root_id if root_id is not None else derive_root_id(path), path=path)


@dataclass(frozen=True, slots=True)
class TraversalLimits:
    """Hard bounds on the discovery walk (D-0021).  Exceeding one truncates the result."""

    max_files: int = 100_000
    """Maximum number of accepted source files across all roots."""

    max_depth: int = 64
    """Maximum directory nesting depth below a root (root entries are at depth 1)."""

    max_entries: int = 2_000_000
    """Maximum number of directory entries examined across all roots."""

    def __post_init__(self) -> None:
        for name in ("max_files", "max_depth", "max_entries"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ConfigError(
                    f"TraversalLimits.{name} must be a positive integer, got {value!r}"
                )


@dataclass(frozen=True, slots=True)
class SafetyPolicy:
    """Explicit safety settings applied to every root (D-0021, D-0025, D-0026).

    The non-execution boundary itself is not configurable: there is no setting that
    makes the analyzer import, execute or build target code (D-0015).
    """

    symlink_policy: SymlinkPolicy = SymlinkPolicy.NEVER
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES
    limits: TraversalLimits = field(default_factory=TraversalLimits)

    def __post_init__(self) -> None:
        if not isinstance(self.symlink_policy, SymlinkPolicy):
            raise ConfigError(
                f"symlink_policy must be a SymlinkPolicy, got {self.symlink_policy!r}"
            )
        size = self.max_file_size_bytes
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ConfigError(f"max_file_size_bytes must be a positive integer, got {size!r}")
        if not isinstance(self.limits, TraversalLimits):
            raise ConfigError(f"limits must be a TraversalLimits, got {self.limits!r}")


def _check_roots(roots: tuple[WorkspaceRoot, ...]) -> None:
    """Roots must be ``WorkspaceRoot`` instances with unique IDs and disjoint real paths."""
    if not isinstance(roots, tuple) or not roots:
        raise ConfigError("roots must be a non-empty tuple of WorkspaceRoot")
    seen_ids: dict[str, Path] = {}
    for root in roots:
        if not isinstance(root, WorkspaceRoot):
            raise ConfigError(f"roots must contain WorkspaceRoot instances, got {root!r}")
        if root.root_id in seen_ids:
            raise ConfigError(
                f"duplicate root_id {root.root_id!r} for {str(root.path)!r} "
                f"and {str(seen_ids[root.root_id])!r}"
            )
        seen_ids[root.root_id] = root.path
    for a in roots:
        for b in roots:
            if a is not b and (a.path == b.path or a.path in b.path.parents):
                raise ConfigError(
                    f"roots {a.root_id!r} ({str(a.path)!r}) and {b.root_id!r} "
                    f"({str(b.path)!r}) overlap; roots must be disjoint"
                )


def _check_patterns(name: str, patterns: tuple[str, ...]) -> PatternSet:
    if not isinstance(patterns, tuple):
        raise ConfigError(f"{name} must be a tuple of strings, got {type(patterns).__name__}")
    try:
        return PatternSet.compile(patterns)
    except PatternError as exc:
        raise ConfigError(f"{name}: {exc}") from exc


@dataclass(frozen=True, slots=True)
class WorkspaceConfig:
    """Validated, immutable description of what to discover and how safely to do it."""

    roots: tuple[WorkspaceRoot, ...]
    include_patterns: tuple[str, ...] = DEFAULT_INCLUDE_PATTERNS
    exclude_patterns: tuple[str, ...] = DEFAULT_EXCLUDE_PATTERNS
    safety: SafetyPolicy = field(default_factory=SafetyPolicy)

    def __post_init__(self) -> None:
        _check_roots(self.roots)
        if not self.include_patterns:
            raise ConfigError("include_patterns must contain at least one pattern")
        _check_patterns("include_patterns", self.include_patterns)
        _check_patterns("exclude_patterns", self.exclude_patterns)
        if not isinstance(self.safety, SafetyPolicy):
            raise ConfigError(f"safety must be a SafetyPolicy, got {self.safety!r}")

    @classmethod
    def single_root(
        cls,
        path: Path,
        root_id: str | None = None,
        *,
        include_patterns: tuple[str, ...] = DEFAULT_INCLUDE_PATTERNS,
        exclude_patterns: tuple[str, ...] = DEFAULT_EXCLUDE_PATTERNS,
        safety: SafetyPolicy | None = None,
    ) -> WorkspaceConfig:
        """Convenience constructor for the common single-repository case."""
        root = WorkspaceRoot.from_path(path, root_id)
        return cls(
            roots=(root,),
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            safety=safety if safety is not None else SafetyPolicy(),
        )

    def compiled_includes(self) -> PatternSet:
        return PatternSet.compile(self.include_patterns)

    def compiled_excludes(self) -> PatternSet:
        return PatternSet.compile(self.exclude_patterns)
