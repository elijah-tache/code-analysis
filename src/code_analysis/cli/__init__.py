"""Command-line interface (SPEC section 8).

T003 scaffolding only (D-0036): ``main`` understands ``--version`` and ``--help``.  The
required commands (``index``, ``status``, ``search``, ``symbol``, ``neighbors``, ``path``,
``impact``, ``compat``, ``diagnostics``, ``diff``, ``explain``, ``export``), ``--json``
output and the full exit-code table arrive with T024.

The CLI sits in the *interfaces* layer (D-0028): it may use the public API of the
query layer (``code_analysis.graph.query``, ``impact``, ``snapshots``) and nothing
private from any other package.
"""

from code_analysis.cli.app import ExitCode, build_parser, main

__all__ = ["ExitCode", "build_parser", "main"]
