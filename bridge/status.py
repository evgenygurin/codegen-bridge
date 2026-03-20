"""Status normalization for Codegen API responses.

The Codegen API returns run statuses in varying cases and forms
(e.g. ``"COMPLETE"`` vs ``"completed"``, ``"ERROR"`` vs ``"failed"``).
This module provides a single normalization function and a canonical
set of terminal statuses so that comparisons are consistent everywhere.
"""

from __future__ import annotations

# Canonical terminal statuses (always lowercase)
TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "failed", "error"})

# Map of non-canonical API status values to canonical forms.
# Only entries that differ from a simple ``.lower()`` need to be listed.
_STATUS_ALIASES: dict[str, str] = {
    "complete": "completed",
}


def normalize_status(status: str | None) -> str:
    """Normalize an API status string to a canonical lowercase form.

    Handles:
    - ``None`` → ``"unknown"``
    - Upper-case variants (``"COMPLETE"`` → ``"completed"``)
    - Alias mapping (``"complete"`` → ``"completed"``)

    >>> normalize_status("COMPLETE")
    'completed'
    >>> normalize_status("error")
    'error'
    >>> normalize_status(None)
    'unknown'
    """
    if status is None:
        return "unknown"
    lower = status.lower()
    return _STATUS_ALIASES.get(lower, lower)


def is_terminal(status: str | None) -> bool:
    """Return True if the status represents a terminal (finished) run state."""
    return normalize_status(status) in TERMINAL_STATUSES
