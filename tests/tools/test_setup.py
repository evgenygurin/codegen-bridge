"""Tests for setup tools (list_orgs, list_repos)."""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from httpx import Response


class TestListOrgs:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_list_orgs" in names

    @respx.mock
    async def test_returns_organizations(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations").mock(
            return_value=Response(
                200,
                json={
                    "items": [{"id": 42, "name": "My Org"}],
                    "total": 1,
                },
            )
        )

        result = await client.call_tool("codegen_list_orgs", {})
        data = json.loads(result.data)
        assert data["organizations"][0]["id"] == 42
        assert data["organizations"][0]["name"] == "My Org"


class TestListRepos:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_list_repos" in names

    @respx.mock
    async def test_returns_repos(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": 10,
                            "name": "myrepo",
                            "full_name": "org/myrepo",
                            "language": "Python",
                            "setup_status": "completed",
                        }
                    ],
                    "total": 1,
                },
            )
        )

        result = await client.call_tool("codegen_list_repos", {})
        data = json.loads(result.data)
        assert data["total"] == 1
        assert data["repos"][0]["full_name"] == "org/myrepo"
