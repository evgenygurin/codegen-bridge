"""Tests for bridge.sampling.schemas — structured output models."""

from __future__ import annotations

from bridge.sampling.schemas import (
    ExecutionSummary,
    LogAnalysis,
    RunSummary,
    TaskPrompt,
)


class TestRunSummary:
    def test_defaults(self):
        r = RunSummary()
        assert r.text == ""
        assert r.key_findings == []
        assert r.status_verdict == ""

    def test_str(self):
        r = RunSummary(text="hello")
        assert str(r) == "hello"

    def test_len(self):
        r = RunSummary(text="12345")
        assert len(r) == 5

    def test_full_construction(self):
        r = RunSummary(
            text="Summary",
            key_findings=["a", "b"],
            status_verdict="success",
        )
        assert r.key_findings == ["a", "b"]
        assert r.status_verdict == "success"

    def test_json_round_trip(self):
        original = RunSummary(text="hello", key_findings=["x"])
        restored = RunSummary.model_validate_json(original.model_dump_json())
        assert restored.text == original.text
        assert restored.key_findings == original.key_findings


class TestExecutionSummary:
    def test_defaults(self):
        r = ExecutionSummary()
        assert r.tasks_completed is None
        assert r.tasks_failed is None
        assert r.next_steps == []

    def test_full_construction(self):
        r = ExecutionSummary(
            text="Done",
            tasks_completed=5,
            tasks_failed=1,
            next_steps=["deploy"],
        )
        assert r.tasks_completed == 5
        assert r.tasks_failed == 1
        assert str(r) == "Done"


class TestTaskPrompt:
    def test_defaults(self):
        r = TaskPrompt()
        assert r.acceptance_criteria == []
        assert r.constraints == []

    def test_full_construction(self):
        r = TaskPrompt(
            text="Build API",
            acceptance_criteria=["passes tests"],
            constraints=["no breaking changes"],
        )
        assert r.acceptance_criteria == ["passes tests"]
        assert r.constraints == ["no breaking changes"]


class TestLogAnalysis:
    def test_defaults(self):
        r = LogAnalysis()
        assert r.severity == "info"
        assert r.error_patterns == []
        assert r.suggestions == []

    def test_full_construction(self):
        r = LogAnalysis(
            text="Analysis",
            severity="critical",
            error_patterns=["OOM"],
            suggestions=["increase memory"],
        )
        assert r.severity == "critical"
        assert r.error_patterns == ["OOM"]


class TestSamplingResultProtocol:
    """All result types support __str__ and __len__ for backward compat."""

    def test_all_types_support_str(self):
        for cls in (RunSummary, ExecutionSummary, TaskPrompt, LogAnalysis):
            result = cls(text="test")
            assert str(result) == "test"

    def test_all_types_support_len(self):
        for cls in (RunSummary, ExecutionSummary, TaskPrompt, LogAnalysis):
            result = cls(text="test")
            assert len(result) == 4

    def test_empty_text(self):
        for cls in (RunSummary, ExecutionSummary, TaskPrompt, LogAnalysis):
            result = cls()
            assert str(result) == ""
            assert len(result) == 0
