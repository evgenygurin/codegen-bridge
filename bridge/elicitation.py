"""Reusable elicitation helpers for interactive user prompts.

Provides high-level wrappers around ``ctx.elicit()`` that handle:
- Graceful degradation when the client doesn't support elicitation
- Consistent logging of elicitation outcomes
- Normalization of accept/decline/cancel to simple return values
- Structured Pydantic schemas for rich confirmation dialogs

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

    from bridge.elicitation import confirm_with_schema, DangerousActionConfirmation

    @mcp.tool
    async def delete_resource(id: int, ctx: Context = CurrentContext()) -> str:
        result = await confirm_with_schema(
            ctx,
            f"Delete resource {id}? This cannot be undone.",
            DangerousActionConfirmation,
        )
        if result is None or not result.confirm:
            return "Cancelled"
        # result.reason is available if the user provided one
        ...
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp.server.context import Context
from fastmcp.server.elicitation import (
    AcceptedElicitation,
)
from mcp.shared.exceptions import McpError
from pydantic import BaseModel, Field

logger = logging.getLogger("bridge.elicitation")


# ── Elicitation schemas (Pydantic) ─────────────────────────────
#
# Pydantic models for structured elicitation.  These are used with
# ``confirm_with_schema`` to collect richer input from the user than
# a plain boolean.


class StopConfirmation(BaseModel):
    """Schema for stop-run confirmation prompt."""

    confirm: bool = Field(description="Whether to proceed with stopping the run.")


class RepoConfirmation(BaseModel):
    """Schema for repository confirmation prompt."""

    confirm: bool = Field(description="Whether to proceed with the detected repository.")


class DangerousActionConfirmation(BaseModel):
    """Schema for confirming a destructive / irreversible action.

    Provides an optional ``reason`` field so the user can annotate
    *why* they chose to proceed (useful for audit logging).
    """

    confirm: bool = Field(description="Whether to proceed with the dangerous action.")
    reason: str = Field(
        default="",
        description="Optional reason for confirming (for audit trail).",
    )


class ModelSelectionInput(BaseModel):
    """Schema for interactive model selection.

    Provides structured input when the user selects a model and
    optionally overrides temperature.
    """

    model: str = Field(description="Selected LLM model identifier.")
    temperature_override: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional temperature override for this run.",
    )


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
    """Ask the user for structured confirmation using a Pydantic schema.

    Accepts both Pydantic ``BaseModel`` subclasses and plain
    ``dataclass`` types as the schema (FastMCP handles both).

    Args:
        ctx: MCP tool context.
        message: Human-readable prompt shown to the user.
        schema: A Pydantic model or dataclass type defining the form.
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


async def collect_input[T: BaseModel](
    ctx: Context,
    message: str,
    schema: type[T],
    *,
    default_on_unsupported: dict[str, Any] | None = None,
) -> T | None:
    """Collect structured input from the user using a Pydantic model.

    Unlike ``confirm_with_schema`` which is generic over any type,
    ``collect_input`` is specifically typed to ``BaseModel`` subclasses
    and can provide a dict of defaults when elicitation is unavailable.

    Args:
        ctx: MCP tool context.
        message: Human-readable prompt shown to the user.
        schema: A Pydantic ``BaseModel`` subclass defining the input form.
        default_on_unsupported: Dict of field values used to construct
            the schema instance when elicitation is unavailable.
            If ``None``, returns ``None`` on unsupported.

    Returns:
        Populated schema instance on accept, constructed default on
        unsupported (if defaults given), or ``None``.
    """
    try:
        result = await ctx.elicit(message, schema)  # type: ignore[arg-type]
    except McpError:
        logger.debug("Elicitation not supported; using defaults")
        if default_on_unsupported is not None:
            return schema.model_validate(default_on_unsupported)
        return None
    except Exception:
        logger.debug("Elicitation failed; using defaults", exc_info=True)
        if default_on_unsupported is not None:
            return schema.model_validate(default_on_unsupported)
        return None

    if isinstance(result, AcceptedElicitation):
        return result.data  # type: ignore[return-value]

    await ctx.info(f"User {result.action}: {message}")
    return None
