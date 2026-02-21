"""Tests for background task support and progress reporting.

Validates that:
- codegen_create_run and codegen_get_logs are configured as optional background tasks
- TaskConfig has correct mode and poll_interval settings
- Progress reporting calls are made during tool execution
- The _report helper is resilient (never raises)
- Tools still work synchronously (mode="optional" fallback)
"""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import AsyncMock

import respx
from fastmcp import Client
from httpx import Response

from bridge.tools.agent import (
    _CREATE_RUN_STEPS,
    _GET_LOGS_STEPS,
    CREATE_RUN_TASK,
    GET_LOGS_TASK,
    _report,
)

# ── TaskConfig constant tests ────────────────────────────


class TestTaskConfigConstants:
    """Verify TaskConfig declarations for task-enabled tools."""

    def test_create_run_task_is_optional(self):
        assert CREATE_RUN_TASK.mode == "optional"

    def test_create_run_task_supports_tasks(self):
        assert CREATE_RUN_TASK.supports_tasks() is True

    def test_create_run_task_poll_interval(self):
        assert CREATE_RUN_TASK.poll_interval == timedelta(seconds=5)

    def test_get_logs_task_is_optional(self):
        assert GET_LOGS_TASK.mode == "optional"

    def test_get_logs_task_supports_tasks(self):
        assert GET_LOGS_TASK.supports_tasks() is True

    def test_get_logs_task_poll_interval(self):
        assert GET_LOGS_TASK.poll_interval == timedelta(seconds=3)

    def test_create_run_steps_count(self):
        assert _CREATE_RUN_STEPS == 5

    def test_get_logs_steps_count(self):
        assert _GET_LOGS_STEPS == 3

    def test_create_run_task_is_not_required(self):
        """mode=optional means sync fallback is available."""
        assert CREATE_RUN_TASK.mode != "required"

    def test_get_logs_task_is_not_required(self):
        assert GET_LOGS_TASK.mode != "required"

    def test_get_logs_polls_faster_than_create_run(self):
        """Log fetch is simpler; it should poll more frequently."""
        assert GET_LOGS_TASK.poll_interval < CREATE_RUN_TASK.poll_interval


# ── _report helper unit tests ────────────────────────────


class TestReportHelper:
    """Test the _report best-effort progress helper."""

    async def test_report_calls_report_progress(self):
        ctx = AsyncMock()
        ctx.report_progress = AsyncMock()

        await _report(ctx, 2, 5, "Working")

        ctx.report_progress.assert_awaited_once_with(
            progress=2, total=5, message="Working"
        )

    async def test_report_never_raises_on_runtime_error(self):
        ctx = AsyncMock()
        ctx.report_progress = AsyncMock(side_effect=RuntimeError("no progress token"))

        # Should NOT raise
        await _report(ctx, 1, 3, "Test")

    async def test_report_never_raises_on_attribute_error(self):
        ctx = AsyncMock()
        ctx.report_progress = AsyncMock(side_effect=AttributeError("missing"))

        await _report(ctx, 0, 1, "Start")

    async def test_report_never_raises_on_exception(self):
        ctx = AsyncMock()
        ctx.report_progress = AsyncMock(side_effect=Exception("generic"))

        await _report(ctx, 3, 10, "Mid-way")

    async def test_report_with_zero_progress(self):
        ctx = AsyncMock()
        ctx.report_progress = AsyncMock()

        await _report(ctx, 0, 10, "Initializing")

        ctx.report_progress.assert_awaited_once_with(
            progress=0, total=10, message="Initializing"
        )

    async def test_report_with_completion(self):
        ctx = AsyncMock()
        ctx.report_progress = AsyncMock()

        await _report(ctx, 5, 5, "Done")

        ctx.report_progress.assert_awaited_once_with(
            progress=5, total=5, message="Done"
        )

    async def test_report_passes_float_values(self):
        ctx = AsyncMock()
        ctx.report_progress = AsyncMock()

        await _report(ctx, 2.5, 10.0, "Partial")

        ctx.report_progress.assert_awaited_once_with(
            progress=2.5, total=10.0, message="Partial"
        )


# ── Tool metadata tests ─────────────────────────────────


class TestToolTaskMetadata:
    """Verify task-enabled tools expose correct metadata."""

    async def test_create_run_still_has_description(self, client: Client):
        tools = await client.list_tools()
        create_tool = next(t for t in tools if t.name == "codegen_create_run")
        assert "agent run" in create_tool.description.lower()
        assert "background" in create_tool.description.lower()

    async def test_get_logs_still_has_description(self, client: Client):
        tools = await client.list_tools()
        logs_tool = next(t for t in tools if t.name == "codegen_get_logs")
        assert "logs" in logs_tool.description.lower()
        assert "background" in logs_tool.description.lower()

    async def test_non_task_tools_unchanged(self, client: Client):
        """Ensure tools that are NOT task-enabled still register correctly."""
        tools = await client.list_tools()
        names = {t.name for t in tools}
        non_task_tools = {
            "codegen_get_run",
            "codegen_list_runs",
            "codegen_resume_run",
            "codegen_stop_run",
        }
        assert non_task_tools.issubset(names)

    async def test_all_core_tools_still_present(self, client: Client):
        """Adding task= to some tools must not break registration of others."""
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


# ── Synchronous fallback tests ───────────────────────────


class TestSynchronousFallback:
    """Test that task-enabled tools still work synchronously (mode=optional)."""

    @respx.mock
    async def test_create_run_works_synchronously(self, client: Client):
        """Calling without task=True should work normally (synchronous)."""
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={
                    "id": 50,
                    "status": "queued",
                    "web_url": "https://codegen.com/run/50",
                },
            )
        )
        respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )

        result = await client.call_tool(
            "codegen_create_run",
            {"prompt": "Sync test", "repo_id": 10},
        )
        data = json.loads(result.data)
        assert data["id"] == 50
        assert data["status"] == "queued"

    @respx.mock
    async def test_get_logs_works_synchronously(self, client: Client):
        """Calling without task=True should work normally (synchronous)."""
        respx.get(
            "https://api.codegen.com/v1/alpha/organizations/42/agent/run/50/logs"
        ).mock(
            return_value=Response(
                200,
                json={
                    "id": 50,
                    "status": "completed",
                    "logs": [],
                    "total_logs": 0,
                },
            )
        )

        result = await client.call_tool(
            "codegen_get_logs",
            {"run_id": 50},
        )
        data = json.loads(result.data)
        assert data["run_id"] == 50
        assert data["total_logs"] == 0

    @respx.mock
    async def test_create_run_returns_correct_structure(self, client: Client):
        """Verify task-enabled create_run returns the expected JSON keys."""
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={
                    "id": 77,
                    "status": "running",
                    "web_url": "https://codegen.com/run/77",
                },
            )
        )
        respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )

        result = await client.call_tool(
            "codegen_create_run",
            {"prompt": "Check structure", "repo_id": 10},
        )
        data = json.loads(result.data)
        assert set(data.keys()) == {"id", "status", "web_url"}
        assert data["web_url"] == "https://codegen.com/run/77"

    @respx.mock
    async def test_get_logs_returns_correct_structure(self, client: Client):
        """Verify task-enabled get_logs returns the expected JSON keys."""
        respx.get(
            "https://api.codegen.com/v1/alpha/organizations/42/agent/run/77/logs"
        ).mock(
            return_value=Response(
                200,
                json={
                    "id": 77,
                    "status": "running",
                    "logs": [
                        {"agent_run_id": 77, "thought": "Analyzing"},
                    ],
                    "total_logs": 1,
                },
            )
        )

        result = await client.call_tool(
            "codegen_get_logs",
            {"run_id": 77},
        )
        data = json.loads(result.data)
        assert set(data.keys()) == {"run_id", "status", "total_logs", "next_cursor", "logs"}
        assert len(data["logs"]) == 1
        assert data["logs"][0]["thought"] == "Analyzing"
