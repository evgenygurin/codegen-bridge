"""Agent run management tools.

Create, get, list, resume, stop, ban, unban, remove-from-pr, logs, workflow.

Decomposed into focused submodules by responsibility:
- lifecycle: create, resume, stop (run lifecycle management)
- queries: get (pure read), list (pagination), report_run_result (explicit mutation)
- moderation: ban, unban, remove-from-pr (CI/CD check-suite management)
- logs: get_logs (execution log retrieval)
- workflow: create_and_monitor (high-level composition)

Endpoints coverage (per Codegen API v1):
- POST /v1/organizations/{org_id}/agent/run           — create
- GET  /v1/organizations/{org_id}/agent/run/{id}      — get
- GET  /v1/organizations/{org_id}/agent/runs           — list
- POST /v1/organizations/{org_id}/agent/run/resume     — resume
- POST /v1/organizations/{org_id}/agent/run/ban        — ban
- POST /v1/organizations/{org_id}/agent/run/unban      — unban
- POST /v1/organizations/{org_id}/agent/run/remove-from-pr — remove from PR
- GET  /v1/organizations/{org_id}/agent/run/{id}/logs  — logs
"""

from __future__ import annotations

from fastmcp import FastMCP

from bridge.tools.agent._progress import CREATE_RUN_STEPS as _CREATE_RUN_STEPS
from bridge.tools.agent._progress import CREATE_RUN_TASK, GET_LOGS_TASK
from bridge.tools.agent._progress import GET_LOGS_STEPS as _GET_LOGS_STEPS
from bridge.tools.agent._progress import report as _report
from bridge.tools.agent.lifecycle import register_lifecycle_tools
from bridge.tools.agent.logs import register_log_tools
from bridge.tools.agent.moderation import register_moderation_tools
from bridge.tools.agent.queries import register_query_tools
from bridge.tools.agent.workflow import register_workflow_tools

__all__ = [
    "CREATE_RUN_TASK",
    "GET_LOGS_TASK",
    "_CREATE_RUN_STEPS",
    "_GET_LOGS_STEPS",
    "_report",
    "register_agent_tools",
]


def register_agent_tools(mcp: FastMCP) -> None:
    """Register all agent run management tools on the given FastMCP server."""
    register_lifecycle_tools(mcp)
    register_query_tools(mcp)
    register_moderation_tools(mcp)
    register_log_tools(mcp)
    register_workflow_tools(mcp)
