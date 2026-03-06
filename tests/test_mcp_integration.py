"""MCP Integration Test — full protocol round-trip for every manual tool.

Launches the MCP server in-memory via ``fastmcp.Client(mcp)``, sends real
MCP-protocol requests to each tool with different parameter combinations,
and produces a clean structured log:

    TOOL: codegen_list_runs
    PARAMS: {"limit": 5}
    STATUS: OK (0.032s)
    RESPONSE: {"total": 1, "runs": [...]}
    ────────────────────────

Run with:
    just mcp-test            # shortcut
    uv run pytest tests/test_mcp_integration.py -v -s   # full output
"""

from __future__ import annotations

import json
import os
import time

os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "42"
os.environ["CODEGEN_ALLOW_DANGEROUS_TOOLS"] = "true"

import pytest
import respx
from fastmcp import Client
from httpx import Response

from bridge.server import mcp

# ── Logging helper ─────────────────────────────────────────

_SEPARATOR = "─" * 50
_LOG_ENTRIES: list[dict[str, object]] = []


def _log(
    tool: str,
    params: dict[str, object],
    *,
    status: str,
    elapsed: float,
    response: object = None,
    error: str | None = None,
) -> None:
    """Print a clean log block and accumulate for summary."""
    entry = {
        "tool": tool,
        "params": params,
        "status": status,
        "elapsed_s": round(elapsed, 4),
    }
    if response is not None:
        entry["response"] = response
    if error:
        entry["error"] = error
    _LOG_ENTRIES.append(entry)

    # Human-readable console output
    print(f"\n  TOOL: {tool}")
    print(f"  PARAMS: {json.dumps(params, default=str)}")
    if error:
        print(f"  STATUS: {status} ({elapsed:.3f}s)")
        print(f"  ERROR: {error}")
    else:
        print(f"  STATUS: {status} ({elapsed:.3f}s)")
        resp_str = json.dumps(response, default=str)
        if len(resp_str) > 600:
            resp_str = resp_str[:600] + "…"
        print(f"  RESPONSE: {resp_str}")
    print(f"  {_SEPARATOR}")


async def _call(client: Client, tool: str, params: dict[str, object] | None = None) -> object:
    """Call a tool, log the result, return parsed response."""
    params = params or {}
    t0 = time.perf_counter()
    try:
        result = await client.call_tool(tool, params)
        elapsed = time.perf_counter() - t0
        data = json.loads(result.data)
        _log(tool, params, status="OK", elapsed=elapsed, response=data)
        return data
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        _log(tool, params, status="ERROR", elapsed=elapsed, error=str(exc))
        raise


# ── Fixtures ───────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEGEN_API_KEY", "test-key")
    monkeypatch.setenv("CODEGEN_ORG_ID", "42")
    monkeypatch.setenv("CODEGEN_ALLOW_DANGEROUS_TOOLS", "true")


@pytest.fixture(autouse=True)
def _reset_server():
    mcp._lifespan_result_set = False
    mcp._lifespan_result = None
    yield
    mcp._lifespan_result_set = False
    mcp._lifespan_result = None


@pytest.fixture
async def c():
    """In-memory MCP client with full server lifespan."""
    async with Client(mcp) as client:
        yield client


# ── Common mock data ────────────────────────────────────────

BASE = "https://api.codegen.com/v1"

RUN_JSON = {
    "id": 99,
    "organization_id": 42,
    "status": "completed",
    "web_url": "https://codegen.com/run/99",
    "summary": "Fixed the bug",
    "source_type": "API",
    "github_pull_requests": [
        {
            "url": "https://github.com/o/r/pull/5",
            "number": 5,
            "title": "Fix bug",
            "state": "open",
            "head_branch_name": "fix-bug",
        }
    ],
}

PAGE_RUNS_JSON = {
    "items": [
        {"id": 1, "organization_id": 42, "status": "completed", "source_type": "API"},
        {"id": 2, "organization_id": 42, "status": "running", "source_type": "GITHUB"},
    ],
    "total": 2,
    "page": 1,
    "size": 20,
    "pages": 1,
}

REPOS_JSON = {
    "items": [
        {
            "id": 10,
            "name": "my-repo",
            "full_name": "org/my-repo",
            "language": "Python",
            "setup_status": "complete",
        }
    ],
    "total": 1,
}

USERS_JSON = {
    "items": [
        {
            "id": 1,
            "email": "dev@example.com",
            "github_username": "devuser",
            "full_name": "Dev User",
            "role": "admin",
            "is_admin": True,
        }
    ],
    "total": 1,
}

ORGS_JSON = {
    "items": [{"id": 42, "name": "TestOrg"}],
    "total": 1,
}

LOGS_JSON = {
    "id": 99,
    "status": "completed",
    "logs": [
        {
            "agent_run_id": 99,
            "thought": "Reading code",
            "tool_name": "read_file",
            "message_type": "ACTION",
        },
        {
            "agent_run_id": 99,
            "thought": "Found issue",
            "tool_name": None,
            "message_type": "PLAN_EVALUATION",
        },
    ],
    "total_logs": 2,
}

INTEGRATIONS_JSON = {
    "organization_id": 42,
    "organization_name": "TestOrg",
    "integrations": [
        {"integration_type": "github", "active": True, "installation_id": 123},
        {"integration_type": "slack", "active": False},
    ],
    "total_active_integrations": 1,
}

WEBHOOK_JSON = {"url": "https://example.com/hook", "enabled": True, "has_secret": False}

ORG_SETTINGS_JSON = {"enable_pr_creation": True, "enable_rules_detection": True}

CHECK_SUITE_JSON = {
    "check_retry_count": 2,
    "ignored_checks": ["lint"],
    "check_retry_counts": {"lint": 1},
    "custom_prompts": {},
    "high_priority_apps": ["ci"],
    "available_check_suite_names": ["lint", "test", "build"],
}

RULES_JSON = {
    "organization_rules": "Be concise",
    "user_custom_prompt": "Focus on tests",
}

SLACK_TOKEN_JSON = {
    "token": "xoxb-test-token",
    "message": "Token generated",
    "expires_in_minutes": 10,
}

SANDBOX_LOG_JSON = {
    "agent_run_id": 99,
    "status": "analyzing",
    "message": "Analysis started",
}

SETUP_CMD_JSON = {
    "agent_run_id": 200,
    "status": "running",
    "url": "https://codegen.com/run/200",
}


# ═══════════════════════════════════════════════════════════
# AGENT TOOLS
# ═══════════════════════════════════════════════════════════


class TestAgentQueries:
    """codegen_get_run, codegen_list_runs — read-only queries."""

    @respx.mock
    async def test_get_run_basic(self, c: Client):
        respx.get(f"{BASE}/organizations/42/agent/run/99").mock(
            return_value=Response(200, json=RUN_JSON)
        )
        data = await _call(c, "codegen_get_run", {"run_id": 99})
        assert data["id"] == 99
        assert data["status"] == "completed"
        assert data["pull_requests"][0]["number"] == 5

    @respx.mock
    async def test_get_run_minimal_response(self, c: Client):
        respx.get(f"{BASE}/organizations/42/agent/run/101").mock(
            return_value=Response(
                200, json={"id": 101, "organization_id": 42, "status": "running"}
            )
        )
        data = await _call(c, "codegen_get_run", {"run_id": 101})
        assert data["id"] == 101
        assert data["status"] == "running"
        assert "pull_requests" not in data

    @respx.mock
    async def test_list_runs_default(self, c: Client):
        respx.get(f"{BASE}/organizations/42/agent/runs").mock(
            return_value=Response(200, json=PAGE_RUNS_JSON)
        )
        data = await _call(c, "codegen_list_runs", {})
        assert data["total"] == 2
        assert len(data["runs"]) == 2

    @respx.mock
    async def test_list_runs_with_filters(self, c: Client):
        respx.get(f"{BASE}/organizations/42/agent/runs").mock(
            return_value=Response(200, json=PAGE_RUNS_JSON)
        )
        data = await _call(
            c, "codegen_list_runs", {"limit": 5, "user_id": 7, "source_type": "API"}
        )
        assert data["total"] == 2

    @respx.mock
    async def test_list_runs_with_cursor(self, c: Client):
        respx.get(f"{BASE}/organizations/42/agent/runs").mock(
            return_value=Response(200, json=PAGE_RUNS_JSON)
        )
        data = await _call(c, "codegen_list_runs", {"cursor": "eyJvIjogMjB9", "limit": 10})
        assert "runs" in data


class TestAgentLifecycle:
    """codegen_create_run, codegen_resume_run, codegen_stop_run."""

    @respx.mock
    async def test_create_run_with_repo_id(self, c: Client):
        respx.get(f"{BASE}/organizations/42/repos").mock(
            return_value=Response(200, json=REPOS_JSON)
        )
        respx.post(f"{BASE}/organizations/42/agent/run").mock(
            return_value=Response(200, json={"id": 99, "status": "queued", "web_url": "https://codegen.com/run/99"})
        )
        data = await _call(c, "codegen_create_run", {
            "prompt": "Fix the bug",
            "repo_id": 10,
            "confirmed": True,
        })
        assert data["id"] == 99
        assert data["status"] == "queued"

    @respx.mock
    async def test_create_run_with_images(self, c: Client):
        respx.get(f"{BASE}/organizations/42/repos").mock(
            return_value=Response(200, json=REPOS_JSON)
        )
        route = respx.post(f"{BASE}/organizations/42/agent/run").mock(
            return_value=Response(200, json={"id": 100, "status": "queued", "web_url": "https://codegen.com/run/100"})
        )
        data = await _call(c, "codegen_create_run", {
            "prompt": "Analyze screenshot",
            "repo_id": 10,
            "images": ["data:image/png;base64,abc123"],
            "confirmed": True,
        })
        assert data["id"] == 100
        body = json.loads(route.calls[0].request.content)
        assert body["images"] == ["data:image/png;base64,abc123"]

    @respx.mock
    async def test_create_run_with_model(self, c: Client):
        respx.get(f"{BASE}/organizations/42/repos").mock(
            return_value=Response(200, json=REPOS_JSON)
        )
        route = respx.post(f"{BASE}/organizations/42/agent/run").mock(
            return_value=Response(200, json={"id": 101, "status": "queued", "web_url": "https://codegen.com/run/101"})
        )
        data = await _call(c, "codegen_create_run", {
            "prompt": "Refactor module",
            "repo_id": 10,
            "model": "claude-3-5-sonnet",
            "confirmed": True,
        })
        assert data["id"] == 101
        body = json.loads(route.calls[0].request.content)
        assert body["model"] == "claude-3-5-sonnet"

    @respx.mock
    async def test_resume_run(self, c: Client):
        respx.post(f"{BASE}/organizations/42/agent/run/resume").mock(
            return_value=Response(200, json={"id": 50, "status": "running", "web_url": "https://codegen.com/run/50"})
        )
        data = await _call(c, "codegen_resume_run", {
            "run_id": 50,
            "prompt": "Continue with fix",
        })
        assert data["id"] == 50
        assert data["status"] == "running"

    @respx.mock
    async def test_resume_run_with_images(self, c: Client):
        route = respx.post(f"{BASE}/organizations/42/agent/run/resume").mock(
            return_value=Response(200, json={"id": 50, "status": "running", "web_url": "https://codegen.com/run/50"})
        )
        data = await _call(c, "codegen_resume_run", {
            "run_id": 50,
            "prompt": "See screenshot",
            "images": ["data:image/png;base64,xyz"],
        })
        assert data["id"] == 50
        body = json.loads(route.calls[0].request.content)
        assert body["images"] == ["data:image/png;base64,xyz"]

    @respx.mock
    async def test_stop_run(self, c: Client):
        respx.post(f"{BASE}/organizations/42/agent/run/ban").mock(
            return_value=Response(200, json={"id": 99, "status": "stopped"})
        )
        data = await _call(c, "codegen_stop_run", {"run_id": 99, "confirmed": True})
        assert data["id"] == 99


class TestAgentModeration:
    """codegen_ban_run, codegen_unban_run, codegen_remove_from_pr."""

    @respx.mock
    async def test_ban_run_full_params(self, c: Client):
        route = respx.post(f"{BASE}/organizations/42/agent/run/ban").mock(
            return_value=Response(200, json={"message": "Banned"})
        )
        data = await _call(c, "codegen_ban_run", {
            "run_id": 55,
            "before_card_order_id": "abc",
            "after_card_order_id": "xyz",
            "confirmed": True,
        })
        assert data["run_id"] == 55
        assert data["action"] == "banned"
        body = json.loads(route.calls[0].request.content)
        assert body["before_card_order_id"] == "abc"

    @respx.mock
    async def test_ban_run_minimal(self, c: Client):
        respx.post(f"{BASE}/organizations/42/agent/run/ban").mock(
            return_value=Response(200, json={})
        )
        data = await _call(c, "codegen_ban_run", {"run_id": 56, "confirmed": True})
        assert data["action"] == "banned"

    @respx.mock
    async def test_unban_run(self, c: Client):
        respx.post(f"{BASE}/organizations/42/agent/run/unban").mock(
            return_value=Response(200, json={"message": "Unbanned"})
        )
        data = await _call(c, "codegen_unban_run", {
            "run_id": 60,
            "before_card_order_id": "a1",
        })
        assert data["run_id"] == 60
        assert data["action"] == "unbanned"

    @respx.mock
    async def test_unban_run_minimal(self, c: Client):
        respx.post(f"{BASE}/organizations/42/agent/run/unban").mock(
            return_value=Response(200, json={})
        )
        data = await _call(c, "codegen_unban_run", {"run_id": 61})
        assert data["action"] == "unbanned"

    @respx.mock
    async def test_remove_from_pr_full(self, c: Client):
        respx.post(f"{BASE}/organizations/42/agent/run/remove-from-pr").mock(
            return_value=Response(200, json={"message": "Removed"})
        )
        data = await _call(c, "codegen_remove_from_pr", {
            "run_id": 70,
            "before_card_order_id": "b1",
            "after_card_order_id": "b2",
            "confirmed": True,
        })
        assert data["run_id"] == 70
        assert data["action"] == "removed_from_pr"

    @respx.mock
    async def test_remove_from_pr_minimal(self, c: Client):
        respx.post(f"{BASE}/organizations/42/agent/run/remove-from-pr").mock(
            return_value=Response(200, json={})
        )
        data = await _call(c, "codegen_remove_from_pr", {"run_id": 71, "confirmed": True})
        assert data["action"] == "removed_from_pr"


class TestAgentLogs:
    """codegen_get_logs — execution log retrieval."""

    @respx.mock
    async def test_get_logs_default(self, c: Client):
        respx.get(f"{BASE}/alpha/organizations/42/agent/run/99/logs").mock(
            return_value=Response(200, json=LOGS_JSON)
        )
        data = await _call(c, "codegen_get_logs", {"run_id": 99})
        assert data["total_logs"] == 2
        assert data["logs"][0]["thought"] == "Reading code"
        assert data["logs"][1]["message_type"] == "PLAN_EVALUATION"

    @respx.mock
    async def test_get_logs_with_pagination(self, c: Client):
        respx.get(f"{BASE}/alpha/organizations/42/agent/run/99/logs").mock(
            return_value=Response(200, json=LOGS_JSON)
        )
        data = await _call(c, "codegen_get_logs", {"run_id": 99, "limit": 1, "reverse": False})
        assert "logs" in data

    @respx.mock
    async def test_get_logs_with_cursor(self, c: Client):
        respx.get(f"{BASE}/alpha/organizations/42/agent/run/99/logs").mock(
            return_value=Response(200, json={
                "id": 99,
                "status": "completed",
                "logs": [],
                "total_logs": 0,
            })
        )
        data = await _call(c, "codegen_get_logs", {"run_id": 99, "cursor": "eyJvIjogNTB9"})
        assert data["total_logs"] == 0


# ═══════════════════════════════════════════════════════════
# EXECUTION CONTEXT TOOLS
# ═══════════════════════════════════════════════════════════


class TestExecutionContext:
    """codegen_start_execution, codegen_get_execution_context, codegen_get_agent_rules."""

    @respx.mock
    async def test_start_execution(self, c: Client):
        respx.get(f"{BASE}/organizations/42/cli/rules").mock(
            return_value=Response(200, json=RULES_JSON)
        )
        respx.get(f"{BASE}/organizations/42/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )
        data = await _call(c, "codegen_start_execution", {
            "execution_id": "exec-1",
            "goal": "Build feature X",
            "mode": "plan",
            "tasks": [
                {"title": "Task 1", "description": "Do first thing"},
                {"title": "Task 2", "description": "Do second thing"},
            ],
            "confirmed": True,
        })
        assert data["execution_id"] == "exec-1"
        assert data["mode"] == "plan"
        assert data["tasks"] == 2
        assert data["has_rules"] is True

    @respx.mock
    async def test_start_execution_adhoc(self, c: Client):
        respx.get(f"{BASE}/organizations/42/cli/rules").mock(
            return_value=Response(200, json={"organization_rules": ""})
        )
        respx.get(f"{BASE}/organizations/42/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )
        data = await _call(c, "codegen_start_execution", {
            "execution_id": "exec-adhoc",
            "goal": "Quick fix",
            "confirmed": True,
        })
        assert data["execution_id"] == "exec-adhoc"
        assert data["mode"] == "adhoc"

    @respx.mock
    async def test_get_execution_context(self, c: Client):
        # First start one
        respx.get(f"{BASE}/organizations/42/cli/rules").mock(
            return_value=Response(200, json=RULES_JSON)
        )
        respx.get(f"{BASE}/organizations/42/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )
        await _call(c, "codegen_start_execution", {
            "execution_id": "ctx-test",
            "goal": "Context test",
            "confirmed": True,
        })
        # Then retrieve it
        data = await _call(c, "codegen_get_execution_context", {"execution_id": "ctx-test"})
        assert data["id"] == "ctx-test"
        assert data["goal"] == "Context test"

    @respx.mock
    async def test_get_execution_context_not_found(self, c: Client):
        data = await _call(c, "codegen_get_execution_context", {"execution_id": "nonexistent"})
        assert "error" in data

    @respx.mock
    async def test_get_agent_rules(self, c: Client):
        respx.get(f"{BASE}/organizations/42/cli/rules").mock(
            return_value=Response(200, json=RULES_JSON)
        )
        data = await _call(c, "codegen_get_agent_rules", {})
        assert data["organization_rules"] == "Be concise"
        assert data["user_custom_prompt"] == "Focus on tests"


# ═══════════════════════════════════════════════════════════
# PULL REQUEST TOOLS
# ═══════════════════════════════════════════════════════════


class TestPullRequests:
    """codegen_edit_pr, codegen_edit_pr_simple."""

    @respx.mock
    async def test_edit_pr(self, c: Client):
        respx.patch(f"{BASE}/organizations/42/repos/10/prs/5").mock(
            return_value=Response(200, json={
                "success": True,
                "url": "https://github.com/o/r/pull/5",
                "number": 5,
                "title": "Fix bug",
                "state": "closed",
            })
        )
        data = await _call(c, "codegen_edit_pr", {
            "repo_id": 10,
            "pr_id": 5,
            "state": "closed",
        })
        assert data["success"] is True
        assert data["state"] == "closed"

    @respx.mock
    async def test_edit_pr_simple(self, c: Client):
        respx.patch(f"{BASE}/organizations/42/prs/5").mock(
            return_value=Response(200, json={
                "success": True,
                "number": 5,
                "state": "open",
            })
        )
        data = await _call(c, "codegen_edit_pr_simple", {"pr_id": 5, "state": "open"})
        assert data["success"] is True
        assert data["state"] == "open"

    @respx.mock
    async def test_edit_pr_to_draft(self, c: Client):
        respx.patch(f"{BASE}/organizations/42/repos/10/prs/7").mock(
            return_value=Response(200, json={
                "success": True,
                "number": 7,
                "state": "draft",
            })
        )
        data = await _call(c, "codegen_edit_pr", {
            "repo_id": 10,
            "pr_id": 7,
            "state": "draft",
        })
        assert data["state"] == "draft"


# ═══════════════════════════════════════════════════════════
# SETUP — USERS
# ═══════════════════════════════════════════════════════════


class TestSetupUsers:
    """codegen_get_current_user, codegen_list_users, codegen_get_user."""

    @respx.mock
    async def test_get_current_user(self, c: Client):
        respx.get(f"{BASE}/users/me").mock(
            return_value=Response(200, json={
                "id": 1,
                "email": "dev@example.com",
                "github_username": "devuser",
                "full_name": "Dev User",
                "role": "admin",
                "is_admin": True,
            })
        )
        data = await _call(c, "codegen_get_current_user", {})
        assert data["user"]["github_username"] == "devuser"
        assert data["user"]["is_admin"] is True

    @respx.mock
    async def test_list_users_default(self, c: Client):
        respx.get(f"{BASE}/organizations/42/users").mock(
            return_value=Response(200, json=USERS_JSON)
        )
        data = await _call(c, "codegen_list_users", {})
        assert data["total"] == 1
        assert data["users"][0]["email"] == "dev@example.com"

    @respx.mock
    async def test_list_users_with_pagination(self, c: Client):
        respx.get(f"{BASE}/organizations/42/users").mock(
            return_value=Response(200, json=USERS_JSON)
        )
        data = await _call(c, "codegen_list_users", {"limit": 5, "cursor": "eyJvIjogMTB9"})
        assert "users" in data

    @respx.mock
    async def test_get_user_by_id(self, c: Client):
        respx.get(f"{BASE}/organizations/42/users/7").mock(
            return_value=Response(200, json={
                "id": 7,
                "email": "other@example.com",
                "github_username": "otheruser",
                "full_name": "Other User",
                "role": "member",
                "is_admin": False,
            })
        )
        data = await _call(c, "codegen_get_user", {"user_id": 7})
        assert data["user"]["id"] == 7
        assert data["user"]["role"] == "member"


# ═══════════════════════════════════════════════════════════
# SETUP — ORGANIZATIONS & REPOS
# ═══════════════════════════════════════════════════════════


class TestSetupOrganizations:
    """codegen_list_orgs, codegen_get_organization_settings, etc."""

    @respx.mock
    async def test_list_orgs(self, c: Client):
        respx.get(f"{BASE}/organizations").mock(
            return_value=Response(200, json=ORGS_JSON)
        )
        data = await _call(c, "codegen_list_orgs", {})
        assert data["organizations"][0]["name"] == "TestOrg"

    @respx.mock
    async def test_get_organization_settings(self, c: Client):
        respx.get(f"{BASE}/organizations/42/settings").mock(
            return_value=Response(200, json=ORG_SETTINGS_JSON)
        )
        data = await _call(c, "codegen_get_organization_settings", {})
        assert data["enable_pr_creation"] is True
        assert data["enable_rules_detection"] is True

    @respx.mock
    async def test_list_repos_default(self, c: Client):
        respx.get(f"{BASE}/organizations/42/repos").mock(
            return_value=Response(200, json=REPOS_JSON)
        )
        data = await _call(c, "codegen_list_repos", {})
        assert data["total"] == 1
        assert data["repos"][0]["name"] == "my-repo"

    @respx.mock
    async def test_list_repos_paginated(self, c: Client):
        respx.get(f"{BASE}/organizations/42/repos").mock(
            return_value=Response(200, json=REPOS_JSON)
        )
        data = await _call(c, "codegen_list_repos", {"limit": 5, "cursor": "eyJvIjogMH0="})
        assert "repos" in data

    @respx.mock
    async def test_generate_setup_commands(self, c: Client):
        respx.post(f"{BASE}/organizations/42/setup-commands/generate").mock(
            return_value=Response(200, json=SETUP_CMD_JSON)
        )
        data = await _call(c, "codegen_generate_setup_commands", {"repo_id": 10})
        assert data["agent_run_id"] == 200
        assert data["status"] == "running"

    @respx.mock
    async def test_generate_setup_commands_with_prompt(self, c: Client):
        route = respx.post(f"{BASE}/organizations/42/setup-commands/generate").mock(
            return_value=Response(200, json=SETUP_CMD_JSON)
        )
        data = await _call(c, "codegen_generate_setup_commands", {
            "repo_id": 10,
            "prompt": "Include Docker setup",
        })
        assert data["agent_run_id"] == 200
        body = json.loads(route.calls[0].request.content)
        assert body["prompt"] == "Include Docker setup"


# ═══════════════════════════════════════════════════════════
# SETUP — OAUTH
# ═══════════════════════════════════════════════════════════


class TestSetupOAuth:
    """codegen_get_mcp_providers, codegen_get_oauth_status, codegen_revoke_oauth."""

    @respx.mock
    async def test_get_mcp_providers(self, c: Client):
        respx.get(f"{BASE}/mcp-providers").mock(
            return_value=Response(200, json=[
                {
                    "id": 1,
                    "name": "linear",
                    "issuer": "https://linear.app",
                    "authorization_endpoint": "https://linear.app/oauth/authorize",
                    "token_endpoint": "https://linear.app/oauth/token",
                    "default_scopes": ["read", "write"],
                    "is_mcp": True,
                }
            ])
        )
        data = await _call(c, "codegen_get_mcp_providers", {})
        assert data["total"] == 1
        assert data["providers"][0]["name"] == "linear"

    @respx.mock
    async def test_get_oauth_status(self, c: Client):
        respx.get(f"{BASE}/oauth/tokens/status").mock(
            return_value=Response(200, json=[
                {"provider": "github", "active": True},
                {"provider": "linear", "active": True},
            ])
        )
        data = await _call(c, "codegen_get_oauth_status", {})
        assert data["total"] == 2
        assert data["connected_providers"][0]["provider"] == "github"

    @respx.mock
    async def test_get_oauth_status_string_format(self, c: Client):
        """API may return list[str] instead of list[dict]."""
        respx.get(f"{BASE}/oauth/tokens/status").mock(
            return_value=Response(200, json=["github", "slack"])
        )
        data = await _call(c, "codegen_get_oauth_status", {})
        assert data["total"] == 2

    @respx.mock
    async def test_revoke_oauth(self, c: Client):
        respx.post(f"{BASE}/oauth/tokens/revoke").mock(
            return_value=Response(200, json={})
        )
        data = await _call(c, "codegen_revoke_oauth", {
            "provider": "linear",
            "confirmed": True,
        })
        assert data["action"] == "revoked"
        assert data["provider"] == "linear"


# ═══════════════════════════════════════════════════════════
# SETUP — CHECK SUITE
# ═══════════════════════════════════════════════════════════


class TestSetupCheckSuite:
    """codegen_get_check_suite_settings, codegen_update_check_suite_settings."""

    @respx.mock
    async def test_get_check_suite_settings(self, c: Client):
        respx.get(f"{BASE}/organizations/42/repos/check-suite-settings").mock(
            return_value=Response(200, json=CHECK_SUITE_JSON)
        )
        data = await _call(c, "codegen_get_check_suite_settings", {"repo_id": 10})
        assert data["check_retry_count"] == 2
        assert "lint" in data["ignored_checks"]
        assert "build" in data["available_check_suite_names"]

    @respx.mock
    async def test_update_check_suite_retry_count(self, c: Client):
        respx.put(f"{BASE}/organizations/42/repos/check-suite-settings").mock(
            return_value=Response(200, json={"status": "updated"})
        )
        data = await _call(c, "codegen_update_check_suite_settings", {
            "repo_id": 10,
            "check_retry_count": 5,
        })
        assert data["status"] == "updated"

    @respx.mock
    async def test_update_check_suite_ignored_checks(self, c: Client):
        respx.put(f"{BASE}/organizations/42/repos/check-suite-settings").mock(
            return_value=Response(200, json={"status": "updated"})
        )
        data = await _call(c, "codegen_update_check_suite_settings", {
            "repo_id": 10,
            "ignored_checks": ["lint", "formatting"],
            "high_priority_apps": ["ci", "deploy"],
        })
        assert data["status"] == "updated"


# ═══════════════════════════════════════════════════════════
# INTEGRATIONS
# ═══════════════════════════════════════════════════════════


class TestIntegrations:
    """codegen_get_integrations."""

    @respx.mock
    async def test_get_integrations(self, c: Client):
        respx.get(f"{BASE}/organizations/42/integrations").mock(
            return_value=Response(200, json=INTEGRATIONS_JSON)
        )
        data = await _call(c, "codegen_get_integrations", {})
        assert data["total_active"] == 1
        assert len(data["integrations"]) == 2
        assert data["integrations"][0]["type"] == "github"
        assert data["integrations"][0]["active"] is True


# ═══════════════════════════════════════════════════════════
# WEBHOOKS
# ═══════════════════════════════════════════════════════════


class TestWebhooks:
    """codegen_get_webhook_config, codegen_set/delete_webhook_config, codegen_test_webhook."""

    @respx.mock
    async def test_get_webhook_config(self, c: Client):
        respx.get(f"{BASE}/organizations/42/webhooks/agent-run").mock(
            return_value=Response(200, json=WEBHOOK_JSON)
        )
        data = await _call(c, "codegen_get_webhook_config", {})
        assert data["url"] == "https://example.com/hook"
        assert data["enabled"] is True
        assert data["has_secret"] is False

    @respx.mock
    async def test_set_webhook_config(self, c: Client):
        respx.post(f"{BASE}/organizations/42/webhooks/agent-run").mock(
            return_value=Response(200, json={"message": "Configured"})
        )
        data = await _call(c, "codegen_set_webhook_config", {
            "url": "https://new-hook.example.com/webhook",
            "enabled": True,
            "confirmed": True,
        })
        assert data["status"] == "configured"

    @respx.mock
    async def test_set_webhook_config_with_secret(self, c: Client):
        route = respx.post(f"{BASE}/organizations/42/webhooks/agent-run").mock(
            return_value=Response(200, json={"message": "OK"})
        )
        data = await _call(c, "codegen_set_webhook_config", {
            "url": "https://secure-hook.example.com",
            "secret": "s3cret",
            "confirmed": True,
        })
        assert data["status"] == "configured"
        body = json.loads(route.calls[0].request.content)
        assert body["secret"] == "s3cret"

    @respx.mock
    async def test_delete_webhook_config(self, c: Client):
        respx.delete(f"{BASE}/organizations/42/webhooks/agent-run").mock(
            return_value=Response(200, json={"message": "Deleted"})
        )
        data = await _call(c, "codegen_delete_webhook_config", {"confirmed": True})
        assert data["status"] == "deleted"

    @respx.mock
    async def test_test_webhook(self, c: Client):
        respx.post(f"{BASE}/organizations/42/webhooks/agent-run/test").mock(
            return_value=Response(200, json={"delivered": True})
        )
        data = await _call(c, "codegen_test_webhook", {"url": "https://example.com/hook"})
        assert data["status"] == "test_sent"


# ═══════════════════════════════════════════════════════════
# SANDBOX
# ═══════════════════════════════════════════════════════════


class TestSandbox:
    """codegen_analyze_sandbox_logs."""

    @respx.mock
    async def test_analyze_sandbox_logs(self, c: Client):
        respx.post(f"{BASE}/organizations/42/sandbox/99/analyze-logs").mock(
            return_value=Response(200, json=SANDBOX_LOG_JSON)
        )
        data = await _call(c, "codegen_analyze_sandbox_logs", {"sandbox_id": 99})
        assert data["agent_run_id"] == 99
        assert data["status"] == "analyzing"
        assert data["message"] == "Analysis started"


# ═══════════════════════════════════════════════════════════
# SLACK
# ═══════════════════════════════════════════════════════════


class TestSlack:
    """codegen_generate_slack_token."""

    @respx.mock
    async def test_generate_slack_token(self, c: Client):
        respx.post(f"{BASE}/slack-connect/generate-token").mock(
            return_value=Response(200, json=SLACK_TOKEN_JSON)
        )
        data = await _call(c, "codegen_generate_slack_token", {})
        assert data["token"] == "xoxb-test-token"
        assert data["expires_in_minutes"] == 10


# ═══════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════


class TestSettings:
    """codegen_get_settings, codegen_update_settings."""

    async def test_get_settings(self, c: Client):
        data = await _call(c, "codegen_get_settings", {})
        assert "auto_monitor" in data
        assert "poll_interval" in data

    async def test_update_settings_bool(self, c: Client):
        data = await _call(c, "codegen_update_settings", {
            "key": "auto_monitor",
            "value": "false",
        })
        assert data["updated"]["auto_monitor"] is False

    async def test_update_settings_int(self, c: Client):
        data = await _call(c, "codegen_update_settings", {
            "key": "poll_interval",
            "value": "60",
        })
        assert data["updated"]["poll_interval"] == 60

    async def test_update_settings_null(self, c: Client):
        data = await _call(c, "codegen_update_settings", {
            "key": "default_model",
            "value": "null",
        })
        assert data["updated"]["default_model"] is None

    async def test_update_settings_string(self, c: Client):
        data = await _call(c, "codegen_update_settings", {
            "key": "default_model",
            "value": "claude-3-5-sonnet",
        })
        assert data["updated"]["default_model"] == "claude-3-5-sonnet"

    async def test_update_settings_unknown_key(self, c: Client):
        data = await _call(c, "codegen_update_settings", {
            "key": "nonexistent_setting",
            "value": "foo",
        })
        assert "error" in data


# ═══════════════════════════════════════════════════════════
# ERROR SCENARIOS
# ═══════════════════════════════════════════════════════════


class TestErrorHandling:
    """Test HTTP errors propagate correctly through MCP."""

    @respx.mock
    async def test_404_on_get_run(self, c: Client):
        respx.get(f"{BASE}/organizations/42/agent/run/99999").mock(
            return_value=Response(404, json={"detail": "Run not found"})
        )
        with pytest.raises(Exception, match=r"404|not found|Not Found"):
            await _call(c, "codegen_get_run", {"run_id": 99999})

    @respx.mock
    async def test_401_unauthorized(self, c: Client):
        respx.get(f"{BASE}/organizations/42/agent/runs").mock(
            return_value=Response(401, json={"detail": "Invalid API key"})
        )
        # ErrorHandlingMiddleware transforms errors into tool results
        # so call_tool may raise ToolError or return an error text
        try:
            data = await _call(c, "codegen_list_runs", {})
            # If middleware transformed the error, response text contains error info
            resp_str = json.dumps(data, default=str)
            assert "401" in resp_str or "Invalid" in resp_str or "error" in resp_str.lower()
        except Exception as exc:
            assert "401" in str(exc) or "Invalid" in str(exc) or "Unauthorized" in str(exc)

    @respx.mock
    async def test_500_server_error(self, c: Client):
        respx.get(f"{BASE}/organizations/42/integrations").mock(
            return_value=Response(500, json={"detail": "Internal Server Error"})
        )
        # Server may retry and/or transform the error
        try:
            data = await _call(c, "codegen_get_integrations", {})
            resp_str = json.dumps(data, default=str)
            assert "500" in resp_str or "error" in resp_str.lower() or "Internal" in resp_str
        except Exception:
            pass  # Exception is also acceptable for server errors


# ═══════════════════════════════════════════════════════════
# EXECUTION CONTEXT + AGENT RUN FLOW
# ═══════════════════════════════════════════════════════════


class TestE2EFlow:
    """End-to-end: start execution → create run → get run with auto-report."""

    @respx.mock
    async def test_full_execution_flow(self, c: Client):
        # 1. Start execution
        respx.get(f"{BASE}/organizations/42/cli/rules").mock(
            return_value=Response(200, json=RULES_JSON)
        )
        respx.get(f"{BASE}/organizations/42/repos").mock(
            return_value=Response(200, json={"items": [], "total": 0})
        )

        exec_data = await _call(c, "codegen_start_execution", {
            "execution_id": "e2e-test",
            "goal": "E2E integration test",
            "tasks": [{"title": "Task 1", "description": "Build feature"}],
            "confirmed": True,
        })
        assert exec_data["execution_id"] == "e2e-test"

        # 2. Create run linked to execution
        respx.post(f"{BASE}/organizations/42/agent/run").mock(
            return_value=Response(200, json={
                "id": 300,
                "status": "queued",
                "web_url": "https://codegen.com/run/300",
            })
        )
        run_data = await _call(c, "codegen_create_run", {
            "prompt": "Build feature",
            "repo_id": 10,
            "execution_id": "e2e-test",
            "confirmed": True,
        })
        assert run_data["id"] == 300

        # 3. Get run with auto-report (simulating completion)
        respx.get(f"{BASE}/organizations/42/agent/run/300").mock(
            return_value=Response(200, json={
                "id": 300,
                "organization_id": 42,
                "status": "completed",
                "summary": "Feature built",
                "web_url": "https://codegen.com/run/300",
                "github_pull_requests": [
                    {
                        "url": "https://github.com/o/r/pull/10",
                        "number": 10, "title": "Add feature", "state": "open",
                    }
                ],
            })
        )
        respx.get(f"{BASE}/alpha/organizations/42/agent/run/300/logs").mock(
            return_value=Response(200, json={
                "id": 300,
                "status": "completed",
                "logs": [{"agent_run_id": 300, "thought": "Done", "tool_name": "write_file"}],
                "total_logs": 1,
            })
        )
        get_data = await _call(c, "codegen_get_run", {
            "run_id": 300,
            "execution_id": "e2e-test",
            "task_index": 0,
        })
        assert get_data["status"] == "completed"
        assert get_data["pull_requests"][0]["number"] == 10
        assert "parsed_logs" in get_data

        # 4. Verify execution context updated
        ctx_data = await _call(c, "codegen_get_execution_context", {"execution_id": "e2e-test"})
        assert ctx_data["tasks"][0]["status"] == "completed"


# ═══════════════════════════════════════════════════════════
# SUMMARY — printed at session end
# ═══════════════════════════════════════════════════════════


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print summary of all tool calls at the end of the test run."""
    if not _LOG_ENTRIES:
        return
    terminalreporter.section("MCP Integration Test Summary")
    ok = sum(1 for e in _LOG_ENTRIES if e["status"] == "OK")
    err = sum(1 for e in _LOG_ENTRIES if e["status"] == "ERROR")
    total_time = sum(e["elapsed_s"] for e in _LOG_ENTRIES)
    terminalreporter.write_line(f"  Total calls: {len(_LOG_ENTRIES)}")
    terminalreporter.write_line(f"  Passed: {ok}")
    terminalreporter.write_line(f"  Failed: {err}")
    terminalreporter.write_line(f"  Total time: {total_time:.3f}s")
    terminalreporter.write_line("")

    if err:
        terminalreporter.write_line("  Failed calls:")
        for e in _LOG_ENTRIES:
            if e["status"] == "ERROR":
                terminalreporter.write_line(f"    ✗ {e['tool']} — {e.get('error', 'unknown')}")
