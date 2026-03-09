"""Plugin settings management tools.

Exposes two MCP tools for reading and updating plugin settings:

* ``codegen_get_settings`` — return current settings as JSON.
* ``codegen_update_settings`` — update one or more settings and persist to disk.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context


from bridge.annotations import MUTATES_LOCAL, READ_ONLY_LOCAL
from bridge.dependencies import CurrentContext
from bridge.icons import ICON_CONFIG
from bridge.settings import load_settings, update_settings


def register_settings_tools(mcp: FastMCP) -> None:
    """Register plugin settings management tools on the given FastMCP server."""

    @mcp.tool(tags={"settings"}, icons=ICON_CONFIG, timeout=5, annotations=READ_ONLY_LOCAL)
    async def codegen_get_settings(
        ctx: Context = CurrentContext(),
    ) -> str:
        """Get current plugin settings.

        Returns all plugin settings with their current values.
        Settings are loaded from ``.claude-plugin/settings.json``.
        """
        await ctx.info("Loading plugin settings")
        settings = load_settings()
        data = settings.model_dump(mode="json")
        await ctx.info(f"Settings loaded: {len(data)} fields")
        return json.dumps(data, indent=2)

    @mcp.tool(tags={"settings"}, icons=ICON_CONFIG, timeout=10, annotations=MUTATES_LOCAL)
    async def codegen_update_settings(
        key: str,
        value: str,
        ctx: Context = CurrentContext(),
    ) -> str:
        """Update a plugin setting.

        Validates the new value and persists it to ``.claude-plugin/settings.json``.

        Args:
            key: Setting name — one of "default_model", "auto_monitor", "poll_interval".
            value: New value as a string. Use "null" to reset to default.
                Booleans: "true" or "false". Integers: numeric string like "60".
        """
        await ctx.info(f"Updating setting: {key}={value}")

        # Parse the string value into the appropriate Python type
        parsed = _parse_value(value)

        try:
            updated = update_settings({key: parsed})
        except ValueError as exc:
            return json.dumps({"error": str(exc)})

        data = updated.model_dump(mode="json")
        await ctx.info(f"Setting updated: {key}={data.get(key)}")
        return json.dumps({"updated": {key: data.get(key)}, "all_settings": data}, indent=2)


def _parse_value(value: str) -> str | bool | int | None:
    """Parse a string value into the appropriate Python type.

    Supports: null, true/false, integers, and strings.
    """
    lower = value.strip().lower()

    if lower == "null" or lower == "none":
        return None
    if lower == "true":
        return True
    if lower == "false":
        return False

    # Try integer
    try:
        return int(value.strip())
    except ValueError:
        pass

    # Return as string
    return value.strip()
