"""Immutable result records produced by discovery (D-0021, D-0022).

None of these records ever holds file *content*: only paths, sizes, hashes and
classification facts (D-0012, SPEC section 3.7).
"""

from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass
from typing import Any

__all__ = [
    "Diagnostic",
    "DiagnosticCode",
    "DiscoveryResult",
    "DiscoverySummary",
    "PackageInfo",
    "PackageKind",
    "Severity",
    "SourceFile",
    "SourceKind",
    "workspace_path",
]


def workspace_path(root_id: str, relative_path: str) -> str:
    """Canonical workspace path ``"<root_id>:<relative posix path>"`` (D-0018)."""
    return f"{root_id}:{relative_path}"


class SourceKind(enum.StrEnum):
    PY = "py"
    PYI = "pyi"


class PackageKind(enum.StrEnum):
    REGULAR = "regular"
    """Directory with an ``__init__.py``."""

    NAMESPACE_CANDIDATE = "namespace_candidate"
    """Directory holding sources/packages but no ``__init__.py``; may or may not be importable."""


class Severity(enum.StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticCode(enum.StrEnum):
    """Stable reason codes.  Values are part of the public, machine-readable output."""

    ROOT_UNAVAILABLE = "root_unavailable"
    EXCLUDED_BY_PATTERN = "excluded_by_pattern"
    SYMLINK_NOT_FOLLOWED = "symlink_not_followed"
    SYMLINK_ESCAPES_ROOT = "symlink_escapes_root"
    SYMLINK_TARGET_MISSING = "symlink_target_missing"
    SYMLINK_ALIAS = "symlink_alias"
    """In-root directory link; the real directory is reported under its own path (D-0025)."""

    SYMLINK_CYCLE = "symlink_cycle"
    """In-root directory link pointing at an ancestor of its own location (D-0025)."""
    FILE_TOO_LARGE = "file_too_large"
    NOT_REGULAR_FILE = "not_regular_file"
    UNREADABLE = "unreadable"
    INVALID_FILENAME = "invalid_filename"
    MAX_DEPTH_EXCEEDED = "max_depth_exceeded"
    LIMIT_REACHED = "limit_reached"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A structured record of something that was skipped, rejected or bounded.

    ``path`` is root-relative (POSIX) or ``"."`` for the root itself.  ``message`` only
    ever contains paths, pattern text and numbers, never file content.
    """

    code: DiagnosticCode
    severity: Severity
    root_id: str
    path: str
    message: str

    @property
    def workspace_path(self) -> str:
        return workspace_path(self.root_id, self.path)


@dataclass(frozen=True, slots=True)
class SourceFile:
    """A discovered Python source or stub file.  Identity basis: path + sha256."""

    root_id: str
    relative_path: str
    kind: SourceKind
    size_bytes: int
    sha256: str

    @property
    def workspace_path(self) -> str:
        return workspace_path(self.root_id, self.relative_path)

    @property
    def name(self) -> str:
        return self.relative_path.rsplit("/", 1)[-1]

    @property
    def is_package_init(self) -> bool:
        return self.name in ("__init__.py", "__init__.pyi")


@dataclass(frozen=True, slots=True)
class PackageInfo:
    """Layout facts about a directory that holds sources or packages.

    Discovery reports facts only; whether a ``NAMESPACE_CANDIDATE`` is really an
    importable namespace package depends on the import search path and is decided
    by import resolution (T008), not here.
    """

    root_id: str
    relative_path: str
    kind: PackageKind
    has_init_py: bool
    has_init_pyi: bool
    importable_name: bool
    """Whether the directory's basename is a valid, non-keyword Python identifier."""

    @property
    def workspace_path(self) -> str:
        return workspace_path(self.root_id, self.relative_path)


@dataclass(frozen=True, slots=True)
class DiscoverySummary:
    """Bounded aggregate counters, so nothing is omitted silently (D-0022)."""

    roots: int
    entries_examined: int
    directories_visited: int
    source_files: int
    ignored_files: int
    """Files that did not match any include pattern (not diagnosed individually)."""

    diagnostics: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """Complete, sorted discovery output.  Equal inputs produce equal results."""

    files: tuple[SourceFile, ...]
    packages: tuple[PackageInfo, ...]
    diagnostics: tuple[Diagnostic, ...]
    summary: DiscoverySummary

    @property
    def truncated(self) -> bool:
        return self.summary.truncated

    def content_fingerprint(self) -> str:
        """SHA-256 over all ``(workspace_path, sha256)`` pairs in order; stable across runs."""
        digest = hashlib.sha256()
        for file in self.files:
            digest.update(file.workspace_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(file.sha256.encode("ascii"))
            digest.update(b"\n")
        return digest.hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """JSON-compatible, deterministic representation (enums become their string values)."""
        return {
            "files": [
                {
                    "root_id": f.root_id,
                    "relative_path": f.relative_path,
                    "workspace_path": f.workspace_path,
                    "kind": f.kind.value,
                    "size_bytes": f.size_bytes,
                    "sha256": f.sha256,
                }
                for f in self.files
            ],
            "packages": [
                {
                    "root_id": p.root_id,
                    "relative_path": p.relative_path,
                    "workspace_path": p.workspace_path,
                    "kind": p.kind.value,
                    "has_init_py": p.has_init_py,
                    "has_init_pyi": p.has_init_pyi,
                    "importable_name": p.importable_name,
                }
                for p in self.packages
            ],
            "diagnostics": [
                {
                    "code": d.code.value,
                    "severity": d.severity.value,
                    "root_id": d.root_id,
                    "path": d.path,
                    "message": d.message,
                }
                for d in self.diagnostics
            ],
            "summary": {
                "roots": self.summary.roots,
                "entries_examined": self.summary.entries_examined,
                "directories_visited": self.summary.directories_visited,
                "source_files": self.summary.source_files,
                "ignored_files": self.summary.ignored_files,
                "diagnostics": self.summary.diagnostics,
                "truncated": self.summary.truncated,
            },
        }
