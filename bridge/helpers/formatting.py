"""Response formatting helpers for MCP tools."""

from __future__ import annotations

import json
from typing import Any

from bridge.models import AgentRun, AgentRunWithLogs


def format_run(run: AgentRun) -> dict[str, Any]:
    """Format an AgentRun into a JSON-serializable dict with core fields."""
    result: dict[str, Any] = {
        "id": run.id,
        "status": run.status,
        "web_url": run.web_url,
    }
    if run.result:
        result["result"] = run.result
    if run.summary:
        result["summary"] = run.summary
    return result


def format_run_basic(run: AgentRun) -> str:
    """Format an AgentRun into a JSON string with id, status, web_url."""
    return json.dumps(
        {
            "id": run.id,
            "status": run.status,
            "web_url": run.web_url,
        }
    )


def format_run_list(runs: list[AgentRun], total: int) -> str:
    """Format a list of AgentRuns into a JSON string."""
    return json.dumps(
        {
            "total": total,
            "runs": [
                {
                    "id": r.id,
                    "status": r.status,
                    "created_at": r.created_at,
                    "web_url": r.web_url,
                    "summary": r.summary,
                }
                for r in runs
            ],
        }
    )


def format_logs(result: AgentRunWithLogs) -> str:
    """Format agent run logs into a JSON string."""
    return json.dumps(
        {
            "run_id": result.id,
            "status": result.status,
            "total_logs": result.total_logs,
            "logs": [
                {
                    k: v
                    for k, v in {
                        "thought": log.thought,
                        "tool_name": log.tool_name,
                        "tool_input": log.tool_input,
                        "tool_output": (str(log.tool_output)[:500] if log.tool_output else None),
                        "created_at": log.created_at,
                    }.items()
                    if v is not None
                }
                for log in result.logs
            ],
        }
    )
