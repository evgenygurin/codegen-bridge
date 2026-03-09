"""Unit tests for RunService business logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bridge.context import ContextRegistry, ExecutionContext, TaskContext
from bridge.helpers.pagination import offset_to_cursor
from bridge.helpers.repo_detection import RepoCache
from bridge.models import AgentLog, AgentRun, AgentRunWithLogs, Page, PullRequest
from bridge.services.runs import RunService


@pytest.fixture
def mock_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_registry() -> MagicMock:
    registry = MagicMock(spec=ContextRegistry)
    registry.get = AsyncMock()
    registry.update_task = AsyncMock()
    registry._save = AsyncMock()
    return registry


@pytest.fixture
def mock_repo_cache() -> MagicMock:
    return MagicMock(spec=RepoCache)


@pytest.fixture
def svc(
    mock_client: AsyncMock,
    mock_registry: MagicMock,
    mock_repo_cache: MagicMock,
) -> RunService:
    return RunService(
        client=mock_client,
        registry=mock_registry,
        repo_cache=mock_repo_cache,
    )


def _make_run(**overrides: object) -> AgentRun:
    payload: dict[str, object] = {
        "id": 42,
        "status": "completed",
        "result": None,
        "summary": "Did the thing",
        "source_type": "mcp",
        "github_pull_requests": None,
    }
    payload.update(overrides)
    if "web_url" not in payload:
        payload["web_url"] = f"https://codegen.com/run/{payload['id']}"
    return AgentRun(**payload)


def _make_execution_context(
    *,
    execution_id: str = "exec-1",
    repo_id: int | None = None,
    current_task_index: int = 0,
) -> ExecutionContext:
    return ExecutionContext(
        id=execution_id,
        mode="plan",
        goal="Ship feature",
        repo_id=repo_id,
        current_task_index=current_task_index,
        tasks=[
            TaskContext(index=0, title="Task 1", description="Implement task 1"),
            TaskContext(index=1, title="Task 2", description="Implement task 2"),
        ],
    )


class TestGetRun:
    async def test_happy_path(self, svc: RunService, mock_client: AsyncMock) -> None:
        mock_client.get_run.return_value = _make_run()

        result = await svc.get_run(42)

        mock_client.get_run.assert_awaited_once_with(42)
        assert result["id"] == 42
        assert result["status"] == "completed"
        assert result["summary"] == "Did the thing"
        assert result["web_url"] == "https://codegen.com/run/42"

    async def test_with_prs(self, svc: RunService, mock_client: AsyncMock) -> None:
        mock_client.get_run.return_value = _make_run(
            github_pull_requests=[
                PullRequest(
                    url="https://github.com/org/repo/pull/7",
                    title="Fix regression",
                    number=7,
                    state="open",
                )
            ]
        )

        result = await svc.get_run(42)

        assert "pull_requests" in result
        assert result["pull_requests"][0]["url"] == "https://github.com/org/repo/pull/7"
        assert result["pull_requests"][0]["number"] == 7


class TestListRuns:
    async def test_pagination(self, svc: RunService, mock_client: AsyncMock) -> None:
        mock_client.list_runs.return_value = Page(
            items=[
                _make_run(id=10, created_at="2026-03-09T10:00:00Z"),
                _make_run(id=11, created_at="2026-03-09T11:00:00Z"),
            ],
            total=9,
        )
        cursor = offset_to_cursor(4)

        result = await svc.list_runs(limit=2, cursor=cursor)

        mock_client.list_runs.assert_awaited_once_with(
            skip=4,
            limit=2,
            source_type=None,
            user_id=None,
        )
        assert len(result["runs"]) == 2
        assert result["total"] == 9
        assert result["next_cursor"] is not None

    async def test_filters(self, svc: RunService, mock_client: AsyncMock) -> None:
        mock_client.list_runs.return_value = Page(items=[], total=0)

        await svc.list_runs(source_type="mcp", user_id=99)

        mock_client.list_runs.assert_awaited_once_with(
            skip=0,
            limit=20,
            source_type="mcp",
            user_id=99,
        )


class TestCreateRun:
    async def test_happy_path(self, svc: RunService, mock_client: AsyncMock) -> None:
        mock_client.create_run.return_value = _make_run(id=99, status="queued")

        result = await svc.create_run("Fix the bug", repo_id=10)

        mock_client.create_run.assert_awaited_once_with(
            "Fix the bug",
            repo_id=10,
            model=None,
            agent_type="claude_code",
            images=None,
        )
        assert result == {
            "id": 99,
            "status": "queued",
            "web_url": "https://codegen.com/run/99",
        }


class TestTrackRunInExecution:
    async def test_tracks_execution(
        self,
        svc: RunService,
        mock_registry: MagicMock,
    ) -> None:
        mock_registry.get.return_value = _make_execution_context(execution_id="exec-42")

        await svc.track_run_in_execution(run_id=123, execution_id="exec-42", task_index=1)

        mock_registry.get.assert_awaited_once_with("exec-42")
        mock_registry.update_task.assert_awaited_once_with(
            execution_id="exec-42",
            task_index=1,
            run_id=123,
        )


class TestDetectRepo:
    async def test_found(self, svc: RunService) -> None:
        with patch("bridge.services.runs.detect_repo_id", new_callable=AsyncMock) as detect:
            detect.return_value = 777

            result = await svc.detect_repo()

        assert result == 777

    async def test_not_found(self, svc: RunService) -> None:
        with patch("bridge.services.runs.detect_repo_id", new_callable=AsyncMock) as detect:
            detect.return_value = None

            result = await svc.detect_repo()

        assert result is None


class TestEnrichPrompt:
    async def test_with_execution(
        self,
        svc: RunService,
        mock_registry: MagicMock,
    ) -> None:
        mock_registry.get.return_value = _make_execution_context(
            execution_id="exec-100",
            repo_id=55,
        )
        with patch("bridge.services.runs.build_task_prompt") as build_prompt:
            build_prompt.return_value = "ENRICHED PROMPT"

            prompt, repo_id = await svc.enrich_prompt("Original", "exec-100", 0)

        assert prompt == "ENRICHED PROMPT"
        assert repo_id == 55
        mock_registry.update_task.assert_awaited_once_with(
            execution_id="exec-100",
            task_index=0,
            status="running",
        )

    async def test_without_execution(self, svc: RunService) -> None:
        prompt, repo_id = await svc.enrich_prompt("Original", None, None)

        assert prompt == "Original"
        assert repo_id is None


class TestStopRun:
    async def test_happy_path(self, svc: RunService, mock_client: AsyncMock) -> None:
        mock_client.stop_run.return_value = _make_run(id=42, status="stopped")

        result = await svc.stop_run(42)

        mock_client.stop_run.assert_awaited_once_with(42)
        assert result == {
            "id": 42,
            "status": "stopped",
            "web_url": "https://codegen.com/run/42",
        }

    async def test_action_payload(self, svc: RunService, mock_client: AsyncMock) -> None:
        mock_client.stop_run.return_value = MagicMock(
            id=None,
            agent_run_id=42,
            status="success",
            web_url=None,
            message="Run stopped",
        )

        result = await svc.stop_run(42)

        assert result == {
            "id": 42,
            "status": "success",
            "web_url": None,
            "message": "Run stopped",
        }


class TestReportRunResult:
    async def test_happy_path(
        self,
        svc: RunService,
        mock_client: AsyncMock,
        mock_registry: MagicMock,
    ) -> None:
        mock_client.get_run.return_value = _make_run(status="completed", summary="Done")
        mock_client.get_logs.return_value = AgentRunWithLogs(id=42, logs=[], total_logs=0)
        mock_registry.get.return_value = _make_execution_context(execution_id="exec-3")

        parsed = MagicMock()
        parsed.files_changed = ["bridge/server.py"]
        parsed.key_decisions = ["Used service layer"]
        parsed.test_results = "1107 passed"
        parsed.agent_notes = "No regressions"
        parsed.commands_run = ["uv run pytest -v"]
        parsed.total_steps = 4

        with patch("bridge.services.runs.parse_logs", return_value=parsed):
            result = await svc.report_run_result(42, "exec-3", task_index=0)

        mock_client.get_run.assert_awaited_once_with(42)
        mock_client.get_logs.assert_awaited_once_with(42, limit=100)
        mock_registry.update_task.assert_awaited_once()
        update_call = mock_registry.update_task.await_args.kwargs
        assert update_call["execution_id"] == "exec-3"
        assert update_call["task_index"] == 0
        assert update_call["status"] == "completed"
        assert update_call["report"].summary == "Done"
        assert result["reported"] is True
        assert result["task_status"] == "completed"


class TestGetLogs:
    async def test_happy_path(self, svc: RunService, mock_client: AsyncMock) -> None:
        mock_client.get_logs.return_value = AgentRunWithLogs(
            id=42,
            status="completed",
            total_logs=2,
            logs=[
                AgentLog(
                    agent_run_id=42,
                    thought="thinking",
                    tool_name="write_file",
                    created_at="2026-03-09T10:00:00Z",
                ),
                AgentLog(
                    agent_run_id=42,
                    thought="done",
                    created_at="2026-03-09T10:01:00Z",
                ),
            ],
        )

        result = await svc.get_logs(42, limit=2, reverse=True, cursor=None)

        mock_client.get_logs.assert_awaited_once_with(42, skip=0, limit=2, reverse=True)
        assert result["run_id"] == 42
        assert result["total_logs"] == 2
        assert len(result["logs"]) == 2
        assert result["logs"][0]["tool_name"] == "write_file"
        assert "tool_name" not in result["logs"][1]
