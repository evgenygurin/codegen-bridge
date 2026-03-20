"""Tests for session state management tools."""

from __future__ import annotations

import json

from fastmcp import Client


class TestSetSessionPreference:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_set_session_preference" in names

    async def test_set_preference(self, client: Client):
        result = await client.call_tool(
            "codegen_set_session_preference",
            {"key": "default_model", "value": "claude-sonnet-4-20250514"},
        )
        data = json.loads(result.data)
        assert data["ok"] is True
        assert data["key"] == "default_model"
        assert data["value"] == "claude-sonnet-4-20250514"


class TestGetSessionPreferences:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_session_preferences" in names

    async def test_initially_empty(self, client: Client):
        result = await client.call_tool("codegen_get_session_preferences", {})
        data = json.loads(result.data)
        assert data["preferences"] == {}

    async def test_set_then_get(self, client: Client):
        """Set two preferences and read them back — within a single session."""
        # Set preferences
        await client.call_tool(
            "codegen_set_session_preference",
            {"key": "model", "value": "gpt-4o"},
        )
        await client.call_tool(
            "codegen_set_session_preference",
            {"key": "branch", "value": "develop"},
        )

        # Read them back
        result = await client.call_tool("codegen_get_session_preferences", {})
        data = json.loads(result.data)
        assert data["preferences"]["model"] == "gpt-4o"
        assert data["preferences"]["branch"] == "develop"
        assert len(data["preferences"]) == 2


class TestClearSessionPreferences:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_clear_session_preferences" in names

    async def test_clear_empty(self, client: Client):
        result = await client.call_tool("codegen_clear_session_preferences", {})
        data = json.loads(result.data)
        assert data["ok"] is True
        assert data["cleared"] == 0

    async def test_set_then_clear(self, client: Client):
        """Set a preference, clear, and verify empty — single session."""
        # Set
        await client.call_tool(
            "codegen_set_session_preference",
            {"key": "theme", "value": "dark"},
        )

        # Clear
        result = await client.call_tool("codegen_clear_session_preferences", {})
        data = json.loads(result.data)
        assert data["ok"] is True
        assert data["cleared"] == 1

        # Verify empty
        result = await client.call_tool("codegen_get_session_preferences", {})
        data = json.loads(result.data)
        assert data["preferences"] == {}


# ── Clear Session Elicitation ──────────────────────────────


from fastmcp.client.elicitation import ElicitResult  # noqa: E402

from bridge.server import mcp as _mcp  # noqa: E402


def _accept_handler():
    async def handler(message, response_type, request_params, context):
        return ElicitResult(action="accept", content={"value": True})

    return handler


def _decline_handler():
    async def handler(message, response_type, request_params, context):
        return ElicitResult(action="decline", content=None)

    return handler


class TestClearSessionElicitation:
    """Elicitation tests for codegen_clear_session_preferences."""

    async def test_clear_empty_skips_elicitation(self):
        """Clearing an empty session doesn't trigger elicitation."""
        async with Client(_mcp) as c:
            result = await c.call_tool("codegen_clear_session_preferences", {})
            data = json.loads(result.data)
            assert data["ok"] is True
            assert data["cleared"] == 0

    async def test_clear_cancelled_when_user_declines(self):
        """User declines clearing non-empty session."""
        async with Client(_mcp, elicitation_handler=_decline_handler()) as c:
            # Set a preference first
            await c.call_tool(
                "codegen_set_session_preference",
                {"key": "elicit_test", "value": "v1"},
            )
            result = await c.call_tool("codegen_clear_session_preferences", {})
            data = json.loads(result.data)
            assert data["cancelled"] is True
            assert data["reason"] == "User declined"

    async def test_clear_proceeds_when_user_confirms(self):
        """User confirms clearing non-empty session."""
        async with Client(_mcp, elicitation_handler=_accept_handler()) as c:
            # Set a preference first
            await c.call_tool(
                "codegen_set_session_preference",
                {"key": "elicit_test2", "value": "v2"},
            )
            result = await c.call_tool("codegen_clear_session_preferences", {})
            data = json.loads(result.data)
            assert data["ok"] is True
            assert data["cleared"] >= 1
