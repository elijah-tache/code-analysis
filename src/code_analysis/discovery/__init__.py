"""Safe, deterministic source file discovery (SPEC.md section 6 step 1).

Public API: :func:`discover` plus the immutable result records in :mod:`.models`.
"""

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
from code_analysis.discovery.walk import discover

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
    "discover",
]
