"""Parameterized resource templates for live entity data.

These MCP resource templates provide cacheable, read-only access to
frequently polled entities (runs, logs, execution contexts) via
parameterized URIs.  Each resource delegates to the service layer —
the same code path as the corresponding tool — so data format is
always consistent.

Resource URIs:
- ``codegen://runs/{run_id}``          → run status, result, PRs
- ``codegen://runs/{run_id}/logs``     → step-by-step execution logs
- ``codegen://execution/{execution_id}`` → execution context state
"""

from __future__ import annotations

import json

from fastmcp import FastMCP

from bridge.dependencies import Depends, get_execution_service, get_run_service
from bridge.icons import ICON_CONTEXT, ICON_GET_RUN, ICON_LOGS
from bridge.services.execution import ExecutionService
from bridge.services.runs import RunService


def register_resource_templates(mcp: FastMCP) -> None:
    """Register parameterized resource templates on the given FastMCP server."""

    @mcp.resource("codegen://runs/{run_id}", icons=ICON_GET_RUN)
    async def get_run_resource(
        run_id: str,
        svc: RunService = Depends(get_run_service),
    ) -> str:
        """Agent run status, result, summary, and created PRs.

        Returns the same data as ``codegen_get_run`` tool but as a
        cacheable MCP resource.  Useful for monitoring dashboards
        and repeated polling without tool-call overhead.
        """
        data = await svc.get_run(int(run_id))
        return json.dumps(data)

    @mcp.resource("codegen://runs/{run_id}/logs", icons=ICON_LOGS)
    async def get_run_logs_resource(
        run_id: str,
        svc: RunService = Depends(get_run_service),
    ) -> str:
        """Step-by-step agent execution logs for debugging.

        Returns the most recent 20 log entries (reverse chronological)
        — the same data as ``codegen_get_logs`` with default parameters.
        """
        data = await svc.get_logs(int(run_id))
        return json.dumps(data)

    @mcp.resource("codegen://execution/{execution_id}", icons=ICON_CONTEXT)
    async def get_execution_resource(
        execution_id: str,
        svc: ExecutionService = Depends(get_execution_service),
    ) -> str:
        """Execution context state — tasks, progress, metadata.

        Returns the full execution context for orchestration
        monitoring.  When no context with the given ID exists,
        returns ``{"status": "not_found"}``.
        """
        ctx = await svc.get_execution_context(execution_id)
        if ctx is None:
            return json.dumps({"status": "not_found", "execution_id": execution_id})
        return ctx.model_dump_json(indent=2)
