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
            "codegen_start_execution",
            "codegen_get_execution_context",
            "codegen_get_agent_rules",
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
        respx.get("https://api.codegen.com/v1/alpha/organizations/42/agent/run/99/logs").mock(
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


# ── Context Tools ────────────────────────────────────────


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


# ── Create Run with Execution Context ────────────────────


class TestCreateRunWithExecution:
    @respx.mock
    async def test_enriches_prompt_when_execution_id_provided(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/cli/rules").mock(
            return_value=Response(200, json={"organization_rules": ""})
        )
        respx.get("https://api.codegen.com/v1/organizations/42/integrations").mock(
            return_value=Response(200, json={})
        )
        respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )

        await client.call_tool(
            "codegen_start_execution",
            {
                "goal": "Test enrichment",
                "execution_id": "enrich-test",
                "tasks": [{"title": "Task 1", "description": "Do the thing"}],
            },
        )

        route = respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={
                    "id": 200,
                    "status": "queued",
                    "web_url": "https://codegen.com/run/200",
                },
            )
        )

        result = await client.call_tool(
            "codegen_create_run",
            {
                "prompt": "Do the thing",
                "repo_id": 10,
                "execution_id": "enrich-test",
            },
        )
        data = json.loads(result.data)
        assert data["id"] == 200

        # Verify the prompt sent to API was enriched
        body = json.loads(route.calls[0].request.content)
        assert "Test enrichment" in body["prompt"]
        assert "Do the thing" in body["prompt"]

    @respx.mock
    async def test_falls_back_to_raw_prompt_without_execution(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )
        route = respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={"id": 201, "status": "queued", "web_url": "https://codegen.com/run/201"},
            )
        )

        result = await client.call_tool(
            "codegen_create_run",
            {"prompt": "Raw prompt only", "repo_id": 10},
        )
        data = json.loads(result.data)
        assert data["id"] == 201

        body = json.loads(route.calls[0].request.content)
        assert body["prompt"] == "Raw prompt only"


# ── Get Run with Execution Context ───────────────────────


class TestGetRunWithExecution:
    @respx.mock
    async def test_parses_logs_and_updates_task_on_completion(self, client: Client):
        # Set up an execution context first
        respx.get("https://api.codegen.com/v1/organizations/42/cli/rules").mock(
            return_value=Response(200, json={"organization_rules": ""})
        )
        respx.get("https://api.codegen.com/v1/organizations/42/integrations").mock(
            return_value=Response(200, json={})
        )
        respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )

        await client.call_tool(
            "codegen_start_execution",
            {
                "goal": "Test get_run reporting",
                "execution_id": "getrun-test",
                "tasks": [{"title": "Task 1", "description": "Build feature"}],
            },
        )

        # Mock the get_run endpoint as completed
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/300").mock(
            return_value=Response(
                200,
                json={
                    "id": 300,
                    "status": "completed",
                    "summary": "Built the feature",
                    "web_url": "https://codegen.com/run/300",
                    "github_pull_requests": [
                        {
                            "url": "https://github.com/o/r/pull/10",
                            "number": 10,
                            "title": "Add feature",
                            "state": "open",
                        }
                    ],
                },
            )
        )

        # Mock the logs endpoint
        respx.get("https://api.codegen.com/v1/alpha/organizations/42/agent/run/300/logs").mock(
            return_value=Response(
                200,
                json={
                    "id": 300,
                    "status": "completed",
                    "logs": [
                        {
                            "agent_run_id": 300,
                            "thought": "Reading code",
                            "tool_name": "read_file",
                        }
                    ],
                    "total_logs": 1,
                },
            )
        )

        result = await client.call_tool(
            "codegen_get_run",
            {
                "run_id": 300,
                "execution_id": "getrun-test",
                "task_index": 0,
            },
        )
        data = json.loads(result.data)
        assert data["status"] == "completed"
        assert data["pull_requests"][0]["number"] == 10
        assert "parsed_logs" in data
        assert data["parsed_logs"]["total_steps"] == 1

        # Verify the execution context was updated
        ctx_result = await client.call_tool(
            "codegen_get_execution_context",
            {"execution_id": "getrun-test"},
        )
        ctx_data = json.loads(ctx_result.data)
        assert ctx_data["tasks"][0]["status"] == "completed"
        assert ctx_data["tasks"][0]["report"]["summary"] == "Built the feature"
        assert ctx_data["current_task_index"] == 1


# ── New Prompts ──────────────────────────────────────────


class TestNewPrompts:
    async def test_build_task_prompt_template_registered(self, client: Client):
        prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert "build_task_prompt_template" in names

    async def test_execution_summary_registered(self, client: Client):
        prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert "execution_summary" in names


# ── Execution Resource ───────────────────────────────────


class TestExecutionResource:
    async def test_execution_resource_registered(self, client: Client):
        resources = await client.list_resources()
        uris = {str(r.uri) for r in resources}
        assert "codegen://config" in uris
