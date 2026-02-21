"""Tests for agent run management tools (create, get, list, resume, stop, ban, unban,
remove-from-pr, logs).
"""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from httpx import Response


# ── Create ────────────────────────────────────────────────


class TestCreateRun:
    @respx.mock
    async def test_creates_run_and_returns_json(self, client: Client):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={
                    "id": 99,
                    "organization_id": 42,
                    "status": "queued",
                    "web_url": "https://codegen.com/run/99",
                },
            )
        )
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

    @respx.mock
    async def test_passes_images_to_api(self, client: Client):
        route = respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={
                    "id": 100,
                    "organization_id": 42,
                    "status": "queued",
                    "web_url": "https://codegen.com/run/100",
                },
            )
        )
        respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )

        await client.call_tool(
            "codegen_create_run",
            {
                "prompt": "Analyze screenshot",
                "repo_id": 10,
                "images": ["data:image/png;base64,iVBOR..."],
            },
        )

        body = json.loads(route.calls[0].request.content)
        assert body["images"] == ["data:image/png;base64,iVBOR..."]


# ── Get ───────────────────────────────────────────────────


class TestGetRun:
    @respx.mock
    async def test_returns_run_with_pr(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/99").mock(
            return_value=Response(
                200,
                json={
                    "id": 99,
                    "organization_id": 42,
                    "status": "completed",
                    "summary": "Fixed the bug",
                    "source_type": "API",
                    "github_pull_requests": [
                        {
                            "url": "https://github.com/o/r/pull/5",
                            "number": 5,
                            "title": "Fix bug",
                            "state": "open",
                            "head_branch_name": "fix-bug",
                        }
                    ],
                },
            )
        )

        result = await client.call_tool("codegen_get_run", {"run_id": 99})
        data = json.loads(result.data)
        assert data["status"] == "completed"
        assert data["source_type"] == "API"
        assert data["pull_requests"][0]["number"] == 5
        assert data["pull_requests"][0]["head_branch_name"] == "fix-bug"

    @respx.mock
    async def test_returns_run_without_optional_fields(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/101").mock(
            return_value=Response(
                200,
                json={
                    "id": 101,
                    "organization_id": 42,
                    "status": "running",
                },
            )
        )

        result = await client.call_tool("codegen_get_run", {"run_id": 101})
        data = json.loads(result.data)
        assert data["id"] == 101
        assert data["status"] == "running"
        assert "pull_requests" not in data
        assert "source_type" not in data


# ── List ──────────────────────────────────────────────────


class TestListRuns:
    @respx.mock
    async def test_passes_user_id_filter(self, client: Client):
        route = respx.get("https://api.codegen.com/v1/organizations/42/agent/runs").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": 1,
                            "organization_id": 42,
                            "status": "completed",
                            "source_type": "API",
                        }
                    ],
                    "total": 1,
                    "page": 1,
                    "size": 20,
                    "pages": 1,
                },
            )
        )

        result = await client.call_tool(
            "codegen_list_runs", {"user_id": 7, "limit": 5}
        )
        data = json.loads(result.data)
        assert data["total"] == 1
        assert data["runs"][0]["id"] == 1

        # Verify user_id was passed as query param
        request_url = str(route.calls[0].request.url)
        assert "user_id=7" in request_url

    @respx.mock
    async def test_includes_source_type_in_response(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/runs").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": 2,
                            "organization_id": 42,
                            "status": "running",
                            "source_type": "GITHUB",
                        }
                    ],
                    "total": 1,
                    "page": 1,
                    "size": 20,
                    "pages": 1,
                },
            )
        )

        result = await client.call_tool("codegen_list_runs", {})
        data = json.loads(result.data)
        assert data["runs"][0]["source_type"] == "GITHUB"


# ── Resume ────────────────────────────────────────────────


class TestResumeRun:
    @respx.mock
    async def test_passes_images_to_resume(self, client: Client):
        route = respx.post(
            "https://api.codegen.com/v1/organizations/42/agent/run/resume"
        ).mock(
            return_value=Response(
                200,
                json={
                    "id": 50,
                    "organization_id": 42,
                    "status": "running",
                    "web_url": "https://codegen.com/run/50",
                },
            )
        )

        result = await client.call_tool(
            "codegen_resume_run",
            {
                "run_id": 50,
                "prompt": "Continue with screenshot",
                "images": ["data:image/png;base64,abc123"],
            },
        )
        data = json.loads(result.data)
        assert data["id"] == 50
        assert data["status"] == "running"

        body = json.loads(route.calls[0].request.content)
        assert body["images"] == ["data:image/png;base64,abc123"]


# ── Stop ──────────────────────────────────────────────────


class TestStopRun:
    @respx.mock
    async def test_stops_run(self, client: Client):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run/ban").mock(
            return_value=Response(200, json={"id": 99, "status": "stopped"})
        )

        result = await client.call_tool("codegen_stop_run", {"run_id": 99})
        data = json.loads(result.data)
        assert data["id"] == 99
        assert data["status"] == "stopped"


# ── Ban ───────────────────────────────────────────────────


class TestBanRun:
    @respx.mock
    async def test_bans_run(self, client: Client):
        route = respx.post("https://api.codegen.com/v1/organizations/42/agent/run/ban").mock(
            return_value=Response(200, json={})
        )

        result = await client.call_tool(
            "codegen_ban_run",
            {"run_id": 55, "before_card_order_id": "abc", "after_card_order_id": "xyz"},
        )
        data = json.loads(result.data)
        assert data["run_id"] == 55
        assert data["action"] == "banned"

        body = json.loads(route.calls[0].request.content)
        assert body["agent_run_id"] == 55
        assert body["before_card_order_id"] == "abc"
        assert body["after_card_order_id"] == "xyz"

    @respx.mock
    async def test_ban_minimal_params(self, client: Client):
        route = respx.post("https://api.codegen.com/v1/organizations/42/agent/run/ban").mock(
            return_value=Response(200, json={"message": "Banned"})
        )

        result = await client.call_tool("codegen_ban_run", {"run_id": 56})
        data = json.loads(result.data)
        assert data["run_id"] == 56
        assert data["action"] == "banned"
        assert data["message"] == "Banned"

        body = json.loads(route.calls[0].request.content)
        assert body == {"agent_run_id": 56}


# ── Unban ─────────────────────────────────────────────────


class TestUnbanRun:
    @respx.mock
    async def test_unbans_run(self, client: Client):
        route = respx.post(
            "https://api.codegen.com/v1/organizations/42/agent/run/unban"
        ).mock(return_value=Response(200, json={}))

        result = await client.call_tool(
            "codegen_unban_run",
            {"run_id": 60, "before_card_order_id": "a1"},
        )
        data = json.loads(result.data)
        assert data["run_id"] == 60
        assert data["action"] == "unbanned"

        body = json.loads(route.calls[0].request.content)
        assert body["agent_run_id"] == 60
        assert body["before_card_order_id"] == "a1"

    @respx.mock
    async def test_unban_minimal_params(self, client: Client):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run/unban").mock(
            return_value=Response(200, json={"message": "Unbanned"})
        )

        result = await client.call_tool("codegen_unban_run", {"run_id": 61})
        data = json.loads(result.data)
        assert data["run_id"] == 61
        assert data["action"] == "unbanned"
        assert data["message"] == "Unbanned"


# ── Remove from PR ────────────────────────────────────────


class TestRemoveFromPr:
    @respx.mock
    async def test_removes_from_pr(self, client: Client):
        route = respx.post(
            "https://api.codegen.com/v1/organizations/42/agent/run/remove-from-pr"
        ).mock(return_value=Response(200, json={}))

        result = await client.call_tool(
            "codegen_remove_from_pr",
            {
                "run_id": 70,
                "before_card_order_id": "b1",
                "after_card_order_id": "b2",
            },
        )
        data = json.loads(result.data)
        assert data["run_id"] == 70
        assert data["action"] == "removed_from_pr"

        body = json.loads(route.calls[0].request.content)
        assert body["agent_run_id"] == 70
        assert body["before_card_order_id"] == "b1"
        assert body["after_card_order_id"] == "b2"

    @respx.mock
    async def test_remove_from_pr_minimal(self, client: Client):
        respx.post(
            "https://api.codegen.com/v1/organizations/42/agent/run/remove-from-pr"
        ).mock(return_value=Response(200, json={"message": "Removed"}))

        result = await client.call_tool("codegen_remove_from_pr", {"run_id": 71})
        data = json.loads(result.data)
        assert data["run_id"] == 71
        assert data["action"] == "removed_from_pr"
        assert data["message"] == "Removed"


# ── Logs ──────────────────────────────────────────────────


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
                            "message_type": "ACTION",
                        },
                        {
                            "agent_run_id": 99,
                            "thought": "Found issue",
                            "tool_name": None,
                            "message_type": "PLAN_EVALUATION",
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
        assert data["logs"][0]["message_type"] == "ACTION"
        assert data["logs"][1]["message_type"] == "PLAN_EVALUATION"


# ── Create with Execution Context ─────────────────────────


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


# ── Get with Execution Context ────────────────────────────


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

        # Mock the logs endpoint (updated path — no /alpha/)
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
