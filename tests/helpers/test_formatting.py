"""Tests for response formatting helpers."""

from __future__ import annotations

import json

from bridge.helpers.formatting import format_logs, format_run, format_run_basic, format_run_list
from bridge.models import AgentLog, AgentRun, AgentRunWithLogs


def _run(**overrides) -> AgentRun:
    defaults = {"id": 1, "status": "completed", "web_url": "https://codegen.com/run/1"}
    defaults.update(overrides)
    return AgentRun(**defaults)


class TestFormatRun:
    def test_includes_core_fields(self):
        result = format_run(_run())
        assert result["id"] == 1
        assert result["status"] == "completed"
        assert result["web_url"] == "https://codegen.com/run/1"

    def test_includes_result_when_present(self):
        result = format_run(_run(result="Fixed the bug"))
        assert result["result"] == "Fixed the bug"

    def test_includes_summary_when_present(self):
        result = format_run(_run(summary="Bug fix applied"))
        assert result["summary"] == "Bug fix applied"

    def test_excludes_none_result(self):
        result = format_run(_run(result=None))
        assert "result" not in result

    def test_excludes_none_summary(self):
        result = format_run(_run(summary=None))
        assert "summary" not in result


class TestFormatRunBasic:
    def test_returns_json_string(self):
        output = format_run_basic(_run())
        data = json.loads(output)
        assert data["id"] == 1
        assert data["status"] == "completed"
        assert data["web_url"] == "https://codegen.com/run/1"

    def test_only_includes_three_fields(self):
        output = format_run_basic(_run(result="extra", summary="extra"))
        data = json.loads(output)
        assert set(data.keys()) == {"id", "status", "web_url"}


class TestFormatRunList:
    def test_returns_json_with_total_and_runs(self):
        runs = [_run(id=1), _run(id=2, status="running")]
        output = format_run_list(runs, total=5)
        data = json.loads(output)
        assert data["total"] == 5
        assert len(data["runs"]) == 2
        assert data["runs"][0]["id"] == 1
        assert data["runs"][1]["status"] == "running"

    def test_empty_list(self):
        output = format_run_list([], total=0)
        data = json.loads(output)
        assert data["total"] == 0
        assert data["runs"] == []


class TestFormatLogs:
    def test_formats_log_entries(self):
        result = AgentRunWithLogs(
            id=1,
            status="running",
            logs=[
                AgentLog(agent_run_id=1, thought="Reading code", tool_name="read_file"),
                AgentLog(agent_run_id=1, thought="Found issue"),
            ],
            total_logs=2,
        )
        output = format_logs(result)
        data = json.loads(output)
        assert data["run_id"] == 1
        assert data["total_logs"] == 2
        assert data["logs"][0]["thought"] == "Reading code"
        assert data["logs"][0]["tool_name"] == "read_file"

    def test_omits_none_fields_from_logs(self):
        result = AgentRunWithLogs(
            id=1,
            status="completed",
            logs=[AgentLog(agent_run_id=1, thought="Done")],
            total_logs=1,
        )
        output = format_logs(result)
        data = json.loads(output)
        log_entry = data["logs"][0]
        assert "thought" in log_entry
        assert "tool_name" not in log_entry
        assert "tool_input" not in log_entry

    def test_truncates_long_tool_output(self):
        long_output = "x" * 1000
        result = AgentRunWithLogs(
            id=1,
            status="running",
            logs=[
                AgentLog(agent_run_id=1, tool_name="bash", tool_output=long_output),
            ],
            total_logs=1,
        )
        output = format_logs(result)
        data = json.loads(output)
        assert len(data["logs"][0]["tool_output"]) <= 500
