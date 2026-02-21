"""Tests for Codegen API client."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from bridge.client import CodegenClient


@pytest.fixture(autouse=True)
def _force_test_env(monkeypatch):
    """Ensure test env vars override real ones."""
    monkeypatch.setenv("CODEGEN_API_KEY", "test-key")
    monkeypatch.setenv("CODEGEN_ORG_ID", "42")


class TestClientInit:
    def test_creates_with_credentials(self):
        client = CodegenClient(api_key="test-key", org_id=42)
        assert client.org_id == 42

    def test_raises_without_api_key(self):
        with pytest.raises(ValueError, match="api_key"):
            CodegenClient(api_key="", org_id=42)

    def test_raises_without_org_id(self):
        with pytest.raises(ValueError, match="org_id"):
            CodegenClient(api_key="test-key", org_id=0)


class TestCreateRun:
    @respx.mock
    async def test_creates_run_with_prompt(self):
        route = respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200, json={"id": 1, "status": "queued", "web_url": "https://codegen.com/run/1"}
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            run = await client.create_run("Fix the bug")

        assert run.id == 1
        assert run.status == "queued"
        assert route.called

    @respx.mock
    async def test_creates_run_with_all_params(self):
        route = respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(200, json={"id": 2, "status": "queued"})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            run = await client.create_run(
                "Refactor auth",
                repo_id=10,
                model="claude-sonnet-4-6",
                agent_type="claude_code",
                metadata={"plan_task": "Task 3"},
            )

        assert run.id == 2
        body = route.calls[0].request.content
        assert b"repo_id" in body


class TestGetRun:
    @respx.mock
    async def test_gets_run_by_id(self):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1").mock(
            return_value=Response(
                200,
                json={
                    "id": 1,
                    "status": "completed",
                    "summary": "Fixed the bug",
                    "github_pull_requests": [
                        {
                            "url": "https://github.com/org/repo/pull/5",
                            "number": 5,
                        }
                    ],
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            run = await client.get_run(1)

        assert run.status == "completed"
        assert run.github_pull_requests[0].number == 5


class TestGetLogs:
    @respx.mock
    async def test_gets_logs(self):
        respx.get("https://api.codegen.com/v1/alpha/organizations/42/agent/run/1/logs").mock(
            return_value=Response(
                200,
                json={
                    "id": 1,
                    "status": "running",
                    "logs": [
                        {
                            "agent_run_id": 1,
                            "thought": "Analyzing code",
                            "tool_name": "read_file",
                        }
                    ],
                    "total_logs": 1,
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.get_logs(1)

        assert len(result.logs) == 1
        assert result.logs[0].thought == "Analyzing code"


class TestStopRun:
    @respx.mock
    async def test_stops_run(self):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run/ban").mock(
            return_value=Response(200, json={"id": 1, "status": "stopped"})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.stop_run(1)

        # stop_run is a legacy alias — returns AgentRun for backward compat
        assert result.id == 1
        assert result.status == "stopped"


class TestBanRun:
    @respx.mock
    async def test_bans_run(self):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run/ban").mock(
            return_value=Response(200, json={"message": "Banned"})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.ban_run(1)

        assert result.message == "Banned"


class TestUnbanRun:
    @respx.mock
    async def test_unbans_run(self):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run/unban").mock(
            return_value=Response(200, json={})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.unban_run(1)

        assert result.message is None


class TestRemoveFromPr:
    @respx.mock
    async def test_removes_from_pr(self):
        respx.post(
            "https://api.codegen.com/v1/organizations/42/agent/run/remove-from-pr"
        ).mock(return_value=Response(200, json={"message": "Removed"}))

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.remove_from_pr(1)

        assert result.message == "Removed"


class TestListRepos:
    @respx.mock
    async def test_lists_repos(self):
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
                        }
                    ],
                    "total": 1,
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            repos = await client.list_repos()

        assert repos.items[0].full_name == "org/myrepo"


class TestGetMCPProviders:
    @respx.mock
    async def test_returns_providers(self):
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
                        "meta": {"docs": "https://docs.github.com"},
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

        async with CodegenClient(api_key="test", org_id=42) as client:
            providers = await client.get_mcp_providers()

        assert len(providers) == 2
        assert providers[0].name == "github"
        assert providers[0].issuer == "https://github.com"
        assert providers[0].default_scopes == ["repo", "read:org"]
        assert providers[0].meta == {"docs": "https://docs.github.com"}
        assert providers[1].name == "linear"
        assert providers[1].is_mcp is True

    @respx.mock
    async def test_returns_empty_list(self):
        respx.get("https://api.codegen.com/v1/mcp-providers").mock(
            return_value=Response(200, json=[])
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            providers = await client.get_mcp_providers()

        assert providers == []


class TestGetOAuthStatus:
    @respx.mock
    async def test_returns_connected_providers_as_strings(self):
        respx.get("https://api.codegen.com/v1/oauth/tokens/status").mock(
            return_value=Response(200, json=["github", "linear"])
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            statuses = await client.get_oauth_status()

        assert len(statuses) == 2
        assert statuses[0].provider == "github"
        assert statuses[0].active is True
        assert statuses[1].provider == "linear"

    @respx.mock
    async def test_returns_connected_providers_as_dicts(self):
        respx.get("https://api.codegen.com/v1/oauth/tokens/status").mock(
            return_value=Response(
                200,
                json=[
                    {"provider": "github", "active": True},
                    {"provider": "slack", "active": False},
                ],
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            statuses = await client.get_oauth_status()

        assert len(statuses) == 2
        assert statuses[0].provider == "github"
        assert statuses[0].active is True
        assert statuses[1].provider == "slack"
        assert statuses[1].active is False

    @respx.mock
    async def test_passes_org_id_query_param(self):
        route = respx.get("https://api.codegen.com/v1/oauth/tokens/status").mock(
            return_value=Response(200, json=[])
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            await client.get_oauth_status()

        assert route.called
        assert route.calls[0].request.url.params["org_id"] == "42"

    @respx.mock
    async def test_returns_empty_list(self):
        respx.get("https://api.codegen.com/v1/oauth/tokens/status").mock(
            return_value=Response(200, json=[])
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            statuses = await client.get_oauth_status()

        assert statuses == []


class TestRevokeOAuth:
    @respx.mock
    async def test_revokes_token(self):
        route = respx.post("https://api.codegen.com/v1/oauth/tokens/revoke").mock(
            return_value=Response(200, json={"status": "revoked"})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            await client.revoke_oauth("github")

        assert route.called
        assert route.calls[0].request.url.params["provider"] == "github"
        assert route.calls[0].request.url.params["org_id"] == "42"

    @respx.mock
    async def test_raises_on_error(self):
        import httpx as _httpx

        respx.post("https://api.codegen.com/v1/oauth/tokens/revoke").mock(
            return_value=Response(422, json={"detail": "Invalid provider"})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            with pytest.raises(_httpx.HTTPStatusError):
                await client.revoke_oauth("nonexistent")


class TestGetRules:
    @respx.mock
    async def test_gets_org_rules(self):
        respx.get("https://api.codegen.com/v1/organizations/42/cli/rules").mock(
            return_value=Response(
                200,
                json={
                    "organization_rules": "Use conventional commits\nAdd type hints",
                    "user_custom_prompt": "Prefer pytest over unittest",
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            rules = await client.get_rules()

        assert "conventional commits" in rules["organization_rules"]


class TestGetIntegrations:
    @respx.mock
    async def test_gets_integrations(self):
        respx.get("https://api.codegen.com/v1/organizations/42/integrations").mock(
            return_value=Response(
                200,
                json={
                    "organization_id": 42,
                    "organization_name": "My Org",
                    "integrations": [
                        {
                            "integration_type": "github",
                            "active": True,
                            "installation_id": 100,
                        },
                        {
                            "integration_type": "slack",
                            "active": False,
                            "token_id": 200,
                        },
                    ],
                    "total_active_integrations": 1,
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.get_integrations()

        assert result.organization_id == 42
        assert result.total_active_integrations == 1
        assert len(result.integrations) == 2
        assert result.integrations[0].integration_type == "github"
        assert result.integrations[0].active is True
        assert result.integrations[1].active is False


class TestWebhookConfig:
    @respx.mock
    async def test_gets_webhook_config(self):
        respx.get("https://api.codegen.com/v1/organizations/42/webhooks/agent-run").mock(
            return_value=Response(
                200,
                json={"url": "https://example.com/hook", "enabled": True, "has_secret": True},
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            config = await client.get_webhook_config()

        assert config.url == "https://example.com/hook"
        assert config.enabled is True
        assert config.has_secret is True

    @respx.mock
    async def test_sets_webhook_config(self):
        route = respx.post(
            "https://api.codegen.com/v1/organizations/42/webhooks/agent-run"
        ).mock(return_value=Response(200, json={"status": "ok"}))

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.set_webhook_config(
                "https://example.com/hook", secret="s3cret", enabled=True
            )

        assert result["status"] == "ok"
        body = route.calls[0].request.content
        assert b"https://example.com/hook" in body
        assert b"s3cret" in body

    @respx.mock
    async def test_deletes_webhook_config(self):
        respx.delete(
            "https://api.codegen.com/v1/organizations/42/webhooks/agent-run"
        ).mock(return_value=Response(200, json={"status": "deleted"}))

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.delete_webhook_config()

        assert result["status"] == "deleted"

    @respx.mock
    async def test_tests_webhook(self):
        route = respx.post(
            "https://api.codegen.com/v1/organizations/42/webhooks/agent-run/test"
        ).mock(return_value=Response(200, json={"status": "sent"}))

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.test_webhook("https://example.com/hook")

        assert result["status"] == "sent"
        assert route.called


class TestGenerateSetupCommands:
    @respx.mock
    async def test_generates_setup_commands(self):
        route = respx.post(
            "https://api.codegen.com/v1/organizations/42/setup-commands/generate"
        ).mock(
            return_value=Response(
                200,
                json={
                    "agent_run_id": 99,
                    "status": "queued",
                    "url": "https://codegen.com/run/99",
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.generate_setup_commands(10, prompt="Custom setup")

        assert result.agent_run_id == 99
        assert result.status == "queued"
        body = route.calls[0].request.content
        assert b"repo_id" in body

    @respx.mock
    async def test_generates_setup_commands_minimal(self):
        respx.post(
            "https://api.codegen.com/v1/organizations/42/setup-commands/generate"
        ).mock(
            return_value=Response(
                200,
                json={
                    "agent_run_id": 100,
                    "status": "queued",
                    "url": "https://codegen.com/run/100",
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.generate_setup_commands(10)

        assert result.agent_run_id == 100


class TestAnalyzeSandboxLogs:
    @respx.mock
    async def test_analyzes_sandbox_logs(self):
        respx.post(
            "https://api.codegen.com/v1/organizations/42/sandbox/55/analyze-logs"
        ).mock(
            return_value=Response(
                200,
                json={
                    "agent_run_id": 77,
                    "status": "queued",
                    "message": "Analysis started",
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.analyze_sandbox_logs(55)

        assert result.agent_run_id == 77
        assert result.status == "queued"
        assert result.message == "Analysis started"


class TestGetCheckSuiteSettings:
    @respx.mock
    async def test_gets_check_suite_settings(self):
        respx.get(
            "https://api.codegen.com/v1/organizations/42/repos/check-suite-settings"
        ).mock(
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

        async with CodegenClient(api_key="test", org_id=42) as client:
            settings = await client.get_check_suite_settings(10)

        assert settings.check_retry_count == 3
        assert settings.ignored_checks == ["lint"]
        assert settings.check_retry_counts == {"ci": 2}
        assert settings.custom_prompts == {"ci": "Fix CI"}
        assert settings.high_priority_apps == ["GitHub Actions"]
        assert settings.available_check_suite_names == ["ci", "lint", "test"]

    @respx.mock
    async def test_passes_repo_id_query_param(self):
        route = respx.get(
            "https://api.codegen.com/v1/organizations/42/repos/check-suite-settings"
        ).mock(
            return_value=Response(
                200,
                json={
                    "check_retry_count": 0,
                    "ignored_checks": [],
                    "check_retry_counts": {},
                    "custom_prompts": {},
                    "high_priority_apps": [],
                    "available_check_suite_names": [],
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            await client.get_check_suite_settings(10)

        assert route.called
        assert route.calls[0].request.url.params["repo_id"] == "10"


class TestUpdateCheckSuiteSettings:
    @respx.mock
    async def test_updates_settings(self):
        route = respx.put(
            "https://api.codegen.com/v1/organizations/42/repos/check-suite-settings"
        ).mock(return_value=Response(200, json={"status": "ok"}))

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.update_check_suite_settings(
                10, {"check_retry_count": 5, "ignored_checks": ["lint"]}
            )

        assert result["status"] == "ok"
        assert route.called
        assert route.calls[0].request.url.params["repo_id"] == "10"
        body = route.calls[0].request.content
        assert b"check_retry_count" in body
        assert b"ignored_checks" in body

    @respx.mock
    async def test_updates_with_empty_body(self):
        route = respx.put(
            "https://api.codegen.com/v1/organizations/42/repos/check-suite-settings"
        ).mock(return_value=Response(200, json={"status": "ok"}))

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.update_check_suite_settings(10, {})

        assert result["status"] == "ok"
        assert route.called


class TestGenerateSlackConnectToken:
    @respx.mock
    async def test_generates_slack_token(self):
        route = respx.post(
            "https://api.codegen.com/v1/slack-connect/generate-token"
        ).mock(
            return_value=Response(
                200,
                json={
                    "token": "abc123",
                    "message": "Send this to the bot",
                    "expires_in_minutes": 10,
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.generate_slack_connect_token()

        assert result.token == "abc123"
        assert result.expires_in_minutes == 10
        body = route.calls[0].request.content
        assert b"org_id" in body
