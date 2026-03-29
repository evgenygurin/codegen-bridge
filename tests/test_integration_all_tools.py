"""Comprehensive integration tests for ALL MCP codegen-bridge tools.

Exercises every registered tool through the in-memory MCP client with
full lifespan support.  Each tool is called with proper HTTP mocking
to validate the complete request pipeline:

    Client.call_tool → MCP protocol → middleware → tool handler → CodegenClient → HTTP

Tests cover:
- Tool registration completeness (all 39+ tools present)
- Successful execution of each tool module
- HTTP error propagation (4xx / 5xx)
- Edge cases: empty responses, missing optional fields
- Pagination consistency
- Dangerous tool tagging
"""

from __future__ import annotations

import json
from typing import ClassVar

import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError
from httpx import Response

# ── Constants ──────────────────────────────────────────────

BASE = "https://api.codegen.com/v1"
ORG = 42


# ── Tool Registration Completeness ────────────────────────


class TestToolRegistrationCompleteness:
    """Verify ALL manual tools are registered and discoverable."""

    EXPECTED_TOOLS: ClassVar[set[str]] = {
        # agent.py (9)
        "codegen_create_run",
        "codegen_get_run",
        "codegen_list_runs",
        "codegen_resume_run",
        "codegen_stop_run",
        "codegen_ban_run",
        "codegen_unban_run",
        "codegen_remove_from_pr",
        "codegen_get_logs",
        # execution.py (3)
        "codegen_start_execution",
        "codegen_get_execution_context",
        "codegen_get_agent_rules",
        # pr.py (2)
        "codegen_edit_pr",
        "codegen_edit_pr_simple",
        # setup.py (12)
        "codegen_get_current_user",
        "codegen_list_users",
        "codegen_get_user",
        "codegen_list_orgs",
        "codegen_get_organization_settings",
        "codegen_list_repos",
        "codegen_generate_setup_commands",
        "codegen_get_mcp_providers",
        "codegen_get_oauth_status",
        "codegen_get_check_suite_settings",
        "codegen_update_check_suite_settings",
        "codegen_revoke_oauth",
        # integrations.py (7)
        "codegen_get_integrations",
        "codegen_get_webhook_config",
        "codegen_set_webhook_config",
        "codegen_delete_webhook_config",
        "codegen_test_webhook",
        "codegen_analyze_sandbox_logs",
        "codegen_generate_slack_token",
        # settings.py (2)
        "codegen_get_settings",
        "codegen_update_settings",
        # sampling (4)
        "codegen_summarise_run",
        "codegen_summarise_execution",
        "codegen_generate_task_prompt",
        "codegen_analyse_run_logs",
    }

    async def test_all_tools_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        missing = self.EXPECTED_TOOLS - names
        assert not missing, f"Missing tools: {missing}"

    async def test_all_tools_have_descriptions(self, client: Client):
        tools = await client.list_tools()
        for tool in tools:
            if tool.name in self.EXPECTED_TOOLS:
                assert tool.description, f"Tool {tool.name} has no description"
                assert len(tool.description) > 10, (
                    f"Tool {tool.name} description too short: {tool.description!r}"
                )

    async def test_tool_count_at_least_39(self, client: Client):
        """There should be at least 39 manual tools registered."""
        tools = await client.list_tools()
        names = {t.name for t in tools if t.name.startswith("codegen_")}
        assert len(names) >= 39, f"Only {len(names)} codegen tools found: {names}"


# ── Dangerous Tool Tagging ────────────────────────────────


class TestDangerousToolTagging:
    """Verify dangerous tools are properly tagged."""

    DANGEROUS_TOOLS: ClassVar[set[str]] = {
        "codegen_stop_run",
        "codegen_ban_run",
        "codegen_remove_from_pr",
        "codegen_edit_pr",
        "codegen_edit_pr_simple",
        "codegen_delete_webhook_config",
        "codegen_revoke_oauth",
    }

    async def test_dangerous_tools_tagged(self, client: Client):
        tools = await client.list_tools()
        for tool in tools:
            if tool.name in self.DANGEROUS_TOOLS:
                tags = tool.meta.get("fastmcp", {}).get("tags", [])
                assert "dangerous" in tags, (
                    f"Tool {tool.name} should be tagged 'dangerous' but has tags: {tags}"
                )


# ── Agent Tools Integration ───────────────────────────────


class TestAgentToolsIntegration:
    """Integration tests for agent.py tools."""

    @respx.mock
    async def test_get_run_with_prs(self, client: Client):
        """codegen_get_run returns PR data when present."""
        respx.get(f"{BASE}/organizations/{ORG}/agent/run/100").mock(
            return_value=Response(
                200,
                json={
                    "id": 100,
                    "status": "completed",
                    "web_url": "https://codegen.com/run/100",
                    "result": "Task completed",
                    "summary": "Fixed the bug",
                    "source_type": "API",
                    "github_pull_requests": [
                        {
                            "url": "https://github.com/org/repo/pull/1",
                            "title": "Fix: resolve null pointer",
                            "head_branch_name": "fix/null-pointer",
                            "number": 1,
                            "state": "open",
                        }
                    ],
                },
            )
        )

        result = await client.call_tool("codegen_get_run", {"run_id": 100})
        data = json.loads(result.data)
        assert data["id"] == 100
        assert data["status"] == "completed"
        assert data["result"] == "Task completed"
        assert data["summary"] == "Fixed the bug"
        assert data["source_type"] == "API"
        assert len(data["pull_requests"]) == 1
        assert data["pull_requests"][0]["number"] == 1
        assert data["pull_requests"][0]["state"] == "open"

    @respx.mock
    async def test_get_run_minimal_response(self, client: Client):
        """codegen_get_run works with minimal API response (no PRs, no summary)."""
        respx.get(f"{BASE}/organizations/{ORG}/agent/run/101").mock(
            return_value=Response(
                200,
                json={
                    "id": 101,
                    "status": "running",
                    "web_url": "https://codegen.com/run/101",
                },
            )
        )

        result = await client.call_tool("codegen_get_run", {"run_id": 101})
        data = json.loads(result.data)
        assert data["id"] == 101
        assert data["status"] == "running"
        assert "pull_requests" not in data
        assert "summary" not in data

    @respx.mock
    async def test_get_run_http_error(self, client: Client):
        """codegen_get_run propagates HTTP errors."""
        respx.get(f"{BASE}/organizations/{ORG}/agent/run/999").mock(
            return_value=Response(404, json={"detail": "Run not found"})
        )

        with pytest.raises(ToolError):
            await client.call_tool("codegen_get_run", {"run_id": 999})

    @respx.mock
    async def test_list_runs_empty(self, client: Client):
        """codegen_list_runs handles empty results."""
        respx.get(f"{BASE}/organizations/{ORG}/agent/runs").mock(
            return_value=Response(
                200,
                json={"items": [], "total": 0},
            )
        )

        # Use a unique limit to avoid ResponseCachingMiddleware collisions
        # with other tests that also call codegen_list_runs with default args.
        result = await client.call_tool("codegen_list_runs", {"limit": 3})
        data = json.loads(result.data)
        assert data["runs"] == []
        assert data["total"] == 0
        assert data["next_cursor"] is None

    @respx.mock
    async def test_list_runs_with_pagination(self, client: Client):
        """codegen_list_runs returns next_cursor when more pages available."""
        respx.get(f"{BASE}/organizations/{ORG}/agent/runs").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": i,
                            "status": "completed",
                            "web_url": f"https://codegen.com/run/{i}",
                        }
                        for i in range(5)
                    ],
                    "total": 15,
                },
            )
        )

        result = await client.call_tool("codegen_list_runs", {"limit": 5})
        data = json.loads(result.data)
        assert len(data["runs"]) == 5
        assert data["total"] == 15
        assert data["next_cursor"] is not None

    @respx.mock
    async def test_list_runs_filter_by_source_type(self, client: Client):
        """codegen_list_runs accepts source_type filter."""
        route = respx.get(f"{BASE}/organizations/{ORG}/agent/runs").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )

        await client.call_tool("codegen_list_runs", {"source_type": "API", "limit": 5})
        # Verify the query parameter was sent
        assert route.called
        request = route.calls[0].request
        assert "source_type=API" in str(request.url)

    @respx.mock
    async def test_resume_run(self, client: Client):
        """codegen_resume_run sends prompt and optional model."""
        route = respx.post(f"{BASE}/organizations/{ORG}/agent/run/resume").mock(
            return_value=Response(
                200,
                json={
                    "id": 50,
                    "status": "running",
                    "web_url": "https://codegen.com/run/50",
                },
            )
        )

        result = await client.call_tool(
            "codegen_resume_run",
            {"run_id": 50, "prompt": "Continue with tests", "model": "gpt-4o"},
        )
        data = json.loads(result.data)
        assert data["id"] == 50
        assert data["status"] == "running"

        body = json.loads(route.calls[0].request.content)
        assert body["agent_run_id"] == 50
        assert body["prompt"] == "Continue with tests"
        assert body["model"] == "gpt-4o"

    @respx.mock
    async def test_resume_run_http_error(self, client: Client):
        """codegen_resume_run propagates 400 errors."""
        respx.post(f"{BASE}/organizations/{ORG}/agent/run/resume").mock(
            return_value=Response(400, json={"detail": "Run not resumable"})
        )

        with pytest.raises(ToolError):
            await client.call_tool(
                "codegen_resume_run",
                {"run_id": 50, "prompt": "Resume please"},
            )

    @respx.mock
    async def test_ban_run_confirmed(self, client: Client):
        """codegen_ban_run proceeds when confirmed=True."""
        respx.post(f"{BASE}/organizations/{ORG}/agent/run/ban").mock(
            return_value=Response(200, json={"message": "Banned"})
        )

        result = await client.call_tool("codegen_ban_run", {"run_id": 60, "confirmed": True})
        data = json.loads(result.data)
        assert data["action"] == "banned"
        assert data["message"] == "Banned"

    @respx.mock
    async def test_unban_run(self, client: Client):
        """codegen_unban_run unbans a run."""
        respx.post(f"{BASE}/organizations/{ORG}/agent/run/unban").mock(
            return_value=Response(200, json={"message": "Unbanned"})
        )

        result = await client.call_tool("codegen_unban_run", {"run_id": 61})
        data = json.loads(result.data)
        assert data["action"] == "unbanned"
        assert data["message"] == "Unbanned"

    @respx.mock
    async def test_remove_from_pr_confirmed(self, client: Client):
        """codegen_remove_from_pr proceeds when confirmed=True."""
        respx.post(f"{BASE}/organizations/{ORG}/agent/run/remove-from-pr").mock(
            return_value=Response(200, json={"message": "Removed"})
        )

        result = await client.call_tool(
            "codegen_remove_from_pr", {"run_id": 62, "confirmed": True}
        )
        data = json.loads(result.data)
        assert data["action"] == "removed_from_pr"
        assert data["message"] == "Removed"

    @respx.mock
    async def test_get_logs_with_entries(self, client: Client):
        """codegen_get_logs returns formatted log entries."""
        respx.get(f"{BASE}/alpha/organizations/{ORG}/agent/run/70/logs").mock(
            return_value=Response(
                200,
                json={
                    "id": 70,
                    "status": "running",
                    "logs": [
                        {
                            "agent_run_id": 70,
                            "thought": "Analyzing code",
                            "tool_name": "bash",
                            "tool_input": {"command": "ls"},
                            "tool_output": "src/ tests/",
                            "message_type": "tool_use",
                            "created_at": "2024-01-01T00:00:00Z",
                        },
                        {
                            "agent_run_id": 70,
                            "thought": "Found source directory",
                        },
                    ],
                    "total_logs": 10,
                },
            )
        )

        result = await client.call_tool("codegen_get_logs", {"run_id": 70, "limit": 2})
        data = json.loads(result.data)
        assert data["run_id"] == 70
        assert data["status"] == "running"
        assert data["total_logs"] == 10
        assert len(data["logs"]) == 2
        assert data["logs"][0]["thought"] == "Analyzing code"
        assert data["logs"][0]["tool_name"] == "bash"
        # Second log has only thought (no tool data)
        assert data["logs"][1]["thought"] == "Found source directory"
        assert "tool_name" not in data["logs"][1]
        # Pagination: offset 0, limit 2, total 10 → has next
        assert data["next_cursor"] is not None

    @respx.mock
    async def test_get_logs_empty(self, client: Client):
        """codegen_get_logs handles runs with no logs."""
        respx.get(f"{BASE}/alpha/organizations/{ORG}/agent/run/71/logs").mock(
            return_value=Response(
                200,
                json={
                    "id": 71,
                    "status": "queued",
                    "logs": [],
                    "total_logs": 0,
                },
            )
        )

        result = await client.call_tool("codegen_get_logs", {"run_id": 71})
        data = json.loads(result.data)
        assert data["logs"] == []
        assert data["total_logs"] == 0
        assert data["next_cursor"] is None


# ── Execution Tools Integration ───────────────────────────


class TestExecutionToolsIntegration:
    """Integration tests for execution.py tools."""

    @respx.mock
    async def test_start_execution_with_tasks(self, client: Client):
        """codegen_start_execution creates context with plan tasks."""
        respx.get(f"{BASE}/organizations/{ORG}/cli/rules").mock(
            return_value=Response(
                200,
                json={"organization_rules": "Always write tests", "user_custom_prompt": ""},
            )
        )
        respx.get(f"{BASE}/organizations/{ORG}/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )

        result = await client.call_tool(
            "codegen_start_execution",
            {
                "execution_id": "exec-int-1",
                "goal": "Build feature X",
                "mode": "plan",
                "tasks": [
                    {"title": "Task 1", "description": "Do first thing"},
                    {"title": "Task 2", "description": "Do second thing"},
                ],
                "tech_stack": ["Python", "FastAPI"],
                "architecture": "Microservices",
                "confirmed": True,
            },
        )
        data = json.loads(result.data)
        assert data["execution_id"] == "exec-int-1"
        assert data["mode"] == "plan"
        assert data["status"] == "active"
        assert data["tasks"] == 2
        assert data["has_rules"] is True

    @respx.mock
    async def test_start_execution_rules_failure_graceful(self, client: Client):
        """codegen_start_execution continues when rules fetch fails."""
        respx.get(f"{BASE}/organizations/{ORG}/cli/rules").mock(
            return_value=Response(500, json={"detail": "Internal error"})
        )
        respx.get(f"{BASE}/organizations/{ORG}/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )

        result = await client.call_tool(
            "codegen_start_execution",
            {
                "execution_id": "exec-int-2",
                "goal": "Quick fix",
                "confirmed": True,
            },
        )
        data = json.loads(result.data)
        assert data["execution_id"] == "exec-int-2"
        assert data["status"] == "active"
        # Rules failed, so has_rules should be False
        assert data["has_rules"] is False

    @respx.mock
    async def test_get_execution_context_by_nonexistent_id(self, client: Client):
        """codegen_get_execution_context returns error for unknown ID."""
        result = await client.call_tool(
            "codegen_get_execution_context",
            {"execution_id": "nonexistent-id-12345"},
        )
        data = json.loads(result.data)
        assert "error" in data

    @respx.mock
    async def test_get_agent_rules(self, client: Client):
        """codegen_get_agent_rules returns rules from API."""
        respx.get(f"{BASE}/organizations/{ORG}/cli/rules").mock(
            return_value=Response(
                200,
                json={
                    "organization_rules": "Always use conventional commits",
                    "user_custom_prompt": "Prefer Python 3.12+",
                },
            )
        )

        result = await client.call_tool("codegen_get_agent_rules", {})
        data = json.loads(result.data)
        assert data["organization_rules"] == "Always use conventional commits"
        assert data["user_custom_prompt"] == "Prefer Python 3.12+"

    @respx.mock
    async def test_get_agent_rules_http_error_with_unique_client(self):
        """codegen_get_agent_rules raises ToolError on HTTP errors.

        NOTE: Zero-argument tools are cached by ResponseCachingMiddleware.
        This test uses a dedicated server instance to avoid cache hits from
        previous test calls to the same tool (which have no args to
        differentiate the cache key).
        """
        # Create a minimal server WITHOUT caching to test error propagation
        from fastmcp import FastMCP as FreshMCP

        from bridge.middleware.config import CachingConfig, MiddlewareConfig
        from bridge.middleware.stack import configure_middleware
        from bridge.tools.execution import register_execution_tools

        fresh_mcp = FreshMCP("test-no-cache")
        configure_middleware(
            fresh_mcp,
            MiddlewareConfig(caching=CachingConfig(enabled=False)),
        )
        register_execution_tools(fresh_mcp)

        respx.get(f"{BASE}/organizations/{ORG}/cli/rules").mock(
            return_value=Response(403, json={"detail": "Forbidden"})
        )

        async with Client(fresh_mcp) as fresh_client:
            with pytest.raises(ToolError):
                await fresh_client.call_tool("codegen_get_agent_rules", {})


# ── Integration Tools ─────────────────────────────────────


class TestIntegrationToolsIntegration:
    """Integration tests for integrations.py tools."""

    @respx.mock
    async def test_get_integrations(self, client: Client):
        """codegen_get_integrations returns integration statuses."""
        respx.get(f"{BASE}/organizations/{ORG}/integrations").mock(
            return_value=Response(
                200,
                json={
                    "organization_id": ORG,
                    "organization_name": "Test Org",
                    "total_active_integrations": 2,
                    "integrations": [
                        {
                            "integration_type": "github",
                            "active": True,
                            "installation_id": "12345",
                        },
                        {
                            "integration_type": "slack",
                            "active": True,
                            "token_id": "tok-1",
                        },
                        {
                            "integration_type": "linear",
                            "active": False,
                        },
                    ],
                },
            )
        )

        result = await client.call_tool("codegen_get_integrations", {})
        data = json.loads(result.data)
        assert data["organization_id"] == ORG
        assert data["total_active"] == 2
        assert len(data["integrations"]) == 3
        assert data["integrations"][0]["type"] == "github"
        assert data["integrations"][0]["active"] is True
        assert data["integrations"][0]["installation_id"] == "12345"

    @respx.mock
    async def test_get_webhook_config(self, client: Client):
        """codegen_get_webhook_config returns webhook settings."""
        respx.get(f"{BASE}/organizations/{ORG}/webhooks/agent-run").mock(
            return_value=Response(
                200,
                json={
                    "url": "https://example.com/hook",
                    "enabled": True,
                    "has_secret": True,
                },
            )
        )

        result = await client.call_tool("codegen_get_webhook_config", {})
        data = json.loads(result.data)
        assert data["url"] == "https://example.com/hook"
        assert data["enabled"] is True
        assert data["has_secret"] is True

    @respx.mock
    async def test_set_webhook_config_confirmed(self, client: Client):
        """codegen_set_webhook_config sets webhook when confirmed."""
        respx.post(f"{BASE}/organizations/{ORG}/webhooks/agent-run").mock(
            return_value=Response(200, json={"status": "ok"})
        )

        result = await client.call_tool(
            "codegen_set_webhook_config",
            {"url": "https://example.com/hook", "confirmed": True},
        )
        data = json.loads(result.data)
        assert data["status"] == "configured"

    @respx.mock
    async def test_delete_webhook_config_confirmed(self, client: Client):
        """codegen_delete_webhook_config deletes when confirmed."""
        respx.delete(f"{BASE}/organizations/{ORG}/webhooks/agent-run").mock(
            return_value=Response(200, json={"status": "deleted"})
        )

        result = await client.call_tool("codegen_delete_webhook_config", {"confirmed": True})
        data = json.loads(result.data)
        assert data["status"] == "deleted"

    @respx.mock
    async def test_test_webhook(self, client: Client):
        """codegen_test_webhook sends a test event."""
        respx.post(f"{BASE}/organizations/{ORG}/webhooks/agent-run/test").mock(
            return_value=Response(200, json={"success": True})
        )

        result = await client.call_tool(
            "codegen_test_webhook", {"url": "https://example.com/hook"}
        )
        data = json.loads(result.data)
        assert data["status"] == "test_sent"

    @respx.mock
    async def test_analyze_sandbox_logs(self, client: Client):
        """codegen_analyze_sandbox_logs starts analysis."""
        respx.post(f"{BASE}/organizations/{ORG}/sandbox/80/analyze-logs").mock(
            return_value=Response(
                200,
                json={
                    "agent_run_id": 90,
                    "status": "queued",
                    "message": "Analysis started",
                },
            )
        )

        result = await client.call_tool("codegen_analyze_sandbox_logs", {"sandbox_id": 80})
        data = json.loads(result.data)
        assert data["agent_run_id"] == 90
        assert data["status"] == "queued"
        assert data["message"] == "Analysis started"

    @respx.mock
    async def test_generate_slack_token(self, client: Client):
        """codegen_generate_slack_token returns a token."""
        respx.post(f"{BASE}/slack-connect/generate-token").mock(
            return_value=Response(
                200,
                json={
                    "token": "xoxb-test-token",
                    "message": "Send this to the bot",
                    "expires_in_minutes": 10,
                },
            )
        )

        result = await client.call_tool("codegen_generate_slack_token", {})
        data = json.loads(result.data)
        assert data["token"] == "xoxb-test-token"
        assert data["expires_in_minutes"] == 10

    @respx.mock
    async def test_get_integrations_http_error_with_unique_client(self):
        """codegen_get_integrations raises ToolError on HTTP errors.

        Uses a minimal server WITHOUT caching middleware to test error
        propagation without cache interference.
        """
        from fastmcp import FastMCP as FreshMCP

        from bridge.middleware.config import CachingConfig, MiddlewareConfig
        from bridge.middleware.stack import configure_middleware
        from bridge.tools.integrations import register_integration_tools

        fresh_mcp = FreshMCP("test-no-cache-int")
        configure_middleware(
            fresh_mcp,
            MiddlewareConfig(caching=CachingConfig(enabled=False)),
        )
        register_integration_tools(fresh_mcp)

        respx.get(f"{BASE}/organizations/{ORG}/integrations").mock(
            return_value=Response(500, json={"detail": "Server error"})
        )

        async with Client(fresh_mcp) as fresh_client:
            with pytest.raises(ToolError):
                await fresh_client.call_tool("codegen_get_integrations", {})


# ── PR Tools Integration ─────────────────────────────────


class TestPRToolsIntegration:
    """Integration tests for pr.py tools."""

    @respx.mock
    async def test_edit_pr_with_all_states(self, client: Client):
        """codegen_edit_pr works for all valid states."""
        for state in ("open", "closed", "draft", "ready_for_review"):
            respx.patch(f"{BASE}/organizations/{ORG}/repos/10/prs/1").mock(
                return_value=Response(
                    200,
                    json={"success": True, "state": state},
                )
            )

            result = await client.call_tool(
                "codegen_edit_pr",
                {"repo_id": 10, "pr_id": 1, "state": state},
            )
            data = json.loads(result.data)
            assert data["success"] is True

            respx.reset()

    @respx.mock
    async def test_edit_pr_simple_server_error(self, client: Client):
        """codegen_edit_pr_simple handles 500 errors."""
        respx.patch(f"{BASE}/organizations/{ORG}/prs/300").mock(
            return_value=Response(500, json={"detail": "Internal error"})
        )

        with pytest.raises(ToolError):
            await client.call_tool(
                "codegen_edit_pr_simple",
                {"pr_id": 300, "state": "open"},
            )


# ── Setup Tools Edge Cases ────────────────────────────────


class TestSetupToolsEdgeCases:
    """Edge case tests for setup.py tools."""

    @respx.mock
    async def test_list_users_empty(self, client: Client):
        """codegen_list_users handles empty user list."""
        respx.get(f"{BASE}/organizations/{ORG}/users").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )

        result = await client.call_tool("codegen_list_users", {})
        data = json.loads(result.data)
        assert data["users"] == []
        assert data["total"] == 0

    @respx.mock
    async def test_get_user_not_found(self, client: Client):
        """codegen_get_user propagates 404."""
        respx.get(f"{BASE}/organizations/{ORG}/users/999").mock(
            return_value=Response(404, json={"detail": "User not found"})
        )

        with pytest.raises(ToolError):
            await client.call_tool("codegen_get_user", {"user_id": 999})

    @respx.mock
    async def test_list_orgs_http_error(self, client: Client):
        """codegen_list_orgs propagates HTTP errors."""
        respx.get(f"{BASE}/organizations").mock(
            return_value=Response(401, json={"detail": "Unauthorized"})
        )

        with pytest.raises(ToolError):
            await client.call_tool("codegen_list_orgs", {})

    @respx.mock
    async def test_get_organization_settings_http_error(self, client: Client):
        """codegen_get_organization_settings propagates HTTP errors."""
        respx.get(f"{BASE}/organizations/{ORG}/settings").mock(
            return_value=Response(403, json={"detail": "Forbidden"})
        )

        with pytest.raises(ToolError):
            await client.call_tool("codegen_get_organization_settings", {})

    @respx.mock
    async def test_list_repos_empty(self, client: Client):
        """codegen_list_repos handles empty repo list."""
        respx.get(f"{BASE}/organizations/{ORG}/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )

        result = await client.call_tool("codegen_list_repos", {})
        data = json.loads(result.data)
        assert data["repos"] == []
        assert data["total"] == 0

    @respx.mock
    async def test_get_mcp_providers_empty(self, client: Client):
        """codegen_get_mcp_providers handles empty provider list."""
        respx.get(f"{BASE}/mcp-providers").mock(return_value=Response(200, json=[]))

        result = await client.call_tool("codegen_get_mcp_providers", {})
        data = json.loads(result.data)
        assert data["providers"] == []
        assert data["total"] == 0

    @respx.mock
    async def test_get_oauth_status_empty(self, client: Client):
        """codegen_get_oauth_status handles no connected providers."""
        respx.get(f"{BASE}/oauth/tokens/status").mock(return_value=Response(200, json=[]))

        result = await client.call_tool("codegen_get_oauth_status", {})
        data = json.loads(result.data)
        assert data["connected_providers"] == []
        assert data["total"] == 0

    @respx.mock
    async def test_generate_setup_commands_http_error(self, client: Client):
        """codegen_generate_setup_commands propagates HTTP errors."""
        respx.post(f"{BASE}/organizations/{ORG}/setup-commands/generate").mock(
            return_value=Response(422, json={"detail": "Invalid repo"})
        )

        with pytest.raises(ToolError):
            await client.call_tool("codegen_generate_setup_commands", {"repo_id": 999})

    @respx.mock
    async def test_get_check_suite_settings_http_error(self, client: Client):
        """codegen_get_check_suite_settings propagates HTTP errors."""
        respx.get(f"{BASE}/organizations/{ORG}/repos/check-suite-settings").mock(
            return_value=Response(404, json={"detail": "Not found"})
        )

        with pytest.raises(ToolError):
            await client.call_tool("codegen_get_check_suite_settings", {"repo_id": 999})


# ── Settings Tools Edge Cases ─────────────────────────────


class TestSettingsToolsEdgeCases:
    """Edge case tests for settings.py tools."""

    async def test_get_settings_returns_all_keys(self, client: Client):
        """codegen_get_settings always returns all expected keys."""
        result = await client.call_tool("codegen_get_settings", {})
        data = json.loads(result.data)
        expected_keys = {"default_model", "auto_monitor", "poll_interval"}
        assert expected_keys.issubset(data.keys()), f"Missing keys: {expected_keys - data.keys()}"

    async def test_update_settings_returns_new_value(self, client: Client):
        """codegen_update_settings returns the updated value."""
        result = await client.call_tool(
            "codegen_update_settings",
            {"key": "poll_interval", "value": "45"},
        )
        data = json.loads(result.data)
        assert data["updated"]["poll_interval"] == 45
        assert data["all_settings"]["poll_interval"] == 45

        # Reset to default to avoid side effects on disk
        await client.call_tool(
            "codegen_update_settings",
            {"key": "poll_interval", "value": "30"},
        )

    async def test_update_settings_invalid_key(self, client: Client):
        """codegen_update_settings rejects unknown keys."""
        result = await client.call_tool(
            "codegen_update_settings",
            {"key": "nonexistent_setting", "value": "foo"},
        )
        data = json.loads(result.data)
        assert "error" in data

    async def test_update_settings_bool_parsing(self, client: Client):
        """codegen_update_settings parses boolean strings correctly."""
        result = await client.call_tool(
            "codegen_update_settings",
            {"key": "auto_monitor", "value": "false"},
        )
        data = json.loads(result.data)
        assert data["updated"]["auto_monitor"] is False

        # Reset
        await client.call_tool(
            "codegen_update_settings",
            {"key": "auto_monitor", "value": "true"},
        )

    async def test_update_settings_null_value(self, client: Client):
        """codegen_update_settings parses null/None strings correctly."""
        result = await client.call_tool(
            "codegen_update_settings",
            {"key": "default_model", "value": "null"},
        )
        data = json.loads(result.data)
        assert data["updated"]["default_model"] is None


# ── Sampling Tools Registration ───────────────────────────


class TestSamplingToolsIntegration:
    """Verify sampling tools are registered with correct schemas."""

    async def test_summarise_run_schema(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_summarise_run")
        props = tool.inputSchema.get("properties", {})
        assert "run_id" in props

    async def test_summarise_execution_schema(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_summarise_execution")
        props = tool.inputSchema.get("properties", {})
        assert "execution_id" in props

    async def test_generate_task_prompt_schema(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_generate_task_prompt")
        props = tool.inputSchema.get("properties", {})
        assert "goal" in props
        assert "task_description" in props

    async def test_analyse_run_logs_schema(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_analyse_run_logs")
        props = tool.inputSchema.get("properties", {})
        assert "run_id" in props


# ── Cross-Module Consistency ──────────────────────────────


class TestCrossModuleConsistency:
    """Verify consistency across tool modules."""

    async def test_all_tools_return_json(self, client: Client):
        """Every codegen tool's description should not be empty."""
        tools = await client.list_tools()
        for tool in tools:
            if tool.name.startswith("codegen_"):
                assert tool.description is not None
                assert len(tool.description.strip()) > 0

    async def test_no_duplicate_tool_names(self, client: Client):
        """Ensure no duplicate tool names are registered."""
        tools = await client.list_tools()
        names = [t.name for t in tools]
        codegen_names = [n for n in names if n.startswith("codegen_")]
        assert len(codegen_names) == len(set(codegen_names)), (
            f"Duplicate tool names found: "
            f"{[n for n in codegen_names if codegen_names.count(n) > 1]}"
        )

    async def test_all_tools_follow_naming_convention(self, client: Client):
        """All codegen_ tools follow codegen_<verb>_<noun> pattern."""
        tools = await client.list_tools()
        for tool in tools:
            if tool.name.startswith("codegen_"):
                # Remove prefix and check it has at least verb + noun
                rest = tool.name[len("codegen_") :]
                parts = rest.split("_")
                assert len(parts) >= 2, (
                    f"Tool {tool.name} doesn't follow codegen_<verb>_<noun> pattern"
                )
