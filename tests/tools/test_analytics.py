"""Tests for run analytics tool."""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from httpx import Response


class TestGetRunAnalytics:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_run_analytics" in names

    @respx.mock
    async def test_returns_analytics(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/runs").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {"id": 1, "organization_id": 42, "status": "completed"},
                        {"id": 2, "organization_id": 42, "status": "completed"},
                        {"id": 3, "organization_id": 42, "status": "failed"},
                        {"id": 4, "organization_id": 42, "status": "running"},
                        {"id": 5, "organization_id": 42, "status": "queued"},
                    ],
                    "total": 5,
                    "page": 1,
                    "size": 100,
                    "pages": 1,
                },
            )
        )

        result = await client.call_tool("codegen_get_run_analytics", {})
        data = json.loads(result.data)
        assert data["organization_id"] == 42
        assert data["total_runs"] == 5
        assert data["completed"] == 2
        assert data["failed"] == 1
        # success_rate = 2 / (2 + 1) = 0.6667
        assert data["success_rate"] == round(2 / 3, 4)
        assert data["status_distribution"]["completed"] == 2
        assert data["status_distribution"]["failed"] == 1
        assert data["status_distribution"]["running"] == 1
        assert data["status_distribution"]["queued"] == 1

    @respx.mock
    async def test_empty_runs(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/runs").mock(
            return_value=Response(
                200,
                json={
                    "items": [],
                    "total": 0,
                    "page": 1,
                    "size": 100,
                    "pages": 0,
                },
            )
        )

        result = await client.call_tool("codegen_get_run_analytics", {})
        data = json.loads(result.data)
        assert data["total_runs"] == 0
        assert data["success_rate"] == 0.0
        assert data["status_distribution"] == {}

    @respx.mock
    async def test_all_completed(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/runs").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {"id": 1, "organization_id": 42, "status": "completed"},
                        {"id": 2, "organization_id": 42, "status": "completed"},
                    ],
                    "total": 2,
                    "page": 1,
                    "size": 100,
                    "pages": 1,
                },
            )
        )

        result = await client.call_tool("codegen_get_run_analytics", {})
        data = json.loads(result.data)
        assert data["success_rate"] == 1.0
        assert data["completed"] == 2
        assert data["failed"] == 0

    @respx.mock
    async def test_no_terminal_runs(self, client: Client):
        """Runs that are all in-progress should yield 0.0 success rate."""
        respx.get("https://api.codegen.com/v1/organizations/42/agent/runs").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {"id": 1, "organization_id": 42, "status": "running"},
                        {"id": 2, "organization_id": 42, "status": "queued"},
                    ],
                    "total": 2,
                    "page": 1,
                    "size": 100,
                    "pages": 1,
                },
            )
        )

        result = await client.call_tool("codegen_get_run_analytics", {})
        data = json.loads(result.data)
        assert data["success_rate"] == 0.0
        assert data["total_runs"] == 2
