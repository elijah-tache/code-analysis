"""Syntax layer (planned; SPEC section 6 step 2): the parser boundary.

This is the only layer that turns source bytes into syntax trees.  It will parse with
the standard-library ``ast`` module (parse-only; never ``compile`` for execution,
D-0015), keep source spans, and emit diagnostics for parse failures and grammar
mismatches instead of omitting files silently (SPEC section 3.2).

The parser strategy for the 3.8-3.14 syntax range (D-0002) is decided by T002 and the
implementation belongs to T006.  Nothing is implemented here yet; the package exists to
mark the boundary in the layer map (D-0028, ``docs/architecture.md``).
"""
