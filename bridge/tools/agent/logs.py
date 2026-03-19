"""Agent execution log retrieval tool.

Provides ``codegen_get_logs`` for fetching step-by-step agent execution
logs with cursor-based pagination and background task support.

Business logic lives in ``RunService``; this tool handles progress
reporting and JSON serialisation.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.annotations import READ_ONLY
from bridge.dependencies import CurrentContext, Depends, get_run_service
from bridge.helpers.pagination import DEFAULT_PAGE_SIZE
from bridge.icons import ICON_LOGS
from bridge.services.runs import RunService
from bridge.tools.agent._progress import GET_LOGS_STEPS, GET_LOGS_TASK, report


def register_log_tools(mcp: FastMCP) -> None:
    """Register agent log retrieval tools."""

    @mcp.tool(tags={"monitoring"}, icons=ICON_LOGS, task=GET_LOGS_TASK, annotations=READ_ONLY)
    async def codegen_get_logs(
        run_id: int,
        limit: int = DEFAULT_PAGE_SIZE,
        reverse: bool = True,
        cursor: str | None = None,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service),    ) -> str: # type: ignore[arg-type]
        """Get step-by-step agent execution logs with cursor-based pagination.

        Shows agent thoughts, tool calls, and outputs for debugging.
        Supports background execution with progress reporting.

        Args:
            run_id: Agent run ID.
            limit: Max log entries per page (default 20).
            reverse: If true, newest entries first.
            cursor: Opaque cursor from a previous response's ``next_cursor``
                field.  Omit or pass ``null`` for the first page.
        """
        total = GET_LOGS_STEPS
        step = 0

        # Step 1: Prepare request
        await report(ctx, step, total, "Preparing log request")
        await ctx.info(f"Fetching logs: run_id={run_id}, limit={limit}")
        step += 1

        # Step 2: Fetch from API via service
        await report(ctx, step, total, f"Fetching logs for run {run_id}")
        result = await svc.get_logs(run_id, limit=limit, reverse=reverse, cursor=cursor)
        await ctx.info(f"Fetched {len(result.get('logs', []))} log entries for run {run_id}")
        step += 1

        # Step 3: Format response
        await report(ctx, step, total, "Formatting log entries")
        response = json.dumps(result)

        await report(ctx, total, total, "Logs retrieved")
        return response
