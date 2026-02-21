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
            return_value=Response(
                200, json={"id": 1, "status": "stopped", "web_url": "https://codegen.com/run/1"}
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            run = await client.stop_run(1)

        assert run.id == 1
        assert run.status == "stopped"


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
