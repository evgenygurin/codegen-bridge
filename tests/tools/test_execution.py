"""Tests for execution context management tools (start, get context, rules)."""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from httpx import Response


class TestStartExecution:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_start_execution" in names

    @respx.mock
    async def test_starts_adhoc_execution(self, client: Client):
        # Mock rules endpoint
        respx.get("https://api.codegen.com/v1/organizations/42/cli/rules").mock(
            return_value=Response(
                200,
                json={"organization_rules": "Use type hints", "user_custom_prompt": ""},
            )
        )
        # Mock repo detection
        respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )

        result = await client.call_tool(
            "codegen_start_execution",
            {"execution_id": "test-exec", "goal": "Fix the bug"},
        )
        data = json.loads(result.data)
        assert data["execution_id"] == "test-exec"
        assert data["mode"] == "adhoc"
        assert data["status"] == "active"


class TestGetExecutionContext:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_execution_context" in names

    @respx.mock
    async def test_returns_error_when_no_context(self, client: Client):
        result = await client.call_tool(
            "codegen_get_execution_context",
            {"execution_id": "nonexistent"},
        )
        data = json.loads(result.data)
        assert "error" in data


class TestGetAgentRules:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_agent_rules" in names

    @respx.mock
    async def test_returns_rules(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/cli/rules").mock(
            return_value=Response(
                200,
                json={"organization_rules": "Use type hints", "user_custom_prompt": ""},
            )
        )
        result = await client.call_tool("codegen_get_agent_rules", {})
        data = json.loads(result.data)
        assert "type hints" in data["organization_rules"]
