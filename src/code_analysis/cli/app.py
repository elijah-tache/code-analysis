"""``argparse``-based entry point (D-0036).  Named ``app`` so the module never shadows
the ``main`` function re-exported by the package.

``main`` is the console-script target (``code-analysis = code_analysis.cli:main``) and
is also used by ``python -m code_analysis``.  It returns an exit code instead of calling
``sys.exit`` so it can be tested in-process.
"""

from __future__ import annotations

import argparse
import enum
from collections.abc import Sequence
from typing import Final

from code_analysis import __version__

__all__ = ["PROGRAM", "ExitCode", "build_parser", "main"]

PROGRAM: Final = "code-analysis"

_DESCRIPTION: Final = (
    "Deterministic, offline, non-executing Python code intelligence engine (Stage 1). "
    "Analyzed code is never imported or executed."
)
_EPILOG: Final = (
    "Commands (index, status, search, symbol, neighbors, path, impact, compat, "
    "diagnostics, diff, explain, export) are not implemented yet (T024)."
)


class ExitCode(enum.IntEnum):
    """Process exit codes.  T024 extends this table; new codes are never ad hoc."""

    OK = 0
    USAGE = 2
    """Invalid arguments (the ``argparse`` convention)."""


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser.  Subcommands are registered here by T024."""
    parser = argparse.ArgumentParser(
        prog=PROGRAM, description=_DESCRIPTION, epilog=_EPILOG, allow_abbrev=False
    )
    parser.add_argument("--version", action="version", version=f"{PROGRAM} {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI on ``argv`` (defaults to ``sys.argv[1:]``) and return the exit code."""
    parser = build_parser()
    try:
        parser.parse_args(argv if argv is None else list(argv))
    except SystemExit as exc:
        # argparse exits 0 after --help/--version and 2 after a usage error.
        if exc.code is None:
            return int(ExitCode.OK)
        return exc.code if isinstance(exc.code, int) else int(ExitCode.USAGE)
    # No subcommands exist yet, so a bare invocation is a request for help.
    parser.print_help()
    return int(ExitCode.OK)
