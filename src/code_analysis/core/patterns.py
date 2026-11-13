"""gitignore-style path pattern matching implemented with the standard library.

Semantics (D-0019; see ``docs/safety-policy.md`` for the user-facing description):

* Patterns are matched against the root-relative POSIX path of an entry
  (forward slashes, no leading ``./``).
* A pattern that contains ``/`` (other than a trailing one) is *anchored* at the
  root; a leading ``/`` is optional.  A pattern without ``/`` matches the basename
  of an entry at any depth.
* ``*`` matches any run of characters within one path segment, ``?`` exactly one
  such character, ``[...]`` a character class, and ``**`` zero or more whole
  segments.
* A trailing ``/`` restricts the pattern to directories.
* Negation (``!``), backslash escaping, comments and absolute patterns are not
  supported and are rejected by :func:`compile_pattern` with :class:`PatternError`.

Matching is case-sensitive on every platform so that results are deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

__all__ = ["PathPattern", "PatternError", "PatternSet", "compile_pattern"]


class PatternError(ValueError):
    """Raised for a pattern that uses unsupported or malformed syntax."""


# Characters that have no special meaning but must not be mangled by re.escape.
_SEGMENT: Final = r"[^/]*"
_SINGLE: Final = r"[^/]"


def _translate_segment(segment: str, pattern: str) -> str:
    """Translate one path segment (no ``/`` inside) of a glob into a regex fragment."""
    out: list[str] = []
    i = 0
    n = len(segment)
    while i < n:
        ch = segment[i]
        if ch == "*":
            # Collapse runs of '*' inside a segment; '**' is only special as a whole segment.
            while i < n and segment[i] == "*":
                i += 1
            out.append(_SEGMENT)
            continue
        if ch == "?":
            out.append(_SINGLE)
        elif ch == "[":
            close = segment.find("]", i + 1)
            if close == -1:
                raise PatternError(f"unterminated character class in pattern {pattern!r}")
            body = segment[i + 1 : close]
            if body.startswith("!"):
                body = "^" + body[1:]
            # Escape everything except a leading '^' and the range operator.
            escaped = "".join(
                c if (c == "^" and k == 0) or c == "-" else re.escape(c) for k, c in enumerate(body)
            )
            if "/" in body:
                raise PatternError(f"character class may not contain '/' in pattern {pattern!r}")
            out.append(f"[{escaped}]")
            i = close
        elif ch == "\\":
            raise PatternError(f"backslash escaping is not supported in pattern {pattern!r}")
        else:
            out.append(re.escape(ch))
        i += 1
    return "".join(out)


def _validate(pattern: str) -> None:
    if not isinstance(pattern, str) or not pattern:
        raise PatternError("pattern must be a non-empty string")
    if pattern.startswith("!"):
        raise PatternError(f"negation is not supported in pattern {pattern!r}")
    if pattern.startswith("#"):
        raise PatternError(f"comment lines are not supported as patterns: {pattern!r}")
    if pattern != pattern.strip():
        raise PatternError(f"pattern has leading/trailing whitespace: {pattern!r}")
    if "\\" in pattern:
        raise PatternError(f"backslash escaping is not supported in pattern {pattern!r}")
    if re.match(r"^[A-Za-z]:[/\\]", pattern) or pattern.startswith("//"):
        raise PatternError(f"absolute patterns are not allowed: {pattern!r}")
    body = pattern[1:] if pattern.startswith("/") else pattern
    segments = body.rstrip("/").split("/")
    if any(seg in ("..", ".") for seg in segments):
        raise PatternError(f"'.' and '..' segments are not allowed in pattern {pattern!r}")
    if any(seg == "" for seg in segments):
        raise PatternError(f"empty path segment ('//') in pattern {pattern!r}")


@dataclass(frozen=True, slots=True)
class PathPattern:
    """A compiled pattern.  ``source`` is the original text, kept for diagnostics."""

    source: str
    anchored: bool
    directory_only: bool
    _regex: re.Pattern[str]

    def matches(self, relative_path: str, *, is_dir: bool) -> bool:
        """Return whether ``relative_path`` (root-relative POSIX) matches this pattern."""
        if self.directory_only and not is_dir:
            return False
        subject = relative_path if self.anchored else relative_path.rsplit("/", 1)[-1]
        return self._regex.fullmatch(subject) is not None


def compile_pattern(pattern: str) -> PathPattern:
    """Compile ``pattern`` into a :class:`PathPattern`, raising :class:`PatternError`."""
    _validate(pattern)
    directory_only = pattern.endswith("/")
    body = pattern.rstrip("/")
    # A leading '/' anchors even a single-segment pattern (e.g. '/build' matches only at root).
    anchored = body.startswith("/") or "/" in body
    if body.startswith("/"):
        body = body[1:]
    segments = body.split("/")
    parts: list[str] = []
    for index, segment in enumerate(segments):
        last = index == len(segments) - 1
        if segment == "**":
            # '**/' at the start or middle: zero or more leading segments;
            # '/**' at the end: anything below (but not the empty remainder).
            parts.append("(?:.*/)?" if not last else "(?:.*)")
            continue
        fragment = _translate_segment(segment, pattern)
        parts.append(fragment if last else fragment + "/")
    try:
        regex = re.compile("".join(parts))
    except re.error as exc:
        # e.g. an empty class "[]" or a reversed range "[z-a]" survive _translate_segment.
        raise PatternError(f"malformed character class in pattern {pattern!r}: {exc}") from exc
    return PathPattern(
        source=pattern, anchored=anchored, directory_only=directory_only, _regex=regex
    )


@dataclass(frozen=True, slots=True)
class PatternSet:
    """An ordered, immutable collection of compiled patterns."""

    patterns: tuple[PathPattern, ...]

    @classmethod
    def compile(cls, patterns: tuple[str, ...]) -> PatternSet:
        return cls(tuple(compile_pattern(p) for p in patterns))

    def first_match(self, relative_path: str, *, is_dir: bool) -> PathPattern | None:
        """Return the first pattern matching ``relative_path``, or ``None``."""
        for pattern in self.patterns:
            if pattern.matches(relative_path, is_dir=is_dir):
                return pattern
        return None

    def matches(self, relative_path: str, *, is_dir: bool) -> bool:
        return self.first_match(relative_path, is_dir=is_dir) is not None
