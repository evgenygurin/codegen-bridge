"""Reusable ToolAnnotations presets for MCP tools.

Each preset encodes a common safety profile so individual ``@mcp.tool()``
decorators stay concise while providing accurate hints to the client.

Profiles
--------
READ_ONLY        Pure read from external API — safe to auto-approve / retry.
READ_ONLY_LOCAL  Pure read from local state — no network at all.
CREATES          Creates a new resource externally — not idempotent.
MUTATES          Idempotent update to an existing resource.
MUTATES_LOCAL    Idempotent update to local-only state.
DESTRUCTIVE      Irreversible or hard-to-undo mutation (stop, ban, delete, close).
"""

from __future__ import annotations

from mcp.types import ToolAnnotations

__all__ = [
    "CREATES",
    "DESTRUCTIVE",
    "MUTATES",
    "MUTATES_LOCAL",
    "READ_ONLY",
    "READ_ONLY_LOCAL",
]

# ── Pure reads ──────────────────────────────────────────────────

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
"""Fetches data from an external API — safe to retry, no side effects."""

READ_ONLY_LOCAL = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
"""Reads from local state (settings, registry) — no network call."""

# ── Writes ──────────────────────────────────────────────────────

CREATES = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)
"""Creates a new external resource (agent run, token, execution context)."""

MUTATES = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
"""Idempotent update to an existing external resource."""

MUTATES_LOCAL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
"""Idempotent update to local-only state (settings file)."""

DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=True,
)
"""Irreversible or hard-to-undo mutation (stop, ban, delete, revoke)."""
