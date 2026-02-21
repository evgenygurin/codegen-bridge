"""Tests for execution context models and registry."""

from __future__ import annotations

import json

import pytest

from bridge.context import (
    ContextRegistry,
    ExecutionContext,
    PRInfo,
    TaskContext,
    TaskReport,
)
from bridge.storage import MemoryStorage


class TestPRInfo:
    def test_creates_with_required_fields(self):
        pr = PRInfo(url="https://github.com/o/r/pull/1", number=1, title="Fix", state="open")
        assert pr.number == 1

    def test_optional_branch(self):
        pr = PRInfo(url="https://github.com/o/r/pull/1", number=1, title="Fix", state="open")
        assert pr.branch is None


class TestTaskReport:
    def test_creates_with_summary(self):
        report = TaskReport(summary="Did the thing", web_url="https://codegen.com/run/1")
        assert report.summary == "Did the thing"
        assert report.files_changed == []
        assert report.key_decisions == []

    def test_serializes_to_json(self):
        report = TaskReport(
            summary="Done",
            web_url="https://codegen.com/run/1",
            files_changed=["src/main.py"],
            pull_requests=[
                PRInfo(url="https://github.com/o/r/pull/5", number=5, title="PR", state="open")
            ],
        )
        data = json.loads(report.model_dump_json())
        assert data["files_changed"] == ["src/main.py"]
        assert data["pull_requests"][0]["number"] == 5


class TestTaskContext:
    def test_default_status_is_pending(self):
        task = TaskContext(index=0, title="Task 1", description="Do stuff")
        assert task.status == "pending"
        assert task.run_id is None
        assert task.report is None


class TestExecutionContext:
    def test_creates_plan_execution(self):
        ctx = ExecutionContext(
            id="test-plan",
            mode="plan",
            goal="Build auth",
            status="active",
        )
        assert ctx.mode == "plan"
        assert ctx.tasks == []
        assert ctx.current_task_index == 0

    def test_creates_adhoc_execution(self):
        ctx = ExecutionContext(
            id="adhoc-123",
            mode="adhoc",
            goal="Fix login bug",
            status="active",
        )
        assert ctx.mode == "adhoc"

    def test_serializes_round_trip(self):
        ctx = ExecutionContext(
            id="rt-test",
            mode="plan",
            goal="Test",
            status="active",
            tech_stack=["Python", "FastAPI"],
            tasks=[TaskContext(index=0, title="T1", description="Do")],
        )
        data = json.loads(ctx.model_dump_json())
        restored = ExecutionContext.model_validate(data)
        assert restored.id == "rt-test"
        assert restored.tasks[0].title == "T1"


class TestContextRegistry:
    @pytest.fixture
    async def registry(self):
        storage = MemoryStorage()
        reg = ContextRegistry(storage=storage)
        await reg.setup()
        return reg

    async def test_start_plan_execution(self, registry):
        ctx = await registry.start_execution(
            execution_id="test-1",
            mode="plan",
            goal="Build auth",
            tasks=[("Setup models", "Create User model and migration")],
        )
        assert ctx.id == "test-1"
        assert len(ctx.tasks) == 1

    async def test_start_adhoc_execution(self, registry):
        ctx = await registry.start_execution(
            execution_id="adhoc-1", mode="adhoc", goal="Fix the bug"
        )
        assert len(ctx.tasks) == 1
        assert ctx.tasks[0].title == "Fix the bug"

    async def test_persists_to_store(self, registry):
        await registry.start_execution(
            execution_id="persist-test", mode="adhoc", goal="Test persistence"
        )
        # Verify the data is in the underlying storage
        data = await registry._storage.get("persist-test")
        assert data is not None
        assert data["id"] == "persist-test"

    async def test_get_returns_cached(self, registry):
        await registry.start_execution(execution_id="cached", mode="adhoc", goal="Test")
        assert await registry.get("cached") is not None

    async def test_get_returns_none_for_missing(self, registry):
        assert await registry.get("nonexistent") is None

    async def test_update_task_status(self, registry):
        await registry.start_execution(
            execution_id="upd", mode="plan", goal="Test", tasks=[("T1", "Do stuff")]
        )
        await registry.update_task(
            execution_id="upd", task_index=0, status="running", run_id=99
        )
        ctx = await registry.get("upd")
        assert ctx.tasks[0].status == "running"
        assert ctx.tasks[0].run_id == 99

    async def test_get_active_returns_active_execution(self, registry):
        await registry.start_execution(execution_id="active-1", mode="adhoc", goal="Active")
        assert await registry.get_active() is not None

    async def test_loads_from_store_when_not_cached(self):
        """Verify that a context persisted by one registry can be loaded by a fresh one."""
        storage = MemoryStorage()
        reg1 = ContextRegistry(storage=storage)
        await reg1.setup()
        await reg1.start_execution(
            execution_id="store-load", mode="adhoc", goal="Persist me"
        )

        # New registry instance sharing the same storage (empty cache)
        reg2 = ContextRegistry(storage=storage)
        await reg2.setup()
        ctx = await reg2.get("store-load")
        assert ctx is not None
        assert ctx.goal == "Persist me"

    async def test_get_active_from_store(self):
        """get_active() should scan store if cache has no active contexts."""
        storage = MemoryStorage()
        reg1 = ContextRegistry(storage=storage)
        await reg1.setup()
        await reg1.start_execution(
            execution_id="store-active", mode="adhoc", goal="Active in store"
        )

        reg2 = ContextRegistry(storage=storage)
        await reg2.setup()
        active = await reg2.get_active()
        assert active is not None
        assert active.id == "store-active"

    async def test_update_task_with_report(self, registry):
        await registry.start_execution(
            execution_id="rpt", mode="plan", goal="Test", tasks=[("T1", "Do stuff")]
        )
        report = TaskReport(summary="All done", web_url="https://codegen.com/run/1")
        await registry.update_task(execution_id="rpt", task_index=0, report=report)
        ctx = await registry.get("rpt")
        assert ctx.tasks[0].report is not None
        assert ctx.tasks[0].report.summary == "All done"

    async def test_update_task_out_of_bounds(self, registry):
        """update_task with an invalid index should be a no-op."""
        await registry.start_execution(
            execution_id="oob", mode="plan", goal="Test", tasks=[("T1", "Do")]
        )
        # Should not raise
        await registry.update_task(execution_id="oob", task_index=999, status="running")
