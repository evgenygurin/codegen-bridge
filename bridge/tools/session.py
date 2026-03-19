"""Session state management tools.

Provides MCP tools for storing and retrieving per-session key/value
preferences.  The state lives in memory for the duration of the MCP
session and is reset on server restart or client disconnect.

Tools:
- ``codegen_set_session_preference``   — store a key/value pair
- ``codegen_get_session_preferences``  — retrieve all preferences
- ``codegen_clear_session_preferences`` — clear all preferences
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context
from mcp.types import ToolAnnotations

from bridge.dependencies import CurrentContext, Depends, get_session_state
from bridge.elicitation import confirm_action
from bridge.icons import ICON_SESSION


def register_session_tools(mcp: FastMCP) -> None:
    """Register session state management tools on the given FastMCP server."""

    @mcp.tool(
        tags={"session"},
        icons=ICON_SESSION,
        timeout=5,
        annotations=ToolAnnotations(
            title="Set Session Preference",
            readOnlyHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def codegen_set_session_preference(
        key: str,
        value: str,
        ctx: Context = CurrentContext(),
        session: dict[str, str] = Depends(get_session_state),
    ) -> str:
        """Store a session preference (key/value pair).

        Preferences persist for the lifetime of the current MCP session.
        Useful for remembering choices like preferred model, repo, or
        default branch across multiple tool invocations.

        Args:
            key: Preference name (e.g. ``"default_model"``).
            value: Preference value (e.g. ``"claude-sonnet-4-20250514"``).
        """
        session[key] = value
        await ctx.info(f"Session preference set: {key}={value}")
        return json.dumps({"ok": True, "key": key, "value": value})

    @mcp.tool(
        tags={"session"},
        icons=ICON_SESSION,
        timeout=5,
        annotations=ToolAnnotations(
            title="Get Session Preferences",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def codegen_get_session_preferences(
        ctx: Context = CurrentContext(),
        session: dict[str, str] = Depends(get_session_state),
    ) -> str:
        """Get all session preferences.

        Returns a JSON object with all key/value pairs stored in the
        current session.
        """
        await ctx.info(f"Session preferences: {len(session)} entries")
        return json.dumps({"preferences": dict(session)})

    @mcp.tool(
        tags={"session"},
        icons=ICON_SESSION,
        timeout=5,
        annotations=ToolAnnotations(
            title="Clear Session Preferences",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def codegen_clear_session_preferences(
        ctx: Context = CurrentContext(),
        session: dict[str, str] = Depends(get_session_state),
    ) -> str:
        """Clear all session preferences.

        Removes all key/value pairs stored in the current session.
        """
        count = len(session)
        if count > 0:
            confirmed = await confirm_action(ctx, f"Clear all {count} session preferences?")
            if not confirmed:
                return json.dumps({"cancelled": True, "reason": "User declined"})
        session.clear()
        await ctx.info(f"Cleared {count} session preferences")
        return json.dumps({"ok": True, "cleared": count})
