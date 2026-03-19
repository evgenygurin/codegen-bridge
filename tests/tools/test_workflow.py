"""Tests for workflow composition tools (create_and_monitor)."""

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


class TestWorkflowRegistration:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_create_and_monitor" in names

    async def test_has_workflow_tag(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_create_and_monitor")
        assert tool.annotations is not None
        # CREATES annotation: not read-only, not destructive
        assert tool.annotations.readOnlyHint is False
        assert tool.annotations.destructiveHint is False


# ── Happy Path ───────────────────────────────────────────


class TestCreateAndMonitorHappyPath:
    """Workflow creates a run, polls, and returns completed result."""

    @respx.mock
    async def test_completes_after_polling(self, client: Client):
        """Create → poll (running) → poll (completed) → return."""
        # Mock create
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={
                    "id": 500,
                    "organization_id": 42,
                    "status": "queued",
                    "web_url": "https://codegen.com/runs/500",
                },
            )
        )

        # Mock get_run — first call returns running, second returns completed
        get_route = respx.get(
            "https://api.codegen.com/v1/organizations/42/agent/run/500"
        )
        get_route.side_effect = [
            Response(
                200,
                json={
                    "id": 500,
                    "organization_id": 42,
                    "status": "running",
                    "web_url": "https://codegen.com/runs/500",
                },
            ),
            Response(
                200,
                json={
                    "id": 500,
                    "organization_id": 42,
                    "status": "completed",
                    "web_url": "https://codegen.com/runs/500",
                    "summary": "Task done",
                    "result": "All good",
                },
            ),
        ]

        result = await client.call_tool(
            "codegen_create_and_monitor",
            {
                "prompt": "Fix the bug",
                "repo_id": 10,
                "poll_interval": 0.01,  # fast polling for test
                "max_polls": 10,
            },
        )
        data = json.loads(result.data)

        assert data["id"] == 500
        assert data["status"] == "completed"
        assert data["summary"] == "Task done"
        assert data["polls"] == 2  # took 2 polls to complete

    @respx.mock
    async def test_returns_pr_data(self, client: Client):
        """Completed run with PRs should include pull_requests."""
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={
                    "id": 501,
                    "organization_id": 42,
                    "status": "queued",
                    "web_url": "https://codegen.com/runs/501",
                },
            )
        )
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/501").mock(
            return_value=Response(
                200,
                json={
                    "id": 501,
                    "organization_id": 42,
                    "status": "completed",
                    "web_url": "https://codegen.com/runs/501",
                    "github_pull_requests": [
                        {
                            "url": "https://github.com/org/repo/pull/7",
                            "number": 7,
                            "title": "feat: auth",
                            "state": "open",
                        }
                    ],
                },
            )
        )

        result = await client.call_tool(
            "codegen_create_and_monitor",
            {"prompt": "Add auth", "repo_id": 10, "poll_interval": 0.01},
        )
        data = json.loads(result.data)

        assert data["status"] == "completed"
        assert data["pull_requests"][0]["number"] == 7
        assert data["polls"] == 1


# ── Failure / Edge Cases ─────────────────────────────────


class TestCreateAndMonitorEdgeCases:
    @respx.mock
    async def test_handles_failed_run(self, client: Client):
        """Run that fails should return immediately."""
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={
                    "id": 502,
                    "organization_id": 42,
                    "status": "queued",
                    "web_url": "https://codegen.com/runs/502",
                },
            )
        )
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/502").mock(
            return_value=Response(
                200,
                json={
                    "id": 502,
                    "organization_id": 42,
                    "status": "failed",
                    "web_url": "https://codegen.com/runs/502",
                    "result": "Syntax error in file.py",
                },
            )
        )

        result = await client.call_tool(
            "codegen_create_and_monitor",
            {"prompt": "Fix it", "repo_id": 10, "poll_interval": 0.01},
        )
        data = json.loads(result.data)

        assert data["status"] == "failed"
        assert data["result"] == "Syntax error in file.py"
        assert data["polls"] == 1

    @respx.mock
    async def test_timeout_after_max_polls(self, client: Client):
        """Should return timeout when max_polls is reached."""
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={
                    "id": 503,
                    "organization_id": 42,
                    "status": "queued",
                    "web_url": "https://codegen.com/runs/503",
                },
            )
        )
        # Always running — never completes
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/503").mock(
            return_value=Response(
                200,
                json={
                    "id": 503,
                    "organization_id": 42,
                    "status": "running",
                    "web_url": "https://codegen.com/runs/503",
                },
            )
        )

        result = await client.call_tool(
            "codegen_create_and_monitor",
            {
                "prompt": "Long task",
                "repo_id": 10,
                "poll_interval": 0.01,
                "max_polls": 3,
            },
        )
        data = json.loads(result.data)

        assert data["timeout"] is True
        assert data["run_id"] == 503
        assert data["last_status"] == "running"
        assert data["polls"] == 3

    @respx.mock
    async def test_error_status_is_terminal(self, client: Client):
        """Error status should also terminate the loop."""
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200,
                json={
                    "id": 504,
                    "organization_id": 42,
                    "status": "queued",
                    "web_url": "https://codegen.com/runs/504",
                },
            )
        )
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/504").mock(
            return_value=Response(
                200,
                json={
                    "id": 504,
                    "organization_id": 42,
                    "status": "error",
                    "web_url": "https://codegen.com/runs/504",
                },
            )
        )

        result = await client.call_tool(
            "codegen_create_and_monitor",
            {"prompt": "Broken", "repo_id": 10, "poll_interval": 0.01},
        )
        data = json.loads(result.data)

        assert data["status"] == "error"
        assert data["polls"] == 1


# ── No Side Effects ──────────────────────────────────────


class TestWorkflowNoSideEffects:
    """Polling should use pure reads — no execution context mutations."""

    @respx.mock
    async def test_polling_uses_get_not_report(self, client: Client):
        """Verify GET is called (pure read), not POST/PUT (mutation)."""
        create_route = respx.post(
            "https://api.codegen.com/v1/organizations/42/agent/run"
        ).mock(
            return_value=Response(
                200,
                json={
                    "id": 505,
                    "organization_id": 42,
                    "status": "queued",
                    "web_url": "https://codegen.com/runs/505",
                },
            )
        )
        get_route = respx.get(
            "https://api.codegen.com/v1/organizations/42/agent/run/505"
        )
        get_route.side_effect = [
            Response(
                200,
                json={
                    "id": 505,
                    "organization_id": 42,
                    "status": "running",
                    "web_url": "https://codegen.com/runs/505",
                },
            ),
            Response(
                200,
                json={
                    "id": 505,
                    "organization_id": 42,
                    "status": "running",
                    "web_url": "https://codegen.com/runs/505",
                },
            ),
            Response(
                200,
                json={
                    "id": 505,
                    "organization_id": 42,
                    "status": "completed",
                    "web_url": "https://codegen.com/runs/505",
                },
            ),
        ]

        await client.call_tool(
            "codegen_create_and_monitor",
            {"prompt": "Test", "repo_id": 10, "poll_interval": 0.01},
        )

        # 1 POST (create) + 3 GET (polls) = 4 total requests
        assert create_route.call_count == 1
        assert get_route.call_count == 3
