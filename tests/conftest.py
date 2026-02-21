"""Shared fixtures and factories for all MCP server tests.

Provides:
- Environment setup fixtures (autouse)
- Server lifespan reset (autouse)
- In-memory MCP ``Client`` fixture
- Model factories for ``AgentRun``, ``Organization``, ``Repository``, etc.
- Shared API response builders for common mock patterns
"""

from __future__ import annotations

import os
from typing import Any

import pytest
import respx
from fastmcp import Client

# Force test env vars before importing server.
# CODEGEN_ALLOW_DANGEROUS_TOOLS enables the full tool suite in integration tests;
# authorization behaviour is tested separately in tests/middleware/test_authorization.py.
os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "42"
os.environ["CODEGEN_ALLOW_DANGEROUS_TOOLS"] = "true"

from bridge.server import mcp

# ── Constants ─────────────────────────────────────────────

BASE_API = "https://api.codegen.com/v1"
ORG_ID = 42


# ── Environment & Lifespan Fixtures ──────────────────────


@pytest.fixture(autouse=True)
def _force_test_env(monkeypatch):
    """Ensure test env vars override real ones for every test."""
    monkeypatch.setenv("CODEGEN_API_KEY", "test-key")
    monkeypatch.setenv("CODEGEN_ORG_ID", "42")
    monkeypatch.setenv("CODEGEN_ALLOW_DANGEROUS_TOOLS", "true")


@pytest.fixture(autouse=True)
def _reset_server_lifespan():
    """Reset server lifespan state between tests.

    When task-enabled tools are present (``task=TaskConfig(mode="optional")``),
    the Docket lifecycle may leave ``_lifespan_result_set=True`` after a
    ``Client`` context-manager exits, preventing subsequent test sessions
    from re-entering the lifespan.  Clearing the flag **before and after**
    each test ensures every test gets a fresh lifespan.
    """
    mcp._lifespan_result_set = False
    mcp._lifespan_result = None
    yield
    mcp._lifespan_result_set = False
    mcp._lifespan_result = None


@pytest.fixture(autouse=True)
def _respx_cleanup():
    """Ensure respx mock state is fully reset between every test.

    respx 0.22.0 patches at the httpcore transport level and can leak mock
    state across separate ``@respx.mock`` contexts.  Explicitly stopping and
    clearing the global router after each test prevents stale routes from
    interfering with subsequent tests — even across different files.
    """
    yield
    try:
        respx.stop()
    except RuntimeError:
        pass  # Not started — nothing to stop.
    respx.clear()


@pytest.fixture
async def client():
    """Create in-memory MCP client with lifespan."""
    async with Client(mcp) as c:
        yield c


# ── Model Factories ──────────────────────────────────────
#
# Each factory returns a dict suitable for ``Response(200, json=...)``
# with sensible defaults that can be overridden via keyword arguments.


class Factory:
    """Namespace for API response factory functions.

    Usage::

        data = Factory.agent_run(id=42, status="completed")
        respx.get(url).mock(return_value=Response(200, json=data))
    """

    @staticmethod
    def agent_run(**overrides: Any) -> dict:
        """Build an AgentRun API response dict."""
        defaults = {
            "id": 1,
            "organization_id": ORG_ID,
            "status": "queued",
            "web_url": "https://codegen.com/run/1",
            "result": None,
            "summary": None,
            "created_at": "2025-01-01T00:00:00Z",
            "source_type": "API",
            "github_pull_requests": None,
            "metadata": None,
        }
        return {**defaults, **overrides}

    @staticmethod
    def agent_run_with_pr(**overrides: Any) -> dict:
        """Build an AgentRun response with a default PR attached."""
        pr = Factory.pull_request()
        defaults = Factory.agent_run(
            status="completed",
            summary="Fixed the bug",
            github_pull_requests=[pr],
        )
        return {**defaults, **overrides}

    @staticmethod
    def pull_request(**overrides: Any) -> dict:
        """Build a PullRequest (nested in AgentRun) response dict."""
        defaults = {
            "id": 1,
            "url": "https://github.com/org/repo/pull/1",
            "number": 1,
            "title": "Fix bug",
            "state": "open",
            "created_at": "2025-01-01T00:00:00Z",
            "head_branch_name": "fix-bug",
        }
        return {**defaults, **overrides}

    @staticmethod
    def organization(**overrides: Any) -> dict:
        """Build an Organization API response dict."""
        defaults = {
            "id": ORG_ID,
            "name": "Test Org",
            "settings": {
                "enable_pr_creation": True,
                "enable_rules_detection": True,
            },
        }
        return {**defaults, **overrides}

    @staticmethod
    def repository(**overrides: Any) -> dict:
        """Build a Repository API response dict."""
        defaults = {
            "id": 10,
            "name": "myrepo",
            "full_name": "org/myrepo",
            "description": "A test repository",
            "github_id": "123456",
            "organization_id": ORG_ID,
            "language": "Python",
            "setup_status": "completed",
            "visibility": "private",
            "archived": False,
        }
        return {**defaults, **overrides}

    @staticmethod
    def user(**overrides: Any) -> dict:
        """Build a User API response dict."""
        defaults = {
            "id": 7,
            "email": "octocat@github.com",
            "github_user_id": "12345",
            "github_username": "octocat",
            "avatar_url": "https://avatars.githubusercontent.com/u/12345",
            "full_name": "Octo Cat",
            "role": "ADMIN",
            "is_admin": True,
        }
        return {**defaults, **overrides}

    @staticmethod
    def agent_log(**overrides: Any) -> dict:
        """Build an AgentLog response dict."""
        defaults = {
            "agent_run_id": 1,
            "created_at": "2025-01-01T00:00:01Z",
            "tool_name": "read_file",
            "message_type": "ACTION",
            "thought": "Reading code",
            "observation": None,
            "tool_input": None,
            "tool_output": None,
        }
        return {**defaults, **overrides}

    @staticmethod
    def agent_run_with_logs(**overrides: Any) -> dict:
        """Build an AgentRunWithLogs response dict."""
        defaults = {
            "id": 1,
            "organization_id": ORG_ID,
            "status": "running",
            "created_at": "2025-01-01T00:00:00Z",
            "web_url": "https://codegen.com/run/1",
            "result": None,
            "metadata": None,
            "logs": [Factory.agent_log()],
            "total_logs": 1,
            "page": 1,
            "size": 50,
            "pages": 1,
        }
        return {**defaults, **overrides}

    @staticmethod
    def integration_status(**overrides: Any) -> dict:
        """Build an IntegrationStatus response dict."""
        defaults = {
            "integration_type": "github",
            "active": True,
            "token_id": None,
            "installation_id": 100,
            "metadata": None,
        }
        return {**defaults, **overrides}

    @staticmethod
    def organization_integrations(**overrides: Any) -> dict:
        """Build an OrganizationIntegrations response dict."""
        defaults = {
            "organization_id": ORG_ID,
            "organization_name": "Test Org",
            "integrations": [
                Factory.integration_status(),
                Factory.integration_status(
                    integration_type="slack", active=True, token_id=200, installation_id=None
                ),
            ],
            "total_active_integrations": 2,
        }
        return {**defaults, **overrides}

    @staticmethod
    def webhook_config(**overrides: Any) -> dict:
        """Build a WebhookConfig response dict."""
        defaults = {
            "url": "https://example.com/hook",
            "enabled": True,
            "has_secret": False,
        }
        return {**defaults, **overrides}

    @staticmethod
    def setup_command(**overrides: Any) -> dict:
        """Build a SetupCommand response dict."""
        defaults = {
            "agent_run_id": 99,
            "status": "queued",
            "url": "https://codegen.com/run/99",
        }
        return {**defaults, **overrides}

    @staticmethod
    def sandbox_log(**overrides: Any) -> dict:
        """Build a SandboxLog response dict."""
        defaults = {
            "agent_run_id": 77,
            "status": "queued",
            "message": "Analysis started",
        }
        return {**defaults, **overrides}

    @staticmethod
    def slack_token(**overrides: Any) -> dict:
        """Build a SlackToken response dict."""
        defaults = {
            "token": "abc123",
            "message": "Send to the bot in DM",
            "expires_in_minutes": 10,
        }
        return {**defaults, **overrides}

    @staticmethod
    def mcp_provider(**overrides: Any) -> dict:
        """Build an MCPProvider response dict."""
        defaults = {
            "id": 1,
            "name": "github",
            "issuer": "https://github.com",
            "authorization_endpoint": "https://github.com/login/oauth/authorize",
            "token_endpoint": "https://github.com/login/oauth/access_token",
            "default_scopes": ["repo", "read:org"],
            "is_mcp": True,
            "meta": None,
        }
        return {**defaults, **overrides}

    @staticmethod
    def edit_pr_response(**overrides: Any) -> dict:
        """Build an EditPRResponse dict."""
        defaults = {
            "success": True,
            "url": "https://github.com/org/repo/pull/1",
            "number": 1,
            "title": "Fix bug",
            "state": "open",
            "error": None,
        }
        return {**defaults, **overrides}

    @staticmethod
    def page(items: list[dict], **overrides: Any) -> dict:
        """Build a paginated Page response dict."""
        defaults = {
            "items": items,
            "total": len(items),
            "page": 1,
            "size": 100,
            "pages": 1,
        }
        return {**defaults, **overrides}

    @staticmethod
    def cli_rules(**overrides: Any) -> dict:
        """Build a CLIRules response dict."""
        defaults = {
            "organization_rules": "Use conventional commits",
            "user_custom_prompt": "Prefer pytest over unittest",
        }
        return {**defaults, **overrides}