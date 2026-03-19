"""Tests for background run monitoring tool (codegen_monitor_run_background).

Validates that:
- Tool is registered with correct tags and annotations
- Polling loop works: running → completed
- Already-terminal runs return immediately (0 polls)
- Timeout after max_polls
- All terminal statuses (completed, failed, error) stop the loop
- Only GET requests are made (pure read, no side effects)
"""

from __future__ import annotations

import json
import os

import pytest
import respx
from fastmcp import Client
from httpx import Response

os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "42"
os.environ["CODEGEN_ALLOW_DANGEROUS_TOOLS"] = "true"

from bridge.server import mcp


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEGEN_API_KEY", "test-key")
    monkeypatch.setenv("CODEGEN_ORG_ID", "42")
    monkeypatch.setenv("CODEGEN_ALLOW_DANGEROUS_TOOLS", "true")


@pytest.fixture
async def client():
    async with Client(mcp) as c:
        yield c


# ── Registration ─────────────────────────────────────────


class TestBackgroundRegistration:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_monitor_run_background" in names

    async def test_has_read_only_annotation(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_monitor_run_background")
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False

    async def test_does_not_break_other_tools(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        core = {
            "codegen_create_run",
            "codegen_get_run",
            "codegen_list_runs",
            "codegen_create_and_monitor",
        }
        assert core.issubset(names), f"Missing core tools: {core - names}"


# ── Happy Path ───────────────────────────────────────────


class TestMonitorRunHappyPath:
    @respx.mock
    async def test_completes_after_polling(self, client: Client):
        """Initial fetch (running) → poll (completed) → return."""
        get_route = respx.get(
            "https://api.codegen.com/v1/organizations/42/agent/run/600"
        )
        get_route.side_effect = [
            # Initial fetch
            Response(
                200,
                json={
                    "id": 600,
                    "organization_id": 42,
                    "status": "running",
                    "web_url": "https://codegen.com/runs/600",
                },
            ),
            # First poll — completed
            Response(
                200,
                json={
                    "id": 600,
                    "organization_id": 42,
                    "status": "completed",
                    "web_url": "https://codegen.com/runs/600",
                    "summary": "All done",
                    "result": "Success",
                },
            ),
        ]

        result = await client.call_tool(
            "codegen_monitor_run_background",
            {"run_id": 600, "poll_interval": 0.01, "max_polls": 10},
        )
        data = json.loads(result.data)

        assert data["id"] == 600
        assert data["status"] == "completed"
        assert data["summary"] == "All done"
        assert data["polls"] == 1

    @respx.mock
    async def test_returns_pr_data(self, client: Client):
        """Completed run with PRs should include pull_requests."""
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/601").mock(
            return_value=Response(
                200,
                json={
                    "id": 601,
                    "organization_id": 42,
                    "status": "completed",
                    "web_url": "https://codegen.com/runs/601",
                    "github_pull_requests": [
                        {
                            "url": "https://github.com/org/repo/pull/9",
                            "number": 9,
                            "title": "feat: new feature",
                            "state": "open",
                        }
                    ],
                },
            )
        )

        result = await client.call_tool(
            "codegen_monitor_run_background",
            {"run_id": 601, "poll_interval": 0.01},
        )
        data = json.loads(result.data)

        assert data["status"] == "completed"
        assert data["pull_requests"][0]["number"] == 9
        assert data["polls"] == 0  # Already terminal on initial fetch


# ── Already Terminal ─────────────────────────────────────


class TestAlreadyTerminal:
    @respx.mock
    async def test_completed_returns_immediately(self, client: Client):
        """Run already completed — 0 polls, immediate return."""
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/610").mock(
            return_value=Response(
                200,
                json={
                    "id": 610,
                    "organization_id": 42,
                    "status": "completed",
                    "web_url": "https://codegen.com/runs/610",
                },
            )
        )

        result = await client.call_tool(
            "codegen_monitor_run_background",
            {"run_id": 610, "poll_interval": 0.01},
        )
        data = json.loads(result.data)

        assert data["status"] == "completed"
        assert data["polls"] == 0

    @respx.mock
    async def test_failed_returns_immediately(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/611").mock(
            return_value=Response(
                200,
                json={
                    "id": 611,
                    "organization_id": 42,
                    "status": "failed",
                    "web_url": "https://codegen.com/runs/611",
                    "result": "Build error",
                },
            )
        )

        result = await client.call_tool(
            "codegen_monitor_run_background",
            {"run_id": 611, "poll_interval": 0.01},
        )
        data = json.loads(result.data)

        assert data["status"] == "failed"
        assert data["result"] == "Build error"
        assert data["polls"] == 0

    @respx.mock
    async def test_error_returns_immediately(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/612").mock(
            return_value=Response(
                200,
                json={
                    "id": 612,
                    "organization_id": 42,
                    "status": "error",
                    "web_url": "https://codegen.com/runs/612",
                },
            )
        )

        result = await client.call_tool(
            "codegen_monitor_run_background",
            {"run_id": 612, "poll_interval": 0.01},
        )
        data = json.loads(result.data)

        assert data["status"] == "error"
        assert data["polls"] == 0


# ── Timeout ──────────────────────────────────────────────


class TestMonitorTimeout:
    @respx.mock
    async def test_timeout_after_max_polls(self, client: Client):
        """Should return timeout when max_polls is reached."""
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/620").mock(
            return_value=Response(
                200,
                json={
                    "id": 620,
                    "organization_id": 42,
                    "status": "running",
                    "web_url": "https://codegen.com/runs/620",
                },
            )
        )

        result = await client.call_tool(
            "codegen_monitor_run_background",
            {"run_id": 620, "poll_interval": 0.01, "max_polls": 3},
        )
        data = json.loads(result.data)

        assert data["timeout"] is True
        assert data["run_id"] == 620
        assert data["last_status"] == "running"
        assert data["polls"] == 3


# ── Terminal Statuses in Poll Loop ───────────────────────


class TestTerminalStatusesInLoop:
    @respx.mock
    async def test_failed_stops_loop(self, client: Client):
        get_route = respx.get(
            "https://api.codegen.com/v1/organizations/42/agent/run/630"
        )
        get_route.side_effect = [
            Response(200, json={"id": 630, "organization_id": 42, "status": "running",
                                "web_url": "https://codegen.com/runs/630"}),
            Response(200, json={"id": 630, "organization_id": 42, "status": "failed",
                                "web_url": "https://codegen.com/runs/630",
                                "result": "Crash"}),
        ]

        result = await client.call_tool(
            "codegen_monitor_run_background",
            {"run_id": 630, "poll_interval": 0.01, "max_polls": 10},
        )
        data = json.loads(result.data)

        assert data["status"] == "failed"
        assert data["polls"] == 1

    @respx.mock
    async def test_error_stops_loop(self, client: Client):
        get_route = respx.get(
            "https://api.codegen.com/v1/organizations/42/agent/run/631"
        )
        get_route.side_effect = [
            Response(200, json={"id": 631, "organization_id": 42, "status": "running",
                                "web_url": "https://codegen.com/runs/631"}),
            Response(200, json={"id": 631, "organization_id": 42, "status": "error",
                                "web_url": "https://codegen.com/runs/631"}),
        ]

        result = await client.call_tool(
            "codegen_monitor_run_background",
            {"run_id": 631, "poll_interval": 0.01, "max_polls": 10},
        )
        data = json.loads(result.data)

        assert data["status"] == "error"
        assert data["polls"] == 1


# ── Pure Read (No Side Effects) ──────────────────────────


class TestPureRead:
    @respx.mock
    async def test_only_get_requests(self, client: Client):
        """Monitor should only use GET — no POST/PUT mutations."""
        get_route = respx.get(
            "https://api.codegen.com/v1/organizations/42/agent/run/640"
        )
        get_route.side_effect = [
            Response(200, json={"id": 640, "organization_id": 42, "status": "running",
                                "web_url": "https://codegen.com/runs/640"}),
            Response(200, json={"id": 640, "organization_id": 42, "status": "running",
                                "web_url": "https://codegen.com/runs/640"}),
            Response(200, json={"id": 640, "organization_id": 42, "status": "completed",
                                "web_url": "https://codegen.com/runs/640"}),
        ]

        await client.call_tool(
            "codegen_monitor_run_background",
            {"run_id": 640, "poll_interval": 0.01, "max_polls": 10},
        )

        # 1 initial fetch + 2 polls = 3 GET requests, 0 POST
        assert get_route.call_count == 3


# ── TaskConfig metadata ─────────────────────────────────


class TestMonitorTaskConfig:
    """Verify the tool uses MONITOR_TASK configuration."""

    def test_monitor_task_is_optional(self):
        from bridge.tools.agent._progress import MONITOR_TASK
        assert MONITOR_TASK.mode == "optional"

    def test_monitor_task_supports_tasks(self):
        from bridge.tools.agent._progress import MONITOR_TASK
        assert MONITOR_TASK.supports_tasks() is True
