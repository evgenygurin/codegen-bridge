"""Reusable elicitation helpers for interactive user prompts.

Provides high-level wrappers around ``ctx.elicit()`` that handle:
- Graceful degradation when the client doesn't support elicitation
- Consistent logging of elicitation outcomes
- Normalization of accept/decline/cancel to simple return values

All helpers fall through silently when elicitation is unsupported,
returning a configurable default so tools remain fully functional
for programmatic callers and non-interactive clients.

Usage::

    from bridge.elicitation import confirm_action, select_choice

    @mcp.tool
    async def stop_run(run_id: int, ctx: Context = CurrentContext()) -> str:
        if not await confirm_action(ctx, f"Stop agent run {run_id}?"):
            return "Cancelled by user"
        ...
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastmcp.server.context import Context
from fastmcp.server.elicitation import (
    AcceptedElicitation,
)
from mcp.shared.exceptions import McpError

logger = logging.getLogger("bridge.elicitation")


# ── Elicitation schemas ──────────────────────────────────────


@dataclass
class StopConfirmation:
    """Schema for stop-run confirmation prompt."""

    confirm: bool


@dataclass
class RepoConfirmation:
    """Schema for repository confirmation prompt."""

    confirm: bool


# ── Helper functions ─────────────────────────────────────────


async def confirm_action(
    ctx: Context,
    message: str,
    *,
    default: bool = True,
) -> bool:
    """Ask the user for a boolean confirmation.

    Args:
        ctx: MCP tool context (must have ``elicit`` method).
        message: Human-readable prompt shown to the user.
        default: Value returned when the client doesn't support
            elicitation or the user declines/cancels.

    Returns:
        ``True`` if the user explicitly confirms, ``False`` if
        declined/cancelled, or *default* if elicitation is
        unavailable.
    """
    try:
        result = await ctx.elicit(message, bool)  # type: ignore[arg-type]
    except McpError:
        logger.debug("Elicitation not supported; using default=%s", default)
        return default
    except Exception:
        logger.debug("Elicitation failed; using default=%s", default, exc_info=True)
        return default

    if isinstance(result, AcceptedElicitation):
        confirmed: bool = result.data  # type: ignore[assignment]
        await ctx.info(f"User {'confirmed' if confirmed else 'rejected'}: {message}")
        return confirmed

    # Declined or cancelled
    await ctx.info(f"User {result.action}: {message}")
    return False


async def confirm_with_schema[T](
    ctx: Context,
    message: str,
    schema: type[T],
    *,
    default_on_unsupported: T | None = None,
) -> T | None:
    """Ask the user for structured confirmation using a dataclass schema.

    Args:
        ctx: MCP tool context.
        message: Human-readable prompt shown to the user.
        schema: A dataclass type defining the elicitation form.
        default_on_unsupported: Value returned when elicitation
            is not supported by the client.

    Returns:
        The populated schema instance on accept, or
        *default_on_unsupported* on decline/cancel/unsupported.
    """
    try:
        result = await ctx.elicit(message, schema)  # type: ignore[arg-type]
    except McpError:
        logger.debug("Elicitation not supported; returning default")
        return default_on_unsupported
    except Exception:
        logger.debug("Elicitation failed; returning default", exc_info=True)
        return default_on_unsupported

    if isinstance(result, AcceptedElicitation):
        return result.data  # type: ignore[return-value]

    await ctx.info(f"User {result.action}: {message}")
    return None


async def select_choice(
    ctx: Context,
    message: str,
    choices: list[str],
    *,
    default: str | None = None,
) -> str | None:
    """Ask the user to select one option from a list.

    Args:
        ctx: MCP tool context.
        message: Human-readable prompt shown to the user.
        choices: List of valid string options.
        default: Value returned when elicitation is unavailable
            or the user declines/cancels.

    Returns:
        The selected choice string, or *default* on
        decline/cancel/unsupported.
    """
    if not choices:
        return default

    try:
        result = await ctx.elicit(message, choices)  # type: ignore[arg-type]
    except McpError:
        logger.debug("Elicitation not supported; using default=%s", default)
        return default
    except Exception:
        logger.debug("Elicitation failed; using default=%s", default, exc_info=True)
        return default

    if isinstance(result, AcceptedElicitation):
        selected: str = result.data  # type: ignore[assignment]
        await ctx.info(f"User selected: {selected}")
        return selected

    await ctx.info(f"User {result.action}: {message}")
    return None
