"""Tests for agent run management tools (create, get, list, resume, stop, logs)."""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from httpx import Response


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
