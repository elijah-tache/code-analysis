"""code_analysis: deterministic, offline, non-executing Python code intelligence.

Stage 1 safety contract (SPEC.md section 3, D-0015): this package parses and reads
repository contents as untrusted bytes. It never imports, executes, compiles for
execution, installs or builds analyzed code, and performs no network I/O.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
