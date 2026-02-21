"""Tests for setup tools (list_orgs, list_repos, users)."""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from httpx import Response

_SAMPLE_USER = {
    "id": 7,
    "github_user_id": "12345",
    "github_username": "octocat",
    "email": "octocat@github.com",
    "avatar_url": "https://avatars.githubusercontent.com/u/12345",
    "full_name": "Octo Cat",
    "role": "ADMIN",
    "is_admin": True,
}

_SAMPLE_USER_2 = {
    "id": 8,
    "github_user_id": "67890",
    "github_username": "hubot",
    "email": "hubot@github.com",
    "avatar_url": "https://avatars.githubusercontent.com/u/67890",
    "full_name": "Hu Bot",
    "role": "MEMBER",
    "is_admin": False,
}


# ── Users ──────────────────────────────────────────────────


class TestGetCurrentUser:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_current_user" in names

    @respx.mock
    async def test_returns_current_user(self, client: Client):
        respx.get("https://api.codegen.com/v1/users/me").mock(
            return_value=Response(200, json=_SAMPLE_USER)
        )

        result = await client.call_tool("codegen_get_current_user", {})
        data = json.loads(result.data)
        assert data["user"]["id"] == 7
        assert data["user"]["github_username"] == "octocat"
        assert data["user"]["email"] == "octocat@github.com"
        assert data["user"]["role"] == "ADMIN"
        assert data["user"]["is_admin"] is True


class TestListUsers:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_list_users" in names

    @respx.mock
    async def test_returns_users(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/users").mock(
            return_value=Response(
                200,
                json={
                    "items": [_SAMPLE_USER, _SAMPLE_USER_2],
                    "total": 2,
                },
            )
        )

        result = await client.call_tool("codegen_list_users", {})
        data = json.loads(result.data)
        assert data["total"] == 2
        assert len(data["users"]) == 2
        assert data["users"][0]["github_username"] == "octocat"
        assert data["users"][1]["github_username"] == "hubot"

    @respx.mock
    async def test_pagination(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/users").mock(
            return_value=Response(
                200,
                json={
                    "items": [_SAMPLE_USER],
                    "total": 5,
                },
            )
        )

        result = await client.call_tool("codegen_list_users", {"limit": 1})
        data = json.loads(result.data)
        assert data["total"] == 5
        assert len(data["users"]) == 1
        assert "next_cursor" in data


class TestGetUser:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_user" in names

    @respx.mock
    async def test_returns_user_by_id(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/users/7").mock(
            return_value=Response(200, json=_SAMPLE_USER)
        )

        result = await client.call_tool("codegen_get_user", {"user_id": 7})
        data = json.loads(result.data)
        assert data["user"]["id"] == 7
        assert data["user"]["github_username"] == "octocat"
        assert data["user"]["full_name"] == "Octo Cat"


# ── Organizations & Repos ──────────────────────────────────


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
