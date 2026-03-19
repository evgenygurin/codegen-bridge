"""Tests for bulk agent run creation tool."""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from httpx import Response


class TestBulkCreateRuns:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_bulk_create_runs" in names

    @respx.mock
    async def test_creates_multiple_runs(self, client: Client):
        route = respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "id": 101,
                        "organization_id": 42,
                        "status": "queued",
                        "web_url": "https://codegen.com/run/101",
                    },
                ),
                Response(
                    200,
                    json={
                        "id": 102,
                        "organization_id": 42,
                        "status": "queued",
                        "web_url": "https://codegen.com/run/102",
                    },
                ),
            ]
        )

        result = await client.call_tool(
            "codegen_bulk_create_runs",
            {
                "tasks": [
                    {"prompt": "Fix bug A"},
                    {"prompt": "Fix bug B"},
                ],
                "repo_id": 10,
            },
        )
        data = json.loads(result.data)
        assert data["total"] == 2
        assert data["created"] == 2
        assert data["failed"] == 0
        assert len(data["runs"]) == 2
        assert data["runs"][0]["id"] == 101
        assert data["runs"][1]["id"] == 102
        assert route.call_count == 2

    @respx.mock
    async def test_skips_tasks_without_prompt(self, client: Client):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={
                    "id": 103,
                    "organization_id": 42,
                    "status": "queued",
                    "web_url": "https://codegen.com/run/103",
                },
            )
        )

        result = await client.call_tool(
            "codegen_bulk_create_runs",
            {
                "tasks": [
                    {"prompt": ""},
                    {"prompt": "Valid task"},
                ],
                "repo_id": 10,
            },
        )
        data = json.loads(result.data)
        assert data["total"] == 2
        assert data["created"] == 1
        assert data["failed"] == 1
        assert data["runs"][0]["error"] == "Missing prompt"
        assert data["runs"][1]["id"] == 103

    async def test_empty_tasks_returns_error(self, client: Client):
        result = await client.call_tool(
            "codegen_bulk_create_runs",
            {"tasks": []},
        )
        data = json.loads(result.data)
        assert data["error"] == "No tasks provided"
        assert data["runs"] == []

    @respx.mock
    async def test_per_task_overrides(self, client: Client):
        route = respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={
                    "id": 104,
                    "organization_id": 42,
                    "status": "queued",
                    "web_url": "https://codegen.com/run/104",
                },
            )
        )

        result = await client.call_tool(
            "codegen_bulk_create_runs",
            {
                "tasks": [
                    {"prompt": "Task with override", "repo_id": "20", "model": "gpt-4o"},
                ],
                "repo_id": 10,
                "model": "claude-3-5-sonnet",
            },
        )
        data = json.loads(result.data)
        assert data["created"] == 1

        # Verify the per-task override was used
        body = json.loads(route.calls[0].request.content)
        assert body["repo_id"] == 20
        assert body["model"] == "gpt-4o"

    @respx.mock
    async def test_handles_api_errors_gracefully(self, client: Client):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(500, json={"detail": "Internal error"})
        )

        result = await client.call_tool(
            "codegen_bulk_create_runs",
            {
                "tasks": [{"prompt": "Will fail"}],
                "repo_id": 10,
            },
        )
        data = json.loads(result.data)
        assert data["total"] == 1
        assert data["created"] == 0
        assert data["failed"] == 1
        assert "error" in data["runs"][0]
