"""Tests for integration, webhook, sandbox, and Slack connect tools."""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from httpx import Response

# ── Integrations ─────────────────────────────────────────


class TestGetIntegrations:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_integrations" in names

    @respx.mock
    async def test_returns_integrations(self, client: Client):
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
                            "active": True,
                            "token_id": 200,
                            "metadata": {"app_name": "Codegen"},
                        },
                        {
                            "integration_type": "linear",
                            "active": False,
                        },
                    ],
                    "total_active_integrations": 2,
                },
            )
        )

        result = await client.call_tool("codegen_get_integrations", {})
        data = json.loads(result.data)
        assert data["organization_id"] == 42
        assert data["total_active"] == 2
        assert len(data["integrations"]) == 3
        assert data["integrations"][0]["type"] == "github"
        assert data["integrations"][1]["metadata"]["app_name"] == "Codegen"
        # Inactive integration should not have token_id or installation_id keys
        assert "token_id" not in data["integrations"][2]


# ── Webhooks ─────────────────────────────────────────────


class TestGetWebhookConfig:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_webhook_config" in names

    @respx.mock
    async def test_returns_webhook_config(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/webhooks/agent-run").mock(
            return_value=Response(
                200,
                json={"url": "https://example.com/hook", "enabled": True, "has_secret": True},
            )
        )

        result = await client.call_tool("codegen_get_webhook_config", {})
        data = json.loads(result.data)
        assert data["url"] == "https://example.com/hook"
        assert data["enabled"] is True
        assert data["has_secret"] is True


class TestSetWebhookConfig:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_set_webhook_config" in names

    @respx.mock
    async def test_sets_webhook_config(self, client: Client):
        respx.post("https://api.codegen.com/v1/organizations/42/webhooks/agent-run").mock(
            return_value=Response(200, json={"status": "ok"})
        )

        result = await client.call_tool(
            "codegen_set_webhook_config",
            {"url": "https://example.com/hook", "confirmed": True},
        )
        data = json.loads(result.data)
        assert data["status"] == "configured"


class TestDeleteWebhookConfig:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_delete_webhook_config" in names

    @respx.mock
    async def test_deletes_webhook_config(self, client: Client):
        respx.delete("https://api.codegen.com/v1/organizations/42/webhooks/agent-run").mock(
            return_value=Response(200, json={"status": "deleted"})
        )

        result = await client.call_tool(
            "codegen_delete_webhook_config",
            {"confirmed": True},
        )
        data = json.loads(result.data)
        assert data["status"] == "deleted"


class TestTestWebhook:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_test_webhook" in names

    @respx.mock
    async def test_sends_test_webhook(self, client: Client):
        respx.post("https://api.codegen.com/v1/organizations/42/webhooks/agent-run/test").mock(
            return_value=Response(200, json={"status": "sent"})
        )

        result = await client.call_tool(
            "codegen_test_webhook",
            {"url": "https://example.com/hook"},
        )
        data = json.loads(result.data)
        assert data["status"] == "test_sent"


# ── Sandbox ──────────────────────────────────────────────


class TestAnalyzeSandboxLogs:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_analyze_sandbox_logs" in names

    @respx.mock
    async def test_analyzes_sandbox_logs(self, client: Client):
        respx.post("https://api.codegen.com/v1/organizations/42/sandbox/55/analyze-logs").mock(
            return_value=Response(
                200,
                json={
                    "agent_run_id": 77,
                    "status": "queued",
                    "message": "Analysis started",
                },
            )
        )

        result = await client.call_tool(
            "codegen_analyze_sandbox_logs",
            {"sandbox_id": 55},
        )
        data = json.loads(result.data)
        assert data["agent_run_id"] == 77
        assert data["status"] == "queued"
        assert data["message"] == "Analysis started"


# ── Slack Connect ────────────────────────────────────────


class TestGenerateSlackToken:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_generate_slack_token" in names

    @respx.mock
    async def test_generates_slack_token(self, client: Client):
        respx.post("https://api.codegen.com/v1/slack-connect/generate-token").mock(
            return_value=Response(
                200,
                json={
                    "token": "abc123",
                    "message": "Send to the bot in DM",
                    "expires_in_minutes": 10,
                },
            )
        )

        result = await client.call_tool("codegen_generate_slack_token", {})
        data = json.loads(result.data)
        assert data["token"] == "abc123"
        assert data["expires_in_minutes"] == 10


# ── Integration Health Check ────────────────────────────


class TestCheckIntegrationHealth:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_check_integration_health" in names

    @respx.mock
    async def test_reports_healthy(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/integrations").mock(
            return_value=Response(
                200,
                json={
                    "organization_id": 42,
                    "organization_name": "My Org",
                    "integrations": [
                        {"integration_type": "github", "active": True, "installation_id": 1},
                        {"integration_type": "slack", "active": True, "token_id": 2},
                    ],
                    "total_active_integrations": 2,
                },
            )
        )
        respx.get("https://api.codegen.com/v1/organizations/42/webhooks/agent-run").mock(
            return_value=Response(
                200,
                json={"url": "https://example.com/hook", "enabled": True, "has_secret": True},
            )
        )

        result = await client.call_tool("codegen_check_integration_health", {})
        data = json.loads(result.data)
        assert data["organization_id"] == 42
        assert data["overall_status"] == "healthy"
        assert data["healthy"] == 3  # 2 integrations + webhook
        assert data["unhealthy"] == 0
        assert len(data["checks"]) == 3

    @respx.mock
    async def test_reports_degraded(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/integrations").mock(
            return_value=Response(
                200,
                json={
                    "organization_id": 42,
                    "organization_name": "My Org",
                    "integrations": [
                        {"integration_type": "github", "active": True, "installation_id": 1},
                        {"integration_type": "slack", "active": False},
                    ],
                    "total_active_integrations": 1,
                },
            )
        )
        respx.get("https://api.codegen.com/v1/organizations/42/webhooks/agent-run").mock(
            return_value=Response(
                200,
                json={"url": "", "enabled": False, "has_secret": False},
            )
        )

        result = await client.call_tool("codegen_check_integration_health", {})
        data = json.loads(result.data)
        assert data["overall_status"] == "degraded"
        assert data["healthy"] == 1  # only github
        assert data["unhealthy"] == 2  # slack + webhook
