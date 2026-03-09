"""Unit tests for ExecutionService business logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bridge.context import ContextRegistry, ExecutionContext, TaskContext
from bridge.helpers.repo_detection import RepoCache
from bridge.services.execution import ExecutionService


@pytest.fixture
def mock_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_registry() -> MagicMock:
    registry = MagicMock(spec=ContextRegistry)
    registry.start_execution = AsyncMock()
    registry.get = AsyncMock()
    registry.get_active = AsyncMock()
    return registry


@pytest.fixture
def mock_repo_cache() -> MagicMock:
    return MagicMock(spec=RepoCache)


@pytest.fixture
def svc(
    mock_client: AsyncMock,
    mock_registry: MagicMock,
    mock_repo_cache: MagicMock,
) -> ExecutionService:
    return ExecutionService(
        client=mock_client,
        registry=mock_registry,
        repo_cache=mock_repo_cache,
    )


def _make_execution_context(execution_id: str) -> ExecutionContext:
    return ExecutionContext(
        id=execution_id,
        mode="plan",
        goal="Build feature",
        status="active",
        tasks=[
            TaskContext(index=0, title="Step 1", description="Scaffold"),
            TaskContext(index=1, title="Step 2", description="Implement"),
        ],
    )


class TestStartExecution:
    async def test_creates_context(
        self,
        svc: ExecutionService,
        mock_registry: MagicMock,
    ) -> None:
        mock_registry.start_execution.return_value = _make_execution_context("exec-1")

        result = await svc.start_execution(
            execution_id="exec-1",
            goal="Build auth system",
            mode="plan",
            tasks=[
                {"title": "Step 1", "description": "Scaffold"},
                {"title": "Step 2", "description": "Implement"},
            ],
        )

        mock_registry.start_execution.assert_awaited_once_with(
            execution_id="exec-1",
            mode="plan",
            goal="Build auth system",
            tasks=[("Step 1", "Scaffold"), ("Step 2", "Implement")],
        )
        assert result["execution_id"] == "exec-1"
        assert result["status"] == "active"
        assert result["tasks"] == 2


class TestGetExecutionContext:
    async def test_exists(
        self,
        svc: ExecutionService,
        mock_registry: MagicMock,
    ) -> None:
        mock_registry.get.return_value = _make_execution_context("exec-2")

        ctx = await svc.get_execution_context("exec-2")

        mock_registry.get.assert_awaited_once_with("exec-2")
        assert ctx is not None
        assert ctx.id == "exec-2"
        assert ctx.status == "active"

    async def test_not_found(
        self,
        svc: ExecutionService,
        mock_registry: MagicMock,
    ) -> None:
        mock_registry.get.return_value = None

        ctx = await svc.get_execution_context("missing")

        assert ctx is None


class TestGetAgentRules:
    async def test_happy_path(
        self,
        svc: ExecutionService,
        mock_client: AsyncMock,
    ) -> None:
        mock_client.get_rules.return_value = {
            "organization_rules": "Rule 1",
            "user_custom_prompt": "Rule 2",
        }

        result = await svc.get_agent_rules()

        mock_client.get_rules.assert_awaited_once()
        assert result == {
            "organization_rules": "Rule 1",
            "user_custom_prompt": "Rule 2",
        }
