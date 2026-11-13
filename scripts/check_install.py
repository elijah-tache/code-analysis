"""Verify that the editable install of ``code-analysis`` is usable from its virtualenv.

Run by ``make install`` (and ``make check-install``) with the virtualenv's interpreter
after ``pip install -e .`` (D-0040).  Development tooling only: it is not part of the
analyzer package and uses nothing but the standard library.

Three conditions must hold for exit status 0:

1. ``import code_analysis`` succeeds in a fresh ``python -I`` process (isolated mode
   ignores ``PYTHONPATH`` and the working directory, so only ``site-packages`` counts)
   and resolves to this repository's ``src/`` tree.
2. No ``site-packages/*.pth`` file carries the macOS ``UF_HIDDEN`` flag: CPython's
   ``site.py`` silently skips hidden ``.pth`` files, which makes an editable install
   inert.
3. The virtualenv has no ancestor managed by iCloud Drive or another File Provider
   sync domain.  iCloud Drive (including ``~/Desktop`` and ``~/Documents`` when
   "Desktop & Documents" sync is on) re-applies ``UF_HIDDEN`` to dot-paths a few seconds
   after they are written, so clearing the flag is not durable.

Otherwise the script prints the cause and the documented options and exits 1.
"""

from __future__ import annotations

import ctypes
import os
import stat
import subprocess
import sys
import sysconfig
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

__all__ = [
    "Report",
    "assess",
    "cloud_sync_provider",
    "hidden_pth_files",
    "import_location",
    "is_hidden",
    "main",
]

REPO_SRC: Final = Path(__file__).resolve().parent.parent / "src"

ICLOUD_XATTR_PREFIX: Final = "com.apple.icloud."
"""Set on ``~/Desktop``/``~/Documents`` by "Desktop & Documents" sync (observed: macOS 15)."""

FILE_PROVIDER_XATTR: Final = "com.apple.file-provider-domain-id"
"""Set on the root of any File Provider domain (iCloud Drive, Dropbox, OneDrive, ...)."""

MOBILE_DOCUMENTS: Final = ("Library", "Mobile Documents")
"""Path suffix of the iCloud Drive container itself."""

_UF_HIDDEN: Final = getattr(stat, "UF_HIDDEN", 0)
# A plain bool (not an inline ``sys.platform`` test) so mypy keeps every branch reachable.
_IS_DARWIN: Final[bool] = sys.platform == "darwin"

_OPTIONS: Final = (
    "Options (README.md, section 'Install'):",
    "  1. Move the repository (and its virtualenv) out of the cloud-synced folder.",
    "  2. Keep the repository where it is and create the virtualenv elsewhere:",
    "       make VENV=~/.venvs/code-analysis install",
    "     then pass the same VENV=... to every make target.",
    "  3. Leave it: the test suite never depends on the install (pytest puts src/ on",
    "     sys.path itself) and `PYTHONPATH=src python -m code_analysis` works, but",
    "     `import code_analysis` outside the repository and the `code-analysis` console",
    "     script stay broken.",
)


@dataclass(frozen=True, slots=True)
class Report:
    """Outcome of the check: ``ok`` plus the lines to show the user."""

    ok: bool
    lines: tuple[str, ...]


def is_hidden(path: Path) -> bool:
    """True when ``path`` carries the macOS ``UF_HIDDEN`` flag (always False elsewhere)."""
    flags = getattr(path.stat(), "st_flags", 0)
    return bool(flags & _UF_HIDDEN)


def hidden_pth_files(site_packages: Path) -> tuple[Path, ...]:
    """The ``.pth`` files in ``site_packages`` that CPython will skip because they are hidden."""
    return tuple(sorted(p for p in site_packages.glob("*.pth") if is_hidden(p)))


def _darwin_xattr_names(path: Path) -> frozenset[str]:
    """``listxattr(2)`` through ctypes: CPython exposes ``os.listxattr`` on Linux only."""
    libc = ctypes.CDLL(None, use_errno=True)
    listxattr = libc.listxattr
    listxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int]
    listxattr.restype = ctypes.c_ssize_t
    encoded = os.fsencode(path)
    size = int(listxattr(encoded, None, 0, 0))
    if size <= 0:  # no attributes, or an error such as ENOENT/EACCES
        return frozenset()
    buffer = ctypes.create_string_buffer(size)
    size = int(listxattr(encoded, buffer, size, 0))
    if size <= 0:
        return frozenset()
    names = buffer.raw[:size].split(b"\0")
    return frozenset(name.decode("utf-8", "replace") for name in names if name)


def _xattr_names(path: Path) -> frozenset[str]:
    listxattr = getattr(os, "listxattr", None)  # Linux
    if listxattr is not None:
        try:
            return frozenset(listxattr(path))
        except OSError:
            return frozenset()
    if _IS_DARWIN:
        return _darwin_xattr_names(path)
    return frozenset()  # Windows: no xattrs, and no iCloud dot-file hiding either


def cloud_sync_provider(path: Path) -> tuple[Path, str] | None:
    """The nearest ancestor of ``path`` (inclusive) managed by a cloud-sync service.

    Returns ``(ancestor, service name)`` or ``None``.  Checked from ``path`` upwards so the
    reported ancestor is the most specific one.
    """
    resolved = path.resolve()
    for candidate in (resolved, *resolved.parents):
        if candidate.parts[-2:] == MOBILE_DOCUMENTS:
            return candidate, "iCloud Drive"
        names = _xattr_names(candidate)
        if any(name.startswith(ICLOUD_XATTR_PREFIX) for name in names):
            return candidate, "iCloud Drive"
        if FILE_PROVIDER_XATTR in names:
            return candidate, "a File Provider cloud-sync service"
    return None


def import_location(python: Path) -> tuple[Path | None, str]:
    """Where ``import code_analysis`` resolves in a fresh ``python -I``, or ``(None, stderr)``."""
    run = subprocess.run(
        [str(python), "-I", "-c", "import code_analysis; print(code_analysis.__file__)"],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if run.returncode != 0:
        return None, run.stderr.strip()
    return Path(run.stdout.strip()), ""


def assess(
    *,
    python: Path,
    site_packages: Path,
    repo_src: Path,
    location: Path | None,
    import_error: str,
    hidden: Sequence[Path],
    provider: tuple[Path, str] | None,
) -> Report:
    """Pure assessment of the gathered facts (D-0040)."""
    lines: list[str] = []
    ok = True
    if location is None:
        ok = False
        lines.append(f"ERROR: `import code_analysis` fails in {python} (fresh `-I` interpreter):")
        lines.extend(f"    {line}" for line in import_error.splitlines() or ["(no output)"])
    elif not location.resolve().is_relative_to(repo_src.resolve()):
        ok = False
        lines.append(f"ERROR: `import code_analysis` resolves to {location}, not to {repo_src}")
    else:
        lines.append(f"import code_analysis -> {location}")
    if hidden:
        ok = False
        lines.append(
            "Cause: these .pth files carry the macOS UF_HIDDEN flag; CPython skips hidden "
            ".pth files, so the editable install is inert:"
        )
        lines.extend(f"    {path}" for path in hidden)
    if provider is not None:
        ok = False
        ancestor, service = provider
        lines.append(
            f"Cause: {site_packages} lives under {ancestor}, which is managed by {service}. "
            "iCloud Drive re-applies UF_HIDDEN to dot-paths (.venv/**, the editable .pth "
            "file, .git) seconds after they are written, so `chflags nohidden` does not "
            "last and the editable install is not durable (D-0040)."
        )
    if not ok:
        lines.extend(_OPTIONS)
    else:
        lines.append("editable install usable: no hidden .pth file, no cloud-synced ancestor")
    return Report(ok, tuple(lines))


def main(argv: Sequence[str] | None = None) -> int:
    """Gather the facts for the running interpreter, print the report, return 0 or 1."""
    if argv:  # No options exist; anything given is a usage error.
        print(f"usage: {Path(sys.argv[0]).name} (no arguments)", file=sys.stderr)
        return 2
    python = Path(sys.executable)
    site_packages = Path(sysconfig.get_paths()["purelib"])
    location, import_error = import_location(python)
    report = assess(
        python=python,
        site_packages=site_packages,
        repo_src=REPO_SRC,
        location=location,
        import_error=import_error,
        hidden=hidden_pth_files(site_packages),
        provider=cloud_sync_provider(site_packages),
    )
    print("\n".join(report.lines), file=sys.stdout if report.ok else sys.stderr)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
