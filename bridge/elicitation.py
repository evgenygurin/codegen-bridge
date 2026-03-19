"""Reusable elicitation helpers for interactive user prompts.

Provides high-level wrappers around ``ctx.elicit()`` that handle:
- Graceful degradation when the client doesn't support elicitation
- Consistent logging of elicitation outcomes
- Normalization of accept/decline/cancel to simple return values
- Pydantic BaseModel and dataclass schemas for structured elicitation
- Multi-select elicitation via ``select_multiple()``

All helpers fall through silently when elicitation is unsupported,
returning a configurable default so tools remain fully functional
for programmatic callers and non-interactive clients.

Usage::

    from bridge.elicitation import confirm_action, select_choice, select_multiple

    @mcp.tool
    async def stop_run(run_id: int, ctx: Context = CurrentContext()) -> str:
        if not await confirm_action(ctx, f"Stop agent run {run_id}?"):
            return "Cancelled by user"
        ...

    @mcp.tool
    async def pick_repos(ctx: Context = CurrentContext()) -> str:
        selected = await select_multiple(ctx, "Which repos?", ["a", "b", "c"])
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
    except (NotImplementedError, AttributeError, RuntimeError, TypeError):
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
    """Ask the user for structured confirmation using a schema.

    Supports both dataclass and Pydantic ``BaseModel`` types as the
    *schema* argument.  FastMCP's ``ctx.elicit()`` natively handles
    both, so either can be passed transparently.

    Args:
        ctx: MCP tool context.
        message: Human-readable prompt shown to the user.
        schema: A dataclass **or** Pydantic BaseModel type defining
            the elicitation form fields.
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
    except (NotImplementedError, AttributeError, RuntimeError, TypeError):
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
    except (NotImplementedError, AttributeError, RuntimeError, TypeError):
        logger.debug("Elicitation failed; using default=%s", default, exc_info=True)
        return default

    if isinstance(result, AcceptedElicitation):
        selected: str = result.data  # type: ignore[assignment]
        await ctx.info(f"User selected: {selected}")
        return selected

    await ctx.info(f"User {result.action}: {message}")
    return None


# ── Multi-select schema ─────────────────────────────────────


@dataclass
class MultiSelectSchema:
    """Schema for multi-select elicitation.

    The ``selected`` field is a comma-separated string of chosen items.
    MCP elicitation schemas only support primitive field types, so a
    ``list[str]`` cannot be used directly.  Instead the user enters a
    comma-separated string which is split by :func:`select_multiple`.
    """

    selected: str = ""


async def select_multiple(
    ctx: Context,
    message: str,
    choices: list[str],
    *,
    default: list[str] | None = None,
) -> list[str]:
    """Ask the user to select one or more options from a list.

    The user is presented with a prompt listing the valid choices and
    asked to enter their selections as a comma-separated string.
    The helper parses the response and returns only values that appear
    in *choices*.

    Args:
        ctx: MCP tool context.
        message: Human-readable prompt shown to the user.
        choices: List of valid string options.
        default: Value returned when elicitation is unavailable
            or the user declines/cancels.  Defaults to an empty list.

    Returns:
        List of selected choices, or *default* on
        decline/cancel/unsupported.
    """
    if default is None:
        default = []

    if not choices:
        return default

    prompt = f"{message}\nChoices: {', '.join(choices)}\nEnter comma-separated selections:"

    try:
        result = await ctx.elicit(prompt, MultiSelectSchema)  # type: ignore[arg-type]
    except McpError:
        logger.debug("Elicitation not supported; using default=%s", default)
        return default
    except (NotImplementedError, AttributeError, RuntimeError, TypeError):
        logger.debug("Elicitation failed; using default=%s", default, exc_info=True)
        return default

    if isinstance(result, AcceptedElicitation):
        data: MultiSelectSchema = result.data  # type: ignore[assignment]
        raw = data.selected if isinstance(data, MultiSelectSchema) else str(data)
        # Parse comma-separated, strip whitespace, filter to valid choices
        parsed = [s.strip() for s in raw.split(",") if s.strip() in choices]
        await ctx.info(f"User selected: {parsed}")
        return parsed

    await ctx.info(f"User {result.action}: {message}")
    return default
