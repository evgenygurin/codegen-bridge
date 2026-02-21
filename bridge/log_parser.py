"""Parse Codegen agent logs into structured data."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bridge.models import AgentLog

_FILE_TOOLS = {"write_file", "create_file", "edit_file", "str_replace_editor"}
_PATH_KEYS = ("path", "file_path", "target_file", "filename")
_DECISION_PATTERNS = re.compile(
    r"\b(decided|chose|chosen|choosing|using|approach|opted|selected|went with)\b",
    re.IGNORECASE,
)
_TEST_RESULT_PATTERNS = re.compile(r"\d+\s+(passed|failed|error)", re.IGNORECASE)


@dataclass
class ParsedLogs:
    """Structured data extracted from agent logs."""

    files_changed: list[str] = field(default_factory=list)
    key_decisions: list[str] = field(default_factory=list)
    test_results: str | None = None
    agent_notes: str | None = None
    commands_run: list[str] = field(default_factory=list)
    total_steps: int = 0


def parse_logs(logs: list[AgentLog]) -> ParsedLogs:
    """Extract structured data from a list of agent log entries."""
    result = ParsedLogs(total_steps=len(logs))
    seen_files: set[str] = set()
    for log in logs:
        _extract_files(log, result, seen_files)
        _extract_decisions(log, result)
        _extract_test_results(log, result)
        _extract_commands(log, result)
        _extract_notes(log, result)
    return result


def _extract_files(log: AgentLog, result: ParsedLogs, seen: set[str]) -> None:
    if log.tool_name not in _FILE_TOOLS:
        return
    if not log.tool_input:
        return
    for key in _PATH_KEYS:
        path = log.tool_input.get(key)
        if path and isinstance(path, str) and path not in seen:
            seen.add(path)
            result.files_changed.append(path)
            break


def _extract_decisions(log: AgentLog, result: ParsedLogs) -> None:
    if not log.thought:
        return
    if _DECISION_PATTERNS.search(log.thought):
        result.key_decisions.append(log.thought)


def _extract_test_results(log: AgentLog, result: ParsedLogs) -> None:
    if log.tool_name != "bash":
        return
    output = log.tool_output
    if isinstance(output, dict):
        output = output.get("stdout", "") or output.get("output", "")
    if not isinstance(output, str):
        return
    if _TEST_RESULT_PATTERNS.search(output):
        result.test_results = output


def _extract_commands(log: AgentLog, result: ParsedLogs) -> None:
    if log.tool_name != "bash":
        return
    if not log.tool_input:
        return
    cmd = log.tool_input.get("command")
    if cmd and isinstance(cmd, str):
        result.commands_run.append(cmd)


def _extract_notes(log: AgentLog, result: ParsedLogs) -> None:
    if log.thought:
        result.agent_notes = log.thought
