"""Safe, deterministic directory walk (SPEC section 6 step 1).

Decisions: D-0015, D-0021, D-0022, D-0025 (symlinks), D-0026 (descriptor-relative traversal),
D-0038 (``O_BINARY``), D-0039 (wording of the symlink and fallback-mode guarantees).

Safety mechanics, in order of appearance:

* Directories are opened with ``O_DIRECTORY | O_NOFOLLOW`` *relative to the already-open
  descriptor of their parent* (``dir_fd``) and listed with ``os.scandir(fd)``.  Every
  type check uses ``follow_symlinks=False`` against that descriptor, so an entry that is
  swapped for a symlink after it was classified is refused (``ELOOP``/``ENOTDIR``), never
  followed.  At most ``max_depth + 1`` descriptors are open at once.
* A symlink is first matched against the exclusion patterns (nothing is resolved for an
  excluded link), then classified by ``os.path.realpath``, which performs only
  ``lstat``/``readlink`` metadata calls on the path components and whose result does not
  depend on whether the target exists.  Targets outside the root are rejected before
  anything is opened or ``stat``-ed through the link; in-root *directory* links are never
  traversed (D-0025), so canonical paths never depend on links.
* Non-regular files (FIFOs, sockets, devices) are rejected before any ``open`` so the
  walk cannot block on them.
* Files are opened with ``O_NOFOLLOW`` (``dir_fd``-relative) and re-checked with
  ``fstat``; at most ``cap + 1`` bytes are read, in chunks, solely to compute a SHA-256.
  Bytes are never retained, decoded, parsed, compiled or executed.
* The walk never calls ``exec``/``eval``/``compile``/``importlib``/``subprocess``.

On platforms without ``dir_fd`` support (``_FD_TRAVERSAL`` false) the same algorithm runs
on absolute paths and has **no directory-swap protection**: a directory replaced by a
symlink after it was classified is listed through the link.  Only the final-component
``O_NOFOLLOW`` check on files remains (known limitation, T029; D-0039).

Determinism: directory entries are processed in sorted name order, roots in
configured order, and the final result is sorted again by canonical path, so the
output (including a truncated one) depends only on the tree and the configuration.
"""

from __future__ import annotations

import errno
import hashlib
import keyword
import os
import stat
from dataclasses import dataclass, field
from typing import Final

from code_analysis.core.config import SymlinkPolicy, WorkspaceConfig, WorkspaceRoot
from code_analysis.core.patterns import PathPattern, PatternSet
from code_analysis.discovery.models import (
    Diagnostic,
    DiagnosticCode,
    DiscoveryResult,
    DiscoverySummary,
    PackageInfo,
    PackageKind,
    Severity,
    SourceFile,
    SourceKind,
)

__all__ = ["discover"]

_CHUNK_SIZE: Final = 64 * 1024
_O_NOFOLLOW: Final = getattr(os, "O_NOFOLLOW", 0)
_O_CLOEXEC: Final = getattr(os, "O_CLOEXEC", 0)
_O_BINARY: Final = getattr(os, "O_BINARY", 0)  # Windows: raw bytes, no newline translation (D-0038)
_OPEN_FLAGS: Final = os.O_RDONLY | _O_NOFOLLOW | _O_CLOEXEC | _O_BINARY
_DIR_FLAGS: Final = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | _O_NOFOLLOW | _O_CLOEXEC
_ROOT_PATH: Final = "."
_MISSING_ERRNOS: Final = frozenset({errno.ENOENT, errno.ENOTDIR, errno.ELOOP})

_FD_TRAVERSAL: Final = (
    os.open in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
    and os.scandir in os.supports_fd
    and hasattr(os, "O_DIRECTORY")
    and hasattr(os, "O_NOFOLLOW")
)
"""Whether directories can be traversed through descriptors (POSIX); see D-0026."""


class _TooLargeError(Exception):
    def __init__(self, observed_at_least: int) -> None:
        super().__init__(observed_at_least)
        self.observed_at_least = observed_at_least


class _NotRegularError(Exception):
    pass


@dataclass(slots=True)
class _DirFacts:
    """Layout facts gathered for one visited directory (mutable during the walk only)."""

    relative_path: str
    name: str
    parent: str | None
    has_source: bool = False
    has_init_py: bool = False
    has_init_pyi: bool = False
    has_package_child: bool = False


@dataclass(slots=True)
class _Frame:
    """One open directory on the DFS stack.

    ``fd`` is the directory descriptor (``None`` without ``dir_fd`` support).  ``pending``
    holds the names of child directories still to be entered, in *reverse* sorted order
    so that ``pop()`` yields them sorted.
    """

    abs_path: str
    relative_path: str
    depth: int
    fd: int | None
    pending: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _State:
    """Mutable accumulator shared across roots; converted to immutable records at the end."""

    config: WorkspaceConfig
    includes: PatternSet
    excludes: PatternSet
    files: list[tuple[int, SourceFile]] = field(default_factory=list)
    packages: list[tuple[int, PackageInfo]] = field(default_factory=list)
    diagnostics: list[tuple[int, Diagnostic]] = field(default_factory=list)
    entries_examined: int = 0
    directories_visited: int = 0
    ignored_files: int = 0
    truncated: bool = False

    def diag(
        self,
        root_index: int,
        root: WorkspaceRoot,
        code: DiagnosticCode,
        severity: Severity,
        path: str,
        message: str,
    ) -> None:
        self.diagnostics.append(
            (root_index, Diagnostic(code, severity, root.root_id, path or _ROOT_PATH, message))
        )


def _relative(parent: str, name: str) -> str:
    return name if not parent else f"{parent}/{name}"


def _valid_name(name: str) -> bool:
    """Names must be strictly UTF-8 encodable (no surrogate escapes from undecodable bytes)."""
    try:
        name.encode("utf-8", "strict")
    except UnicodeEncodeError:
        return False
    return "\x00" not in name


def _is_within(root_real: str, target_real: str) -> bool:
    root_n = os.path.normcase(root_real)
    target_n = os.path.normcase(target_real)
    return target_n == root_n or target_n.startswith(root_n.rstrip(os.sep) + os.sep)


def _error_text(exc: OSError) -> str:
    return exc.strerror or exc.__class__.__name__


def _hash_regular_file(path: str, cap: int, *, dir_fd: int | None = None) -> tuple[int, str]:
    """Return ``(size, sha256)`` for a regular file of at most ``cap`` bytes.

    Opens with ``O_NOFOLLOW`` (relative to ``dir_fd`` when given) and re-validates via
    ``fstat`` so that a path swapped for a symlink, FIFO or larger file between ``lstat``
    and ``open`` is still rejected.
    """
    fd = os.open(path, _OPEN_FLAGS, dir_fd=dir_fd)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise _NotRegularError
        if st.st_size > cap:
            raise _TooLargeError(st.st_size)
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(fd, min(_CHUNK_SIZE, cap + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > cap:
                raise _TooLargeError(total)
            digest.update(chunk)
        return total, digest.hexdigest()
    finally:
        os.close(fd)


def _source_kind(name: str) -> SourceKind:
    return SourceKind.PYI if name.endswith(".pyi") else SourceKind.PY


def _importable_name(name: str) -> bool:
    return name.isidentifier() and not keyword.iskeyword(name)


class _RootWalker:
    """Walks a single root.  Instances are short-lived; results flow into ``_State``."""

    def __init__(self, state: _State, root_index: int, root: WorkspaceRoot) -> None:
        self.state = state
        self.root_index = root_index
        self.root = root
        self.root_real = str(root.path)
        self.policy = state.config.safety.symlink_policy
        self.limits = state.config.safety.limits
        self.cap = state.config.safety.max_file_size_bytes
        self.dirs: dict[str, _DirFacts] = {}
        self.visit_order: list[str] = []

    # -- diagnostics helpers -------------------------------------------------------------

    def _diag(self, code: DiagnosticCode, severity: Severity, path: str, message: str) -> None:
        self.state.diag(self.root_index, self.root, code, severity, path, message)

    def _limit(self, path: str, message: str) -> None:
        self._diag(DiagnosticCode.LIMIT_REACHED, Severity.ERROR, path, message)
        self.state.truncated = True

    def _rel_to_root(self, abs_real: str) -> str:
        """Root-relative POSIX form of an in-root real path (``"."`` for the root)."""
        rel = os.path.relpath(abs_real, self.root_real)
        return _ROOT_PATH if rel == os.curdir else rel.replace(os.sep, "/")

    # -- directory descriptors ------------------------------------------------------------

    @staticmethod
    def _open_dir(abs_path: str, name: str, parent_fd: int | None) -> int | None:
        """Open a directory without following a final-component link; ``None`` without fds."""
        if not _FD_TRAVERSAL:
            return None
        if parent_fd is None:
            return os.open(abs_path, _DIR_FLAGS)
        return os.open(name, _DIR_FLAGS, dir_fd=parent_fd)

    @staticmethod
    def _close(frame: _Frame) -> None:
        if frame.fd is not None:
            os.close(frame.fd)
            frame.fd = None

    # -- walk ---------------------------------------------------------------------------

    def run(self) -> None:
        try:
            if not os.path.isdir(self.root_real):
                raise NotADirectoryError(errno.ENOTDIR, "not a directory", self.root_real)
            root_fd = self._open_dir(self.root_real, "", None)
        except OSError as exc:
            self._diag(
                DiagnosticCode.ROOT_UNAVAILABLE,
                Severity.ERROR,
                _ROOT_PATH,
                f"root {self.root.root_id!r} at {self.root_real!r} is not an accessible "
                f"directory ({_error_text(exc)})",
            )
            return
        self.dirs[""] = _DirFacts(relative_path="", name=self.root.path.name, parent=None)
        self.visit_order.append("")
        stack: list[_Frame] = [_Frame(self.root_real, "", 0, root_fd)]
        try:
            self._scan_directory(stack[-1])
            while stack and not self.state.truncated:
                frame = stack[-1]
                if not frame.pending:
                    self._close(stack.pop())
                    continue
                self._descend(frame, frame.pending.pop(), stack)
        finally:
            for frame in stack:
                self._close(frame)
        self._emit_packages()

    def _descend(self, parent: _Frame, name: str, stack: list[_Frame]) -> None:
        child_abs = os.path.join(parent.abs_path, name)
        child_rel = _relative(parent.relative_path, name)
        try:
            fd = self._open_dir(child_abs, name, parent.fd)
        except OSError as exc:
            # Includes ELOOP/ENOTDIR when the directory was swapped for a link meanwhile.
            self._diag(
                DiagnosticCode.UNREADABLE,
                Severity.WARNING,
                child_rel,
                f"directory could not be opened: {_error_text(exc)}",
            )
            return
        child = _Frame(child_abs, child_rel, parent.depth + 1, fd)
        stack.append(child)  # pushed before scanning so the descriptor is always closed
        self._scan_directory(child)

    def _scan_directory(self, frame: _Frame) -> None:
        self.state.directories_visited += 1
        try:
            with os.scandir(frame.fd if frame.fd is not None else frame.abs_path) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError as exc:
            self._diag(
                DiagnosticCode.UNREADABLE,
                Severity.WARNING,
                frame.relative_path,
                f"directory could not be listed: {_error_text(exc)}",
            )
            return
        child_dirs: list[str] = []
        for entry in entries:
            if self.state.entries_examined >= self.limits.max_entries:
                self._limit(
                    _relative(frame.relative_path, entry.name),
                    f"max_entries={self.limits.max_entries} reached; discovery truncated",
                )
                break
            self.state.entries_examined += 1
            rel = _relative(frame.relative_path, entry.name)
            try:
                self._classify_entry(entry, rel, frame, child_dirs)
            except OSError as exc:
                self._diag(
                    DiagnosticCode.UNREADABLE,
                    Severity.WARNING,
                    rel,
                    f"entry could not be examined: {_error_text(exc)}",
                )
            if self.state.truncated:
                break
        child_dirs.reverse()
        frame.pending = child_dirs

    def _classify_entry(
        self, entry: os.DirEntry[str], rel: str, frame: _Frame, child_dirs: list[str]
    ) -> None:
        # With scandir(fd), entry.path is the bare name and the type checks are
        # descriptor-relative; without fds entry.path is absolute and frame.fd is None.
        if not _valid_name(entry.name):
            self._diag(
                DiagnosticCode.INVALID_FILENAME,
                Severity.WARNING,
                rel,
                "entry name is not valid UTF-8 and was skipped",
            )
        elif entry.is_symlink():
            self._handle_symlink(entry, rel, frame)
        elif entry.is_dir(follow_symlinks=False):
            self._consider_directory(entry.name, rel, frame, child_dirs)
        elif entry.is_file(follow_symlinks=False):
            self._consider_file(rel, frame.relative_path, path=entry.path, dir_fd=frame.fd)
        elif not self.state.includes.matches(rel, is_dir=False):
            self.state.ignored_files += 1  # a socket/FIFO we would never read anyway
        else:
            self._diag(
                DiagnosticCode.NOT_REGULAR_FILE,
                Severity.WARNING,
                rel,
                "entry is neither a regular file nor a directory",
            )

    def _consider_directory(
        self, name: str, rel: str, parent: _Frame, child_dirs: list[str]
    ) -> None:
        matched = self.state.excludes.first_match(rel, is_dir=True)
        if matched is not None:
            self._diag(
                DiagnosticCode.EXCLUDED_BY_PATTERN,
                Severity.INFO,
                rel,
                f"directory excluded by pattern {matched.source!r}; subtree not visited",
            )
            return
        depth = parent.depth + 1
        if depth > self.limits.max_depth:
            self._diag(
                DiagnosticCode.MAX_DEPTH_EXCEEDED,
                Severity.WARNING,
                rel,
                f"directory nested deeper than max_depth={self.limits.max_depth}; not entered",
            )
            return
        self.dirs[rel] = _DirFacts(relative_path=rel, name=name, parent=parent.relative_path)
        self.visit_order.append(rel)
        child_dirs.append(name)

    def _consider_file(self, rel: str, parent_rel: str, *, path: str, dir_fd: int | None) -> None:
        """Apply include/exclude/limit filters, then hash ``path`` under the logical ``rel``."""
        if not self.state.includes.matches(rel, is_dir=False):
            self.state.ignored_files += 1
            return
        matched = self.state.excludes.first_match(rel, is_dir=False)
        if matched is not None:
            self._diag(
                DiagnosticCode.EXCLUDED_BY_PATTERN,
                Severity.INFO,
                rel,
                f"file excluded by pattern {matched.source!r}",
            )
            return
        if len(self.state.files) >= self.limits.max_files:
            self._limit(rel, f"max_files={self.limits.max_files} reached; discovery truncated")
            return
        self._hash_file(rel, parent_rel, path, dir_fd)

    def _hash_file(self, rel: str, parent_rel: str, path: str, dir_fd: int | None) -> None:
        # First size/type check from lstat (cheap); the authoritative check happens on the
        # open descriptor inside _hash_regular_file.
        st = os.stat(path, dir_fd=dir_fd, follow_symlinks=False)
        if not stat.S_ISREG(st.st_mode):
            self._not_regular(rel, "entry is not a regular file (device, socket or FIFO)")
            return
        if st.st_size > self.cap:
            self._too_large(rel, st.st_size)
            return
        try:
            size, digest = _hash_regular_file(path, self.cap, dir_fd=dir_fd)
        except _TooLargeError as exc:
            self._too_large(rel, exc.observed_at_least)
            return
        except _NotRegularError:
            self._not_regular(rel, "entry changed to a non-regular file before it could be read")
            return
        except OSError as exc:
            self._diag(
                DiagnosticCode.UNREADABLE,
                Severity.WARNING,
                rel,
                f"file could not be read: {_error_text(exc)}",
            )
            return
        self._record_source(rel, parent_rel, size, digest)

    def _record_source(self, rel: str, parent_rel: str, size: int, digest: str) -> None:
        name = rel.rsplit("/", 1)[-1]
        self.state.files.append(
            (
                self.root_index,
                SourceFile(
                    root_id=self.root.root_id,
                    relative_path=rel,
                    kind=_source_kind(name),
                    size_bytes=size,
                    sha256=digest,
                ),
            )
        )
        facts = self.dirs[parent_rel]
        facts.has_source = True
        if name == "__init__.py":
            facts.has_init_py = True
        elif name == "__init__.pyi":
            facts.has_init_pyi = True

    def _too_large(self, rel: str, observed: int) -> None:
        self._diag(
            DiagnosticCode.FILE_TOO_LARGE,
            Severity.WARNING,
            rel,
            f"file size {observed} bytes exceeds max_file_size_bytes={self.cap}; not hashed",
        )

    def _not_regular(self, rel: str, message: str) -> None:
        self._diag(DiagnosticCode.NOT_REGULAR_FILE, Severity.WARNING, rel, f"{message}; not opened")

    # -- symlinks (D-0025) ----------------------------------------------------------------

    def _handle_symlink(self, entry: os.DirEntry[str], rel: str, frame: _Frame) -> None:
        # Exclusions apply to the link's own path before anything is resolved.  The type
        # of an unresolved link is unknown, so directory-only patterns match it as well.
        matched = self.state.excludes.first_match(rel, is_dir=True)
        if matched is not None:
            self._diag(
                DiagnosticCode.EXCLUDED_BY_PATTERN,
                Severity.INFO,
                rel,
                f"symlink excluded by pattern {matched.source!r}; target not resolved",
            )
            return
        # realpath performs only lstat/readlink metadata calls on the path components; its
        # result does not depend on whether the target exists, and nothing is opened or
        # stat-ed through the link before the within-root check below (D-0039).
        target_real = os.path.realpath(os.path.join(frame.abs_path, entry.name))
        if not _is_within(self.root_real, target_real):
            self._diag(
                DiagnosticCode.SYMLINK_ESCAPES_ROOT,
                Severity.WARNING,
                rel,
                f"symlink resolves outside root {self.root.root_id!r}; rejected and not followed",
            )
            return
        try:
            target_st = os.stat(target_real)  # in-root target only
        except OSError as exc:
            if exc.errno not in _MISSING_ERRNOS:
                raise
            self._diag(
                DiagnosticCode.SYMLINK_TARGET_MISSING,
                Severity.WARNING,
                rel,
                f"symlink target does not resolve ({_error_text(exc)}); not followed",
            )
            return
        if self.policy is SymlinkPolicy.NEVER:
            self._diag(
                DiagnosticCode.SYMLINK_NOT_FOLLOWED,
                Severity.INFO,
                rel,
                "symlink not followed (symlink_policy=never)",
            )
            return
        target_rel = self._rel_to_root(target_real)
        if stat.S_ISDIR(target_st.st_mode):
            self._report_directory_link(rel, frame, target_real, target_rel)
            return
        excluded = self._target_excluded(target_rel)
        if excluded is not None:
            self._diag(
                DiagnosticCode.EXCLUDED_BY_PATTERN,
                Severity.INFO,
                rel,
                f"symlink target {target_rel!r} is excluded by pattern {excluded.source!r}; "
                "not followed",
            )
            return
        # Hash the resolved in-root file (no symlink components remain) under the link's
        # logical path; the real file is still reported under its own path.
        self._consider_file(rel, frame.relative_path, path=target_real, dir_fd=None)

    def _report_directory_link(
        self, rel: str, frame: _Frame, target_real: str, target_rel: str
    ) -> None:
        """Directory links are never traversed: canonical paths must not depend on links."""
        if _is_within(target_real, frame.abs_path):
            self._diag(
                DiagnosticCode.SYMLINK_CYCLE,
                Severity.INFO,
                rel,
                f"symlink points at its own ancestor directory {target_rel!r}; not followed",
            )
        else:
            self._diag(
                DiagnosticCode.SYMLINK_ALIAS,
                Severity.INFO,
                rel,
                f"symlink is an alias of directory {target_rel!r}, which is reported under "
                "its own path; not followed",
            )

    def _target_excluded(self, target_rel: str) -> PathPattern | None:
        """First exclusion pattern hit by the target file or any of its ancestor directories."""
        parts = target_rel.split("/")
        for index in range(1, len(parts)):
            matched = self.state.excludes.first_match("/".join(parts[:index]), is_dir=True)
            if matched is not None:
                return matched
        return self.state.excludes.first_match(target_rel, is_dir=False)

    # -- packages -----------------------------------------------------------------------

    def _emit_packages(self) -> None:
        # Children were appended after their parents, so reverse order is bottom-up.
        for rel in reversed(self.visit_order):
            facts = self.dirs[rel]
            is_package_like = facts.has_source or facts.has_package_child
            if not is_package_like:
                continue
            if facts.parent is not None:
                self.dirs[facts.parent].has_package_child = True
            if rel == "" and not facts.has_init_py:
                # The root itself is a search-path candidate, not a package (D-0022).
                continue
            self.state.packages.append(
                (
                    self.root_index,
                    PackageInfo(
                        root_id=self.root.root_id,
                        relative_path=rel or _ROOT_PATH,
                        kind=PackageKind.REGULAR
                        if facts.has_init_py
                        else PackageKind.NAMESPACE_CANDIDATE,
                        has_init_py=facts.has_init_py,
                        has_init_pyi=facts.has_init_pyi,
                        importable_name=_importable_name(facts.name),
                    ),
                )
            )


def discover(config: WorkspaceConfig) -> DiscoveryResult:
    """Discover Python sources under every root of ``config`` without executing anything.

    The result is sorted by (root order, relative path) and is identical for identical
    trees and configurations.  Skipped or rejected entries are reported as diagnostics;
    files outside the include patterns are only counted (see ``DiscoverySummary``).
    """
    state = _State(
        config=config,
        includes=config.compiled_includes(),
        excludes=config.compiled_excludes(),
    )
    for index, root in enumerate(config.roots):
        if state.truncated:
            state.diag(
                index,
                root,
                DiagnosticCode.LIMIT_REACHED,
                Severity.ERROR,
                _ROOT_PATH,
                "root not visited because a traversal limit was reached earlier",
            )
            continue
        _RootWalker(state, index, root).run()

    files = tuple(
        f for _, f in sorted(state.files, key=lambda item: (item[0], item[1].relative_path))
    )
    packages = tuple(
        p for _, p in sorted(state.packages, key=lambda item: (item[0], item[1].relative_path))
    )
    diagnostics = tuple(
        d
        for _, d in sorted(
            state.diagnostics,
            key=lambda item: (item[0], item[1].path, item[1].code.value, item[1].message),
        )
    )
    summary = DiscoverySummary(
        roots=len(config.roots),
        entries_examined=state.entries_examined,
        directories_visited=state.directories_visited,
        source_files=len(files),
        ignored_files=state.ignored_files,
        diagnostics=len(diagnostics),
        truncated=state.truncated,
    )
    return DiscoveryResult(files=files, packages=packages, diagnostics=diagnostics, summary=summary)
