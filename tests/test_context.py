"""Tests for execution context models and ContextRegistry."""

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

# ── Model Tests ─────────────────────────────────────────


class TestModels:
    def test_task_report_defaults(self):
        report = TaskReport()
        assert report.summary == ""
        assert report.pull_requests == []
        assert report.web_url is None

    def test_task_report_with_pr(self):
        pr = PRInfo(url="https://github.com/o/r/pull/1", number=1, title="Fix")
        report = TaskReport(summary="Done", pull_requests=[pr])
        assert len(report.pull_requests) == 1
        assert report.pull_requests[0].number == 1

    def test_task_context_defaults(self):
        task = TaskContext(title="Build it")
        assert task.status == "pending"
        assert task.run_id is None
        assert task.report is None

    def test_execution_context_defaults(self):
        ctx = ExecutionContext(id="test-1", goal="Test")
        assert ctx.mode == "adhoc"
        assert ctx.status == "active"
        assert ctx.tasks == []

    def test_execution_context_roundtrip(self):
        ctx = ExecutionContext(
            id="rt",
            mode="plan",
            goal="Ship it",
            tasks=[TaskContext(title="Step 1")],
        )
        data = json.loads(ctx.model_dump_json())
        loaded = ExecutionContext.model_validate(data)
        assert loaded.id == "rt"
        assert loaded.tasks[0].title == "Step 1"


# ── ContextRegistry Tests ──────────────────────────────


class TestContextRegistry:
    @pytest.fixture()
    def storage_dir(self, tmp_path):
        return tmp_path / "executions"

    @pytest.fixture()
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
        assert ctx.mode == "plan"
        assert len(ctx.tasks) == 1
        assert ctx.tasks[0].title == "Setup models"

    def test_start_adhoc_execution(self, registry):
        ctx = registry.start_execution(
            execution_id="adhoc-1",
            mode="adhoc",
            goal="Fix the bug",
        )
        assert ctx.mode == "adhoc"
        assert len(ctx.tasks) == 1
        assert ctx.tasks[0].title == "Fix the bug"

    def test_persists_to_disk(self, registry, storage_dir):
        registry.start_execution(
            execution_id="persist-test",
            mode="adhoc",
            goal="Test persistence",
        )
        file = storage_dir / "persist-test.json"
        assert file.exists()
        data = json.loads(file.read_text())
        assert data["id"] == "persist-test"

    def test_get_returns_cached(self, registry):
        registry.start_execution(execution_id="cached", mode="adhoc", goal="Test")
        ctx = registry.get("cached")
        assert ctx is not None
        assert ctx.id == "cached"

    def test_get_returns_none_for_missing(self, registry):
        assert registry.get("nonexistent") is None

    def test_loads_from_disk_on_get(self, storage_dir):
        ctx = ExecutionContext(id="disk-test", mode="adhoc", goal="Disk", status="active")
        storage_dir.mkdir(parents=True, exist_ok=True)
        (storage_dir / "disk-test.json").write_text(ctx.model_dump_json(indent=2))
        registry2 = ContextRegistry(storage_dir=storage_dir)
        loaded = registry2.get("disk-test")
        assert loaded is not None
        assert loaded.goal == "Disk"

    def test_update_task_status(self, registry):
        registry.start_execution(
            execution_id="upd",
            mode="plan",
            goal="Test",
            tasks=[("T1", "Do stuff")],
        )
        registry.update_task(execution_id="upd", task_index=0, status="running", run_id=99)
        ctx = registry.get("upd")
        assert ctx.tasks[0].status == "running"
        assert ctx.tasks[0].run_id == 99

    def test_update_task_report(self, registry):
        registry.start_execution(
            execution_id="rpt",
            mode="plan",
            goal="Test",
            tasks=[("T1", "Do stuff")],
        )
        report = TaskReport(summary="Done", web_url="https://codegen.com/run/1")
        registry.update_task(
            execution_id="rpt",
            task_index=0,
            status="completed",
            report=report,
        )
        ctx = registry.get("rpt")
        assert ctx.tasks[0].status == "completed"
        assert ctx.tasks[0].report.summary == "Done"

    def test_get_active_returns_active_execution(self, registry):
        registry.start_execution(execution_id="active-1", mode="adhoc", goal="Active")
        active = registry.get_active()
        assert active is not None
        assert active.id == "active-1"

    def test_get_active_returns_none_when_all_completed(self, registry):
        ctx = registry.start_execution(execution_id="done", mode="adhoc", goal="Done")
        ctx.status = "completed"
        registry._save(ctx)
        assert registry.get_active() is None

    def test_update_task_raises_for_missing_execution(self, registry):
        with pytest.raises(KeyError, match="not-here"):
            registry.update_task(execution_id="not-here", task_index=0, status="running")

    def test_update_persists_to_disk(self, registry, storage_dir):
        registry.start_execution(
            execution_id="persist-upd",
            mode="plan",
            goal="Test",
            tasks=[("T1", "Do stuff")],
        )
        registry.update_task(
            execution_id="persist-upd", task_index=0, status="completed"
        )
        # Load fresh from disk
        data = json.loads((storage_dir / "persist-upd.json").read_text())
        assert data["tasks"][0]["status"] == "completed"
