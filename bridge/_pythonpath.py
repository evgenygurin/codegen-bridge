"""Sanitize ``PYTHONPATH`` / ``sys.path`` to prevent ABI mismatches.

**Problem:**  In hosted sandboxes the system-level ``PYTHONPATH`` may point to
site-packages compiled for a *different* Python minor version (e.g. 3.13)
while the project venv runs 3.12.  C-extension modules such as
``pydantic_core`` will fail to import when loaded from the wrong ABI.

**How it works:**

1. Detect the *running* interpreter's ``major.minor`` version.
2. Walk ``sys.path`` and strip any entry that contains a
   ``/pythonX.Y/`` segment where ``X.Y`` differs from the running version.
3. Evict the corresponding entries from ``sys.path_importer_cache`` so the
   import machinery cannot resolve modules through stale cached finders.
4. Evict any already-loaded modules in ``sys.modules`` whose ``__file__``
   resides under a removed path — this forces a clean re-import from the
   now-correct ``sys.path`` on next access.
5. Apply the same filter to the ``PYTHONPATH`` environment variable so
   child processes (e.g. pytest-xdist workers) do not re-inherit the
   contaminated paths.

The function is intentionally **import-free** beyond the stdlib so it can
run before *any* third-party code is loaded.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import MutableSequence

# Matches  /pythonX.Y/  anywhere in a path component.
_PYVER_RE = re.compile(r"/python(\d+\.\d+)/")


def _is_foreign(path: str, current_ver: str) -> bool:
    """Return True if *path* contains a pythonX.Y segment for a different version."""
    m = _PYVER_RE.search(path)
    return bool(m and m.group(1) != current_ver)


def sanitize_python_path(
    *,
    sys_path: MutableSequence[str] | None = None,
    env: dict[str, str] | None = None,
) -> list[str]:
    """Remove foreign-version site-packages from *sys_path* and *env*.

    Parameters
    ----------
    sys_path:
        The path list to sanitise **in-place**.  Defaults to ``sys.path``.
    env:
        The environment dict to sanitise **in-place**.  Defaults to
        ``os.environ``.

    Returns
    -------
    list[str]
        The paths that were removed from *sys_path* (useful for logging /
        testing).
    """
    if sys_path is None:
        sys_path = sys.path
    # os.environ is a Mapping[str, str] but not dict — cast is safe here.
    resolved_env: dict[str, str] = env if env is not None else os.environ  # type: ignore[assignment]

    current_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    removed: list[str] = []

    # --- clean sys.path in-place ---
    clean: list[str] = []
    for p in sys_path:
        if _is_foreign(p, current_ver):
            removed.append(p)
        else:
            clean.append(p)
    sys_path[:] = clean

    # --- evict stale finders from the import-machinery cache ---
    for p in removed:
        sys.path_importer_cache.pop(p, None)

    # --- evict already-loaded modules from contaminated paths ---
    #
    # Lightweight pure-Python packages (e.g. typing_extensions) may have
    # been imported by pytest during its own startup, *before* any conftest
    # runs.  If they were loaded from a foreign path, their cached module
    # object in sys.modules has the wrong content (different API surface or
    # ABI).  Evicting them forces a clean re-import from the now-correct
    # sys.path on next access.
    if removed and sys_path is sys.path:
        evict = [
            name
            for name, mod in sys.modules.items()
            if any((getattr(mod, "__file__", None) or "").startswith(bad) for bad in removed)
        ]
        for name in evict:
            del sys.modules[name]

    # --- clean PYTHONPATH env var ---
    raw = resolved_env.get("PYTHONPATH")
    if raw is not None:
        parts = [p for p in raw.split(os.pathsep) if p and not _is_foreign(p, current_ver)]
        if parts:
            resolved_env["PYTHONPATH"] = os.pathsep.join(parts)
        else:
            resolved_env.pop("PYTHONPATH", None)

    return removed
