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
    def storage_dir(self, tmp_path):
        return tmp_path / "executions"

    @pytest.fixture
    def registry(self, storage_dir):
        return ContextRegistry(storage_dir=storage_dir)

    def test_creates_storage_dir(self, registry, storage_dir):
        assert storage_dir.exists()

    def test_start_plan_execution(self, registry):
        ctx = registry.start_execution(
            execution_id="test-1",
            mode="plan",
            goal="Build auth",
            tasks=[("Setup models", "Create User model and migration")],
        )
        assert ctx.id == "test-1"
        assert len(ctx.tasks) == 1

    def test_start_adhoc_execution(self, registry):
        ctx = registry.start_execution(execution_id="adhoc-1", mode="adhoc", goal="Fix the bug")
        assert len(ctx.tasks) == 1
        assert ctx.tasks[0].title == "Fix the bug"

    def test_persists_to_disk(self, registry, storage_dir):
        registry.start_execution(
            execution_id="persist-test", mode="adhoc", goal="Test persistence"
        )
        assert (storage_dir / "persist-test.json").exists()

    def test_get_returns_cached(self, registry):
        registry.start_execution(execution_id="cached", mode="adhoc", goal="Test")
        assert registry.get("cached") is not None

    def test_get_returns_none_for_missing(self, registry):
        assert registry.get("nonexistent") is None

    def test_update_task_status(self, registry):
        registry.start_execution(
            execution_id="upd", mode="plan", goal="Test", tasks=[("T1", "Do stuff")]
        )
        registry.update_task(execution_id="upd", task_index=0, status="running", run_id=99)
        ctx = registry.get("upd")
        assert ctx.tasks[0].status == "running"
        assert ctx.tasks[0].run_id == 99

    def test_get_active_returns_active_execution(self, registry):
        registry.start_execution(execution_id="active-1", mode="adhoc", goal="Active")
        assert registry.get_active() is not None

    def test_loads_from_disk_when_not_cached(self, storage_dir):
        """Verify that a context persisted by one registry can be loaded by a fresh one."""
        reg1 = ContextRegistry(storage_dir=storage_dir)
        reg1.start_execution(execution_id="disk-load", mode="adhoc", goal="Persist me")

        # New registry instance (empty cache) should load from disk
        reg2 = ContextRegistry(storage_dir=storage_dir)
        ctx = reg2.get("disk-load")
        assert ctx is not None
        assert ctx.goal == "Persist me"

    def test_get_active_from_disk(self, storage_dir):
        """get_active() should scan disk if cache has no active contexts."""
        reg1 = ContextRegistry(storage_dir=storage_dir)
        reg1.start_execution(execution_id="disk-active", mode="adhoc", goal="Active on disk")

        reg2 = ContextRegistry(storage_dir=storage_dir)
        active = reg2.get_active()
        assert active is not None
        assert active.id == "disk-active"

    def test_update_task_with_report(self, registry):
        registry.start_execution(
            execution_id="rpt", mode="plan", goal="Test", tasks=[("T1", "Do stuff")]
        )
        report = TaskReport(summary="All done", web_url="https://codegen.com/run/1")
        registry.update_task(execution_id="rpt", task_index=0, report=report)
        ctx = registry.get("rpt")
        assert ctx.tasks[0].report is not None
        assert ctx.tasks[0].report.summary == "All done"

    def test_update_task_out_of_bounds(self, registry):
        """update_task with an invalid index should be a no-op."""
        registry.start_execution(
            execution_id="oob", mode="plan", goal="Test", tasks=[("T1", "Do")]
        )
        # Should not raise
        registry.update_task(execution_id="oob", task_index=999, status="running")
