"""Tests for pull-request management tools (edit PR, edit PR simple)."""

from __future__ import annotations

import json

import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError
from httpx import Response

# ── codegen_edit_pr (RESTful) ──────────────────────────────


class TestEditPR:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_edit_pr" in names

    @respx.mock
    async def test_edit_pr_open(self, client: Client):
        respx.patch(
            "https://api.codegen.com/v1/organizations/42/repos/10/prs/5"
        ).mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "url": "https://github.com/org/repo/pull/5",
                    "number": 5,
                    "title": "Fix bug",
                    "state": "open",
                },
            )
        )

        result = await client.call_tool(
            "codegen_edit_pr",
            {"repo_id": 10, "pr_id": 5, "state": "open"},
        )
        data = json.loads(result.data)
        assert data["success"] is True
        assert data["url"] == "https://github.com/org/repo/pull/5"
        assert data["number"] == 5
        assert data["title"] == "Fix bug"
        assert data["state"] == "open"

    @respx.mock
    async def test_edit_pr_closed(self, client: Client):
        respx.patch(
            "https://api.codegen.com/v1/organizations/42/repos/20/prs/15"
        ).mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "url": "https://github.com/org/repo/pull/15",
                    "number": 15,
                    "title": "Fix bug",
                    "state": "closed",
                },
            )
        )

        result = await client.call_tool(
            "codegen_edit_pr",
            {"repo_id": 20, "pr_id": 15, "state": "closed"},
        )
        data = json.loads(result.data)
        assert data["success"] is True
        assert data["state"] == "closed"

    @respx.mock
    async def test_edit_pr_draft(self, client: Client):
        respx.patch(
            "https://api.codegen.com/v1/organizations/42/repos/20/prs/16"
        ).mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "state": "draft",
                },
            )
        )

        result = await client.call_tool(
            "codegen_edit_pr",
            {"repo_id": 20, "pr_id": 16, "state": "draft"},
        )
        data = json.loads(result.data)
        assert data["success"] is True
        assert data["state"] == "draft"

    @respx.mock
    async def test_edit_pr_ready_for_review(self, client: Client):
        respx.patch(
            "https://api.codegen.com/v1/organizations/42/repos/20/prs/17"
        ).mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "state": "open",
                },
            )
        )

        result = await client.call_tool(
            "codegen_edit_pr",
            {"repo_id": 20, "pr_id": 17, "state": "ready_for_review"},
        )
        data = json.loads(result.data)
        assert data["success"] is True

    @respx.mock
    async def test_edit_pr_with_error(self, client: Client):
        respx.patch(
            "https://api.codegen.com/v1/organizations/42/repos/10/prs/999"
        ).mock(
            return_value=Response(
                200,
                json={
                    "success": False,
                    "error": "PR not found",
                },
            )
        )

        result = await client.call_tool(
            "codegen_edit_pr",
            {"repo_id": 10, "pr_id": 999, "state": "open"},
        )
        data = json.loads(result.data)
        assert data["success"] is False
        assert data["error"] == "PR not found"

    @respx.mock
    async def test_edit_pr_omits_null_fields(self, client: Client):
        respx.patch(
            "https://api.codegen.com/v1/organizations/42/repos/30/prs/50"
        ).mock(
            return_value=Response(
                200,
                json={"success": True},
            )
        )

        result = await client.call_tool(
            "codegen_edit_pr",
            {"repo_id": 30, "pr_id": 50, "state": "open"},
        )
        data = json.loads(result.data)
        assert data == {"success": True}
        # None fields should not appear in output
        assert "url" not in data
        assert "number" not in data
        assert "title" not in data
        assert "state" not in data
        assert "error" not in data

    @respx.mock
    async def test_edit_pr_http_error(self, client: Client):
        respx.patch(
            "https://api.codegen.com/v1/organizations/42/repos/30/prs/51"
        ).mock(return_value=Response(422, json={"detail": "Validation error"}))

        with pytest.raises(ToolError):
            await client.call_tool(
                "codegen_edit_pr",
                {"repo_id": 30, "pr_id": 51, "state": "open"},
            )


# ── codegen_edit_pr_simple ──────────────────────────────────


class TestEditPRSimple:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_edit_pr_simple" in names

    @respx.mock
    async def test_edit_pr_simple_open(self, client: Client):
        respx.patch("https://api.codegen.com/v1/organizations/42/prs/100").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "url": "https://github.com/org/repo/pull/100",
                    "number": 100,
                    "title": "Fix bug",
                    "state": "open",
                },
            )
        )

        result = await client.call_tool(
            "codegen_edit_pr_simple",
            {"pr_id": 100, "state": "open"},
        )
        data = json.loads(result.data)
        assert data["success"] is True
        assert data["url"] == "https://github.com/org/repo/pull/100"
        assert data["number"] == 100
        assert data["title"] == "Fix bug"
        assert data["state"] == "open"

    @respx.mock
    async def test_edit_pr_simple_closed(self, client: Client):
        respx.patch("https://api.codegen.com/v1/organizations/42/prs/101").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "state": "closed",
                },
            )
        )

        result = await client.call_tool(
            "codegen_edit_pr_simple",
            {"pr_id": 101, "state": "closed"},
        )
        data = json.loads(result.data)
        assert data["success"] is True
        assert data["state"] == "closed"

    @respx.mock
    async def test_edit_pr_simple_draft(self, client: Client):
        respx.patch("https://api.codegen.com/v1/organizations/42/prs/102").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "state": "draft",
                },
            )
        )

        result = await client.call_tool(
            "codegen_edit_pr_simple",
            {"pr_id": 102, "state": "draft"},
        )
        data = json.loads(result.data)
        assert data["success"] is True
        assert data["state"] == "draft"

    @respx.mock
    async def test_edit_pr_simple_ready_for_review(self, client: Client):
        respx.patch("https://api.codegen.com/v1/organizations/42/prs/103").mock(
            return_value=Response(
                200,
                json={
                    "success": True,
                    "state": "open",
                },
            )
        )

        result = await client.call_tool(
            "codegen_edit_pr_simple",
            {"pr_id": 103, "state": "ready_for_review"},
        )
        data = json.loads(result.data)
        assert data["success"] is True

    @respx.mock
    async def test_edit_pr_simple_with_error(self, client: Client):
        respx.patch("https://api.codegen.com/v1/organizations/42/prs/999").mock(
            return_value=Response(
                200,
                json={
                    "success": False,
                    "error": "PR not found",
                },
            )
        )

        result = await client.call_tool(
            "codegen_edit_pr_simple",
            {"pr_id": 999, "state": "open"},
        )
        data = json.loads(result.data)
        assert data["success"] is False
        assert data["error"] == "PR not found"

    @respx.mock
    async def test_edit_pr_simple_omits_null_fields(self, client: Client):
        respx.patch("https://api.codegen.com/v1/organizations/42/prs/200").mock(
            return_value=Response(
                200,
                json={"success": True},
            )
        )

        result = await client.call_tool(
            "codegen_edit_pr_simple",
            {"pr_id": 200, "state": "open"},
        )
        data = json.loads(result.data)
        assert data == {"success": True}
        assert "url" not in data
        assert "error" not in data

    @respx.mock
    async def test_edit_pr_simple_http_error(self, client: Client):
        respx.patch("https://api.codegen.com/v1/organizations/42/prs/201").mock(
            return_value=Response(429, json={"detail": "Rate limited"})
        )

        with pytest.raises(ToolError):
            await client.call_tool(
                "codegen_edit_pr_simple",
                {"pr_id": 201, "state": "open"},
            )
