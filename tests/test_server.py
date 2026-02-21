"""Tests for MCP server tools, resources, and prompts."""

from __future__ import annotations

import json
import os

import pytest
import respx
from fastmcp import Client
from httpx import Response

# Force test env vars before importing server
os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "42"

from bridge.server import mcp


@pytest.fixture(autouse=True)
def _force_test_env(monkeypatch):
    """Ensure test env vars override real ones for every test."""
    monkeypatch.setenv("CODEGEN_API_KEY", "test-key")
    monkeypatch.setenv("CODEGEN_ORG_ID", "42")


@pytest.fixture
async def client():
    """Create in-memory MCP client with lifespan."""
    async with Client(mcp) as c:
        yield c


# ── Tool Registration ────────────────────────────────────


class TestToolRegistration:
    async def test_core_tools_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        core = {
            "codegen_create_run",
            "codegen_get_run",
            "codegen_list_runs",
            "codegen_resume_run",
            "codegen_stop_run",
            "codegen_get_logs",
            "codegen_list_orgs",
            "codegen_list_repos",
        }
        assert core.issubset(names), f"Missing core tools: {core - names}"

    async def test_create_run_has_description(self, client: Client):
        tools = await client.list_tools()
        create_tool = next(t for t in tools if t.name == "codegen_create_run")
        assert "agent run" in create_tool.description.lower()


# ── Core Tools ───────────────────────────────────────────


class TestCreateRun:
    @respx.mock
    async def test_creates_run_and_returns_json(self, client: Client):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={
                    "id": 99,
                    "status": "queued",
                    "web_url": "https://codegen.com/run/99",
                },
            )
        )
        # Mock repo detection to avoid subprocess
        respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )

        result = await client.call_tool(
            "codegen_create_run",
            {"prompt": "Fix the bug", "repo_id": 10},
        )
        data = json.loads(result.data)
        assert data["id"] == 99
        assert data["status"] == "queued"


class TestGetRun:
    @respx.mock
    async def test_returns_run_with_pr(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/99").mock(
            return_value=Response(
                200,
                json={
                    "id": 99,
                    "status": "completed",
                    "summary": "Fixed the bug",
                    "github_pull_requests": [
                        {
                            "url": "https://github.com/o/r/pull/5",
                            "number": 5,
                            "title": "Fix bug",
                            "state": "open",
                        }
                    ],
                },
            )
        )

        result = await client.call_tool("codegen_get_run", {"run_id": 99})
        data = json.loads(result.data)
        assert data["status"] == "completed"
        assert data["pull_requests"][0]["number"] == 5


class TestStopRun:
    @respx.mock
    async def test_stops_run(self, client: Client):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run/ban").mock(
            return_value=Response(
                200,
                json={
                    "id": 99,
                    "status": "stopped",
                    "web_url": "https://codegen.com/run/99",
                },
            )
        )

        result = await client.call_tool("codegen_stop_run", {"run_id": 99})
        data = json.loads(result.data)
        assert data["id"] == 99
        assert data["status"] == "stopped"


class TestGetLogs:
    @respx.mock
    async def test_returns_formatted_logs(self, client: Client):
        respx.get(
            "https://api.codegen.com/v1/alpha/organizations/42/agent/run/99/logs"
        ).mock(
            return_value=Response(
                200,
                json={
                    "id": 99,
                    "status": "running",
                    "logs": [
                        {
                            "agent_run_id": 99,
                            "thought": "Reading code",
                            "tool_name": "read_file",
                        },
                        {
                            "agent_run_id": 99,
                            "thought": "Found issue",
                            "tool_name": None,
                        },
                    ],
                    "total_logs": 2,
                },
            )
        )

        result = await client.call_tool("codegen_get_logs", {"run_id": 99})
        data = json.loads(result.data)
        assert data["total_logs"] == 2
        assert data["logs"][0]["thought"] == "Reading code"


# ── Resources ────────────────────────────────────────────


class TestResources:
    async def test_config_resource(self, client: Client):
        resources = await client.list_resources()
        uris = {str(r.uri) for r in resources}
        assert "codegen://config" in uris

    async def test_config_returns_org_id(self, client: Client):
        result = await client.read_resource("codegen://config")
        data = json.loads(result[0].text)
        assert data["org_id"] == "42"
        assert data["has_api_key"] is True


# ── Prompts ──────────────────────────────────────────────


class TestPrompts:
    async def test_prompts_registered(self, client: Client):
        prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert "delegate_task" in names
        assert "monitor_runs" in names

    async def test_delegate_task_prompt(self, client: Client):
        result = await client.get_prompt(
            "delegate_task",
            {"task_description": "Fix login bug"},
        )
        text = result.messages[0].content.text
        assert "Fix login bug" in text
        assert "Constraints" in text
