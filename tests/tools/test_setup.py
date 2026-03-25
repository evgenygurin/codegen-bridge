"""Tests for setup tools (list_orgs, list_repos, users, generate_setup_commands,
MCP providers, OAuth, check suite settings).
"""

from __future__ import annotations

import json

import pytest
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


class TestGetOrganizationSettings:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_organization_settings" in names

    @respx.mock
    async def test_returns_settings(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/settings").mock(
            return_value=Response(
                200,
                json={
                    "enable_pr_creation": False,
                    "enable_rules_detection": True,
                },
            )
        )

        result = await client.call_tool("codegen_get_organization_settings", {})
        data = json.loads(result.data)
        assert data["enable_pr_creation"] is False
        assert data["enable_rules_detection"] is True


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


class TestGenerateSetupCommands:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_generate_setup_commands" in names

    @respx.mock
    async def test_generates_setup_commands(self, client: Client):
        respx.post("https://api.codegen.com/v1/organizations/42/setup-commands/generate").mock(
            return_value=Response(
                200,
                json={
                    "agent_run_id": 99,
                    "status": "queued",
                    "url": "https://codegen.com/run/99",
                },
            )
        )

        result = await client.call_tool(
            "codegen_generate_setup_commands",
            {"repo_id": 10},
        )
        data = json.loads(result.data)
        assert data["agent_run_id"] == 99
        assert data["status"] == "queued"
        assert data["url"] == "https://codegen.com/run/99"

    @respx.mock
    async def test_generates_with_custom_prompt(self, client: Client):
        respx.post("https://api.codegen.com/v1/organizations/42/setup-commands/generate").mock(
            return_value=Response(
                200,
                json={
                    "agent_run_id": 100,
                    "status": "queued",
                    "url": "https://codegen.com/run/100",
                },
            )
        )

        result = await client.call_tool(
            "codegen_generate_setup_commands",
            {"repo_id": 10, "prompt": "Include Docker setup"},
        )
        data = json.loads(result.data)
        assert data["agent_run_id"] == 100


class TestGetMCPProviders:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_mcp_providers" in names

    @respx.mock
    async def test_returns_providers(self, client: Client):
        respx.get("https://api.codegen.com/v1/mcp-providers").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "github",
                        "issuer": "https://github.com",
                        "authorization_endpoint": "https://github.com/login/oauth/authorize",
                        "token_endpoint": "https://github.com/login/oauth/access_token",
                        "default_scopes": ["repo", "read:org"],
                        "is_mcp": True,
                    },
                    {
                        "id": 2,
                        "name": "linear",
                        "issuer": "https://linear.app",
                        "authorization_endpoint": "https://linear.app/oauth/authorize",
                        "token_endpoint": "https://api.linear.app/oauth/token",
                        "default_scopes": ["read"],
                        "is_mcp": True,
                    },
                ],
            )
        )

        result = await client.call_tool("codegen_get_mcp_providers", {})
        data = json.loads(result.data)
        assert data["total"] == 2
        assert data["providers"][0]["name"] == "github"
        assert data["providers"][0]["issuer"] == "https://github.com"
        assert data["providers"][1]["name"] == "linear"


class TestGetOAuthStatus:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_oauth_status" in names

    @respx.mock
    async def test_returns_connected_providers(self, client: Client):
        respx.get("https://api.codegen.com/v1/oauth/tokens/status").mock(
            return_value=Response(200, json=["github", "linear"])
        )

        result = await client.call_tool("codegen_get_oauth_status", {})
        data = json.loads(result.data)
        assert data["total"] == 2
        assert data["connected_providers"][0]["provider"] == "github"
        assert data["connected_providers"][0]["active"] is True
        assert data["connected_providers"][1]["provider"] == "linear"


# ── Check Suite Settings ──────────────────────────────────


class TestGetCheckSuiteSettings:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_check_suite_settings" in names

    @respx.mock
    async def test_returns_settings(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/repos/check-suite-settings").mock(
            return_value=Response(
                200,
                json={
                    "check_retry_count": 3,
                    "ignored_checks": ["lint"],
                    "check_retry_counts": {"ci": 2},
                    "custom_prompts": {"ci": "Fix CI"},
                    "high_priority_apps": ["GitHub Actions"],
                    "available_check_suite_names": ["ci", "lint", "test"],
                },
            )
        )

        result = await client.call_tool(
            "codegen_get_check_suite_settings",
            {"repo_id": 10},
        )
        data = json.loads(result.data)
        assert data["check_retry_count"] == 3
        assert data["ignored_checks"] == ["lint"]
        assert data["check_retry_counts"] == {"ci": 2}
        assert data["custom_prompts"] == {"ci": "Fix CI"}
        assert data["high_priority_apps"] == ["GitHub Actions"]
        assert data["available_check_suite_names"] == ["ci", "lint", "test"]


class TestUpdateCheckSuiteSettings:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_update_check_suite_settings" in names

    @respx.mock
    async def test_updates_settings(self, client: Client):
        respx.put("https://api.codegen.com/v1/organizations/42/repos/check-suite-settings").mock(
            return_value=Response(200, json={"status": "ok"})
        )

        result = await client.call_tool(
            "codegen_update_check_suite_settings",
            {"repo_id": 10, "check_retry_count": 5, "ignored_checks": ["lint"]},
        )
        data = json.loads(result.data)
        assert data["status"] == "updated"
        assert data["result"]["status"] == "ok"

    @respx.mock
    async def test_updates_single_field(self, client: Client):
        respx.put("https://api.codegen.com/v1/organizations/42/repos/check-suite-settings").mock(
            return_value=Response(200, json={"status": "ok"})
        )

        result = await client.call_tool(
            "codegen_update_check_suite_settings",
            {"repo_id": 10, "check_retry_count": 2},
        )
        data = json.loads(result.data)
        assert data["status"] == "updated"

    async def test_rejects_empty_update(self, client: Client):
        """Calling update with no setting fields raises ToolError."""
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="At least one setting field"):
            await client.call_tool(
                "codegen_update_check_suite_settings",
                {"repo_id": 10},
            )


class TestRevokeOAuth:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_revoke_oauth" in names

    @respx.mock
    async def test_revokes_token_confirmed(self, client: Client):
        route = respx.post("https://api.codegen.com/v1/oauth/tokens/revoke").mock(
            return_value=Response(200, json={"status": "revoked"})
        )

        result = await client.call_tool(
            "codegen_revoke_oauth",
            {"provider": "github", "confirmed": True},
        )
        data = json.loads(result.data)
        assert data["action"] == "revoked"
        assert data["provider"] == "github"
        assert route.called

    @respx.mock
    async def test_revoke_proceeds_when_elicitation_unsupported(self, client: Client):
        """When elicitation is unsupported, confirm_action defaults to True."""
        route = respx.post("https://api.codegen.com/v1/oauth/tokens/revoke").mock(
            return_value=Response(200, json={"status": "revoked"})
        )

        result = await client.call_tool(
            "codegen_revoke_oauth",
            {"provider": "slack"},
        )
        data = json.loads(result.data)
        assert data["action"] == "revoked"
        assert data["provider"] == "slack"
        assert route.called

    async def test_revoke_tagged_as_dangerous(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_revoke_oauth")
        tags = tool.meta.get("fastmcp", {}).get("tags", [])
        assert "dangerous" in tags


# ── Repository Rules ──────────────────────────────────────


class TestGetRepositoryRules:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_repository_rules" in names

    @respx.mock
    async def test_returns_rules(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/cli/rules").mock(
            return_value=Response(
                200,
                json={
                    "organization_rules": "Always use TypeScript strict mode",
                    "user_custom_prompt": "Prefer functional style",
                },
            )
        )

        result = await client.call_tool("codegen_get_repository_rules", {})
        data = json.loads(result.data)
        assert data["organization_rules"] == "Always use TypeScript strict mode"
        assert data["user_custom_prompt"] == "Prefer functional style"
        assert "AGENTS.md" in data["auto_detected_patterns"]
        assert data["max_budget_chars"] == 25_000
        assert "docs.codegen.com" in data["documentation_url"]

    @respx.mock
    async def test_returns_empty_rules(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/cli/rules").mock(
            return_value=Response(
                200,
                json={
                    "organization_rules": "",
                    "user_custom_prompt": None,
                },
            )
        )

        result = await client.call_tool("codegen_get_repository_rules", {})
        data = json.loads(result.data)
        assert data["organization_rules"] is None
        assert data["user_custom_prompt"] is None


class TestConfigureRepositoryRules:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_configure_repository_rules" in names

    async def test_returns_guidance(self, client: Client):
        result = await client.call_tool(
            "codegen_configure_repository_rules",
            {"org_name": "my-org", "repo_name": "my-repo"},
        )
        data = json.loads(result.data)
        assert data["status"] == "guidance"
        assert data["api_supported"] is False
        assert "my-org/my-repo" in data["ui_url"]
        assert len(data["instructions"]) > 0
        assert "AGENTS.md" in data["supported_rule_files"]
        assert data["constraints"]["max_budget_chars"] == 25_000
        assert data["constraints"]["rule_priority"] == "User > Repository > Organization"

    async def test_tagged_as_setup(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_configure_repository_rules")
        tags = tool.meta.get("fastmcp", {}).get("tags", [])
        assert "setup" in tags


# ── Web Preview ───────────────────────────────────────────


class TestGetWebPreviewGuide:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_web_preview_guide" in names

    async def test_returns_guidance(self, client: Client):
        result = await client.call_tool(
            "codegen_get_web_preview_guide",
            {"org_name": "my-org", "repo_name": "my-repo"},
        )
        data = json.loads(result.data)
        assert data["status"] == "guidance"
        assert data["api_supported"] is False
        assert "my-org/my-repo" in data["ui_url"]
        assert data["requirements"]["port"] == 3000
        assert data["requirements"]["host"] == "127.0.0.1"
        assert data["requirements"]["env_var"] == "CG_PREVIEW_URL"
        assert len(data["common_commands"]) > 0
        assert len(data["instructions"]) > 0

    async def test_filters_by_framework(self, client: Client):
        result = await client.call_tool(
            "codegen_get_web_preview_guide",
            {"org_name": "org", "repo_name": "repo", "framework": "django"},
        )
        data = json.loads(result.data)
        # Should filter down to Django-related commands
        assert len(data["common_commands"]) >= 1
        assert any("django" in c["framework"].lower() for c in data["common_commands"])

    async def test_framework_filter_no_match_returns_all(self, client: Client):
        result = await client.call_tool(
            "codegen_get_web_preview_guide",
            {"org_name": "org", "repo_name": "repo", "framework": "nonexistent"},
        )
        data = json.loads(result.data)
        # No match → returns all commands as fallback
        assert len(data["common_commands"]) > 3

    async def test_tagged_as_setup(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_get_web_preview_guide")
        tags = tool.meta.get("fastmcp", {}).get("tags", [])
        assert "setup" in tags


# ── Secrets ───────────────────────────────────────────────


class TestGetSecretsGuide:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_secrets_guide" in names

    async def test_returns_guidance(self, client: Client):
        result = await client.call_tool(
            "codegen_get_secrets_guide",
            {"org_name": "my-org", "repo_name": "my-repo"},
        )
        data = json.loads(result.data)
        assert data["status"] == "guidance"
        assert data["api_supported"] is False
        assert "my-org/my-repo" in data["ui_url"]
        assert data["security_constraints"]["staging_only"] is True
        assert "production" in data["security_constraints"]["warning"].lower()
        assert len(data["common_use_cases"]) > 0
        assert len(data["instructions"]) > 0

    async def test_common_use_cases_structure(self, client: Client):
        result = await client.call_tool(
            "codegen_get_secrets_guide",
            {"org_name": "org", "repo_name": "repo"},
        )
        data = json.loads(result.data)
        for use_case in data["common_use_cases"]:
            assert "category" in use_case
            assert "description" in use_case
            assert "example_key" in use_case

    async def test_tagged_as_setup(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_get_secrets_guide")
        tags = tool.meta.get("fastmcp", {}).get("tags", [])
        assert "setup" in tags
