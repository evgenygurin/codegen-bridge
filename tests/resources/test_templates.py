"""Tests for parameterized resource templates (runs, logs, execution)."""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from httpx import Response

# ── Run Resource ─────────────────────────────────────────────────


class TestRunResource:
    """Tests for codegen://runs/{run_id} resource template."""

    async def test_resource_template_registered(self, client: Client):
        templates = await client.list_resource_templates()
        uris = {str(t.uriTemplate) for t in templates}
        assert "codegen://runs/{run_id}" in uris

    @respx.mock
    async def test_returns_run_data(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/123").mock(
            return_value=Response(
                200,
                json={
                    "id": 123,
                    "status": "completed",
                    "web_url": "https://codegen.com/runs/123",
                    "result": "Task completed",
                    "summary": "Added auth middleware",
                },
            )
        )

        result = await client.read_resource("codegen://runs/123")
        data = json.loads(result[0].text)

        assert data["id"] == 123
        assert data["status"] == "completed"
        assert data["web_url"] == "https://codegen.com/runs/123"
        assert data["summary"] == "Added auth middleware"

    @respx.mock
    async def test_includes_pull_requests(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/456").mock(
            return_value=Response(
                200,
                json={
                    "id": 456,
                    "status": "completed",
                    "web_url": "https://codegen.com/runs/456",
                    "github_pull_requests": [
                        {
                            "url": "https://github.com/org/repo/pull/10",
                            "number": 10,
                            "title": "feat: add auth",
                            "state": "open",
                        }
                    ],
                },
            )
        )

        result = await client.read_resource("codegen://runs/456")
        data = json.loads(result[0].text)

        assert "pull_requests" in data
        assert data["pull_requests"][0]["number"] == 10

    @respx.mock
    async def test_same_data_as_tool(self, client: Client):
        """Resource and tool should return identical data (same service path)."""
        run_json = {
            "id": 789,
            "status": "running",
            "web_url": "https://codegen.com/runs/789",
        }
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/789").mock(
            return_value=Response(200, json=run_json)
        )

        resource_result = await client.read_resource("codegen://runs/789")
        resource_data = json.loads(resource_result[0].text)

        tool_result = await client.call_tool("codegen_get_run", {"run_id": 789})
        tool_data = json.loads(tool_result.data)

        # Both should have the same core fields
        assert resource_data["id"] == tool_data["id"]
        assert resource_data["status"] == tool_data["status"]
        assert resource_data["web_url"] == tool_data["web_url"]


# ── Logs Resource ────────────────────────────────────────────────


class TestRunLogsResource:
    """Tests for codegen://runs/{run_id}/logs resource template."""

    async def test_resource_template_registered(self, client: Client):
        templates = await client.list_resource_templates()
        uris = {str(t.uriTemplate) for t in templates}
        assert "codegen://runs/{run_id}/logs" in uris

    @respx.mock
    async def test_returns_log_data(self, client: Client):
        respx.get(
            "https://api.codegen.com/v1/alpha/organizations/42/agent/run/100/logs"
        ).mock(
            return_value=Response(
                200,
                json={
                    "id": 100,
                    "status": "completed",
                    "total_logs": 2,
                    "logs": [
                        {
                            "agent_run_id": 100,
                            "thought": "Reading file",
                            "tool_name": "read_file",
                            "created_at": "2025-01-01T00:00:00Z",
                        },
                        {
                            "agent_run_id": 100,
                            "thought": "Writing code",
                            "tool_name": "write_file",
                            "created_at": "2025-01-01T00:01:00Z",
                        },
                    ],
                },
            )
        )

        result = await client.read_resource("codegen://runs/100/logs")
        data = json.loads(result[0].text)

        assert data["run_id"] == 100
        assert data["status"] == "completed"
        assert len(data["logs"]) == 2
        assert data["logs"][0]["tool_name"] == "read_file"

    @respx.mock
    async def test_logs_have_pagination(self, client: Client):
        respx.get(
            "https://api.codegen.com/v1/alpha/organizations/42/agent/run/200/logs"
        ).mock(
            return_value=Response(
                200,
                json={
                    "id": 200,
                    "status": "running",
                    "total_logs": 50,
                    "logs": [
                        {"agent_run_id": 200, "thought": f"Step {i}"}
                        for i in range(20)
                    ],
                },
            )
        )

        result = await client.read_resource("codegen://runs/200/logs")
        data = json.loads(result[0].text)

        assert data["total_logs"] == 50
        assert "next_cursor" in data


# ── Execution Resource ───────────────────────────────────────────


class TestExecutionResource:
    """Tests for codegen://execution/{execution_id} resource template."""

    async def test_resource_template_registered(self, client: Client):
        templates = await client.list_resource_templates()
        uris = {str(t.uriTemplate) for t in templates}
        assert "codegen://execution/{execution_id}" in uris

    async def test_returns_not_found_for_missing(self, client: Client):
        result = await client.read_resource(
            "codegen://execution/nonexistent-id"
        )
        data = json.loads(result[0].text)
        assert data["status"] == "not_found"
        assert data["execution_id"] == "nonexistent-id"

    @respx.mock
    async def test_returns_execution_context(self, client: Client):
        """When an execution exists, its full context should be returned."""
        # Create an execution context first via the tool
        respx.post(
            "https://api.codegen.com/v1/organizations/42/agent/rules"
        ).mock(return_value=Response(200, json={}))
        respx.get(
            "https://api.codegen.com/v1/organizations/42/agent/rules"
        ).mock(return_value=Response(200, json={}))

        await client.call_tool(
            "codegen_start_execution",
            {
                "execution_id": "test-exec-1",
                "goal": "Build auth system",
                "tasks": [{"title": "Setup", "description": "Initial setup"}],
            },
        )

        # Now read it via resource template
        result = await client.read_resource("codegen://execution/test-exec-1")
        data = json.loads(result[0].text)

        assert data["id"] == "test-exec-1"
        assert data["goal"] == "Build auth system"
        assert data["status"] == "active"
        assert len(data["tasks"]) == 1
