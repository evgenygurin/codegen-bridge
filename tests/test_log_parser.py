"""Tests for agent log parsing."""

from __future__ import annotations

from bridge.log_parser import parse_logs
from bridge.models import AgentLog


def _log(
    thought: str | None = None,
    tool_name: str | None = None,
    tool_input: dict | None = None,
    tool_output: str | dict | None = None,
) -> AgentLog:
    return AgentLog(
        agent_run_id=1,
        thought=thought,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
    )


class TestParseFiles:
    def test_extracts_write_file(self):
        logs = [_log(tool_name="write_file", tool_input={"path": "src/main.py"})]
        result = parse_logs(logs)
        assert "src/main.py" in result.files_changed

    def test_extracts_create_file(self):
        logs = [_log(tool_name="create_file", tool_input={"file_path": "new.py"})]
        result = parse_logs(logs)
        assert "new.py" in result.files_changed

    def test_extracts_edit_file(self):
        logs = [_log(tool_name="edit_file", tool_input={"target_file": "utils.py"})]
        result = parse_logs(logs)
        assert "utils.py" in result.files_changed

    def test_deduplicates_files(self):
        logs = [
            _log(tool_name="write_file", tool_input={"path": "a.py"}),
            _log(tool_name="edit_file", tool_input={"target_file": "a.py"}),
        ]
        result = parse_logs(logs)
        assert result.files_changed == ["a.py"]

    def test_ignores_none_tool_input(self):
        logs = [_log(tool_name="write_file", tool_input=None)]
        result = parse_logs(logs)
        assert result.files_changed == []


class TestParseDecisions:
    def test_extracts_decided(self):
        logs = [_log(thought="I decided to use JWT for auth")]
        result = parse_logs(logs)
        assert any("JWT" in d for d in result.key_decisions)

    def test_extracts_chose(self):
        logs = [_log(thought="I chose bcrypt over argon2")]
        result = parse_logs(logs)
        assert any("bcrypt" in d for d in result.key_decisions)

    def test_ignores_non_decision_thoughts(self):
        logs = [_log(thought="Reading the file contents")]
        result = parse_logs(logs)
        assert result.key_decisions == []


class TestParseTestResults:
    def test_extracts_pytest_output(self):
        logs = [_log(tool_name="bash", tool_output="5 passed, 1 failed in 2.3s")]
        result = parse_logs(logs)
        assert "5 passed" in result.test_results

    def test_extracts_from_dict_output(self):
        logs = [_log(tool_name="bash", tool_output={"stdout": "12 passed in 1.0s"})]
        result = parse_logs(logs)
        assert "12 passed" in result.test_results

    def test_uses_last_test_result(self):
        logs = [
            _log(tool_name="bash", tool_output="3 passed"),
            _log(tool_name="bash", tool_output="5 passed"),
        ]
        result = parse_logs(logs)
        assert "5 passed" in result.test_results


class TestParseCommands:
    def test_extracts_bash_commands(self):
        logs = [_log(tool_name="bash", tool_input={"command": "pytest -v"})]
        result = parse_logs(logs)
        assert "pytest -v" in result.commands_run


class TestParseAgentNotes:
    def test_uses_last_thought(self):
        logs = [
            _log(thought="Starting work"),
            _log(thought="All tests pass, creating PR"),
        ]
        result = parse_logs(logs)
        assert result.agent_notes == "All tests pass, creating PR"


class TestParseTotalSteps:
    def test_counts_all_logs(self):
        logs = [_log(thought="A"), _log(thought="B"), _log(thought="C")]
        result = parse_logs(logs)
        assert result.total_steps == 3
