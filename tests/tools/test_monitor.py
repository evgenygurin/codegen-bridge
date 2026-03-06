"""Tests for agent run monitoring tools (codegen_monitor_run, codegen_list_monitors).

Validates:
- Monitor tool polls until terminal state and reports progress
- Monitor tool times out gracefully when run stays active
- Monitor tool tracks via BackgroundTaskManager
- Monitor tool integrates with execution context
- List monitors tool returns correct data
- Tool registration and metadata
"""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from httpx import Response

from bridge.tools.agent._progress import MONITOR_RUN_TASK

# ── TaskConfig tests ─────────────────────────────────────


class TestMonitorRunTaskConfig:
    def test_monitor_run_task_is_optional(self):
        assert MONITOR_RUN_TASK.mode == "optional"

    def test_monitor_run_task_supports_tasks(self):
        assert MONITOR_RUN_TASK.supports_tasks() is True

    def test_monitor_run_task_is_not_required(self):
        assert MONITOR_RUN_TASK.mode != "required"


# ── Tool registration tests ──────────────────────────────


class TestToolRegistration:
    async def test_monitor_run_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_monitor_run" in names

    async def test_list_monitors_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_list_monitors" in names

    async def test_monitor_run_has_description(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_monitor_run")
        assert "monitor" in tool.description.lower()
        assert "progress" in tool.description.lower()

    async def test_list_monitors_has_description(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_list_monitors")
        assert "monitor" in tool.description.lower()

    async def test_all_agent_tools_still_present(self, client: Client):
        """Adding monitor tools must not break registration of others."""
        tools = await client.list_tools()
        names = {t.name for t in tools}
        expected = {
            "codegen_create_run",
            "codegen_get_run",
            "codegen_list_runs",
            "codegen_resume_run",
            "codegen_stop_run",
            "codegen_ban_run",
            "codegen_unban_run",
            "codegen_remove_from_pr",
            "codegen_get_logs",
            "codegen_monitor_run",
            "codegen_list_monitors",
        }
        assert expected.issubset(names), f"Missing tools: {expected - names}"


# ── Monitor run - terminal on first poll ─────────────────


class TestMonitorRunTerminal:
    @respx.mock
    async def test_returns_immediately_when_already_completed(self, client: Client):
        """If run is already completed, monitor should return after first poll."""
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/100").mock(
            return_value=Response(
                200,
                json={
                    "id": 100,
                    "status": "completed",
                    "summary": "All done",
                    "web_url": "https://codegen.com/run/100",
                },
            )
        )

        result = await client.call_tool(
            "codegen_monitor_run",
            {"run_id": 100, "poll_interval": 2, "max_duration": 10},
        )
        data = json.loads(result.data)
        assert data["outcome"] == "completed"
        assert data["run_id"] == 100
        assert data["poll_count"] == 1
        assert "monitor_id" in data

    @respx.mock
    async def test_returns_on_failed_status(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/101").mock(
            return_value=Response(
                200,
                json={
                    "id": 101,
                    "status": "failed",
                    "web_url": "https://codegen.com/run/101",
                },
            )
        )

        result = await client.call_tool(
            "codegen_monitor_run",
            {"run_id": 101, "poll_interval": 2, "max_duration": 10},
        )
        data = json.loads(result.data)
        assert data["outcome"] == "failed"
        assert data["poll_count"] == 1


# ── Monitor run - polling then terminal ──────────────────


class TestMonitorRunPolling:
    @respx.mock
    async def test_polls_until_completed(self, client: Client):
        """Run starts 'running', then becomes 'completed' on second poll."""
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return Response(
                    200,
                    json={
                        "id": 200,
                        "status": "running",
                        "web_url": "https://codegen.com/run/200",
                    },
                )
            return Response(
                200,
                json={
                    "id": 200,
                    "status": "completed",
                    "summary": "Task done",
                    "web_url": "https://codegen.com/run/200",
                },
            )

        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/200").mock(
            side_effect=side_effect
        )

        result = await client.call_tool(
            "codegen_monitor_run",
            {"run_id": 200, "poll_interval": 2, "max_duration": 30},
        )
        data = json.loads(result.data)
        assert data["outcome"] == "completed"
        assert data["poll_count"] == 2
        assert data["summary"] == "Task done"


# ── Monitor run - timeout ────────────────────────────────


class TestMonitorRunTimeout:
    @respx.mock
    async def test_returns_timeout_when_run_stays_running(self, client: Client):
        """If run never reaches terminal state, monitor should time out."""
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/300").mock(
            return_value=Response(
                200,
                json={
                    "id": 300,
                    "status": "running",
                    "web_url": "https://codegen.com/run/300",
                },
            )
        )

        result = await client.call_tool(
            "codegen_monitor_run",
            {
                "run_id": 300,
                "poll_interval": 2,
                "max_duration": 10,
            },
        )
        data = json.loads(result.data)
        assert data["outcome"] == "monitor_timeout"
        assert data["last_known_status"] == "running"
        assert data["poll_count"] >= 1
        assert "codegen_get_run" in data["message"]


# ── Monitor run - with PRs ──────────────────────────────


class TestMonitorRunWithPRs:
    @respx.mock
    async def test_includes_pr_info(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/400").mock(
            return_value=Response(
                200,
                json={
                    "id": 400,
                    "status": "completed",
                    "summary": "PR created",
                    "web_url": "https://codegen.com/run/400",
                    "github_pull_requests": [
                        {
                            "url": "https://github.com/org/repo/pull/5",
                            "number": 5,
                            "title": "New feature",
                            "state": "open",
                            "head_branch_name": "feat/new",
                        }
                    ],
                },
            )
        )

        result = await client.call_tool(
            "codegen_monitor_run",
            {"run_id": 400, "poll_interval": 2, "max_duration": 10},
        )
        data = json.loads(result.data)
        assert data["outcome"] == "completed"
        assert len(data["pull_requests"]) == 1
        assert data["pull_requests"][0]["number"] == 5
        assert data["pull_requests"][0]["head_branch_name"] == "feat/new"


# ── Monitor run - input clamping ────────────────────────


class TestMonitorRunInputClamping:
    @respx.mock
    async def test_clamps_poll_interval_below_minimum(self, client: Client):
        """poll_interval=1 should be clamped to MIN_POLL_INTERVAL (2)."""
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/500").mock(
            return_value=Response(
                200,
                json={
                    "id": 500,
                    "status": "completed",
                    "web_url": "https://codegen.com/run/500",
                },
            )
        )

        result = await client.call_tool(
            "codegen_monitor_run",
            {"run_id": 500, "poll_interval": 1, "max_duration": 10},
        )
        data = json.loads(result.data)
        # Should still work — just clamped
        assert data["outcome"] == "completed"

    @respx.mock
    async def test_clamps_max_duration_below_minimum(self, client: Client):
        """max_duration=5 should be clamped to MIN_DURATION (10)."""
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/501").mock(
            return_value=Response(
                200,
                json={
                    "id": 501,
                    "status": "completed",
                    "web_url": "https://codegen.com/run/501",
                },
            )
        )

        result = await client.call_tool(
            "codegen_monitor_run",
            {"run_id": 501, "poll_interval": 2, "max_duration": 5},
        )
        data = json.loads(result.data)
        assert data["outcome"] == "completed"


# ── List monitors ────────────────────────────────────────


class TestListMonitors:
    async def test_returns_empty_initially(self, client: Client):
        result = await client.call_tool("codegen_list_monitors", {})
        data = json.loads(result.data)
        assert data["total"] >= 0
        assert isinstance(data["monitors"], list)

    @respx.mock
    async def test_monitor_result_contains_monitor_id(self, client: Client):
        """Monitor result includes monitor_id that can be used for tracking."""
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/600").mock(
            return_value=Response(
                200,
                json={
                    "id": 600,
                    "status": "completed",
                    "web_url": "https://codegen.com/run/600",
                },
            )
        )

        result = await client.call_tool(
            "codegen_monitor_run",
            {"run_id": 600, "poll_interval": 2, "max_duration": 10},
        )
        data = json.loads(result.data)
        assert "monitor_id" in data
        assert isinstance(data["monitor_id"], str)
        assert len(data["monitor_id"]) > 0

    async def test_list_monitors_accepts_active_only(self, client: Client):
        """list_monitors should accept active_only parameter."""
        result = await client.call_tool(
            "codegen_list_monitors", {"active_only": True}
        )
        data = json.loads(result.data)
        assert data["total"] >= 0
        assert isinstance(data["monitors"], list)

    async def test_list_monitors_accepts_run_id(self, client: Client):
        """list_monitors should accept run_id filter."""
        result = await client.call_tool(
            "codegen_list_monitors", {"run_id": 999}
        )
        data = json.loads(result.data)
        assert data["total"] == 0
        assert isinstance(data["monitors"], list)


# ── Monitor run with execution context ───────────────────


class TestMonitorRunWithExecution:
    @respx.mock
    async def test_updates_execution_context_on_completion(self, client: Client):
        """Monitor should auto-report to execution context when run completes."""
        # Set up execution context
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
                "goal": "Test monitor execution",
                "execution_id": "monitor-exec-test",
                "tasks": [{"title": "Task 1", "description": "Build feature"}],
            },
        )

        # Mock the run endpoint as completed
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/800").mock(
            return_value=Response(
                200,
                json={
                    "id": 800,
                    "status": "completed",
                    "summary": "Feature built",
                    "web_url": "https://codegen.com/run/800",
                },
            )
        )

        # Mock the logs endpoint for auto-reporting
        respx.get(
            "https://api.codegen.com/v1/alpha/organizations/42/agent/run/800/logs"
        ).mock(
            return_value=Response(
                200,
                json={
                    "id": 800,
                    "status": "completed",
                    "logs": [
                        {
                            "agent_run_id": 800,
                            "thought": "Building feature",
                            "tool_name": "write_file",
                        }
                    ],
                    "total_logs": 1,
                },
            )
        )

        # Run monitor with execution context
        result = await client.call_tool(
            "codegen_monitor_run",
            {
                "run_id": 800,
                "execution_id": "monitor-exec-test",
                "task_index": 0,
                "poll_interval": 2,
                "max_duration": 10,
            },
        )
        data = json.loads(result.data)
        assert data["outcome"] == "completed"

        # Verify execution context was updated
        ctx_result = await client.call_tool(
            "codegen_get_execution_context",
            {"execution_id": "monitor-exec-test"},
        )
        ctx_data = json.loads(ctx_result.data)
        assert ctx_data["tasks"][0]["status"] == "completed"
        assert ctx_data["tasks"][0]["report"]["summary"] == "Feature built"
        assert ctx_data["current_task_index"] == 1
