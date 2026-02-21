"""Tests for execution context models and registry."""

from __future__ import annotations

import json
from pathlib import Path

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
