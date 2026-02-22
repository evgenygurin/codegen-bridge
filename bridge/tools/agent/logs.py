"""Agent execution log retrieval tool.

Provides ``codegen_get_logs`` for fetching step-by-step agent execution
logs with cursor-based pagination and background task support.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.helpers.pagination import DEFAULT_PAGE_SIZE, cursor_to_offset, next_cursor_or_none
from bridge.icons import ICON_LOGS
from bridge.tools.agent._progress import GET_LOGS_STEPS, GET_LOGS_TASK, report


def register_log_tools(mcp: FastMCP) -> None:
    """Register agent log retrieval tools."""

    @mcp.tool(tags={"monitoring"}, icons=ICON_LOGS, task=GET_LOGS_TASK)
    async def codegen_get_logs(
        run_id: int,
        limit: int = DEFAULT_PAGE_SIZE,
        reverse: bool = True,
        cursor: str | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
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

        # Step 1: Parse pagination
        await report(ctx, step, total, "Preparing log request")
        offset = cursor_to_offset(cursor)
        await ctx.info(f"Fetching logs: run_id={run_id}, limit={limit}, offset={offset}")
        step += 1

        # Step 2: Fetch from API
        await report(ctx, step, total, f"Fetching logs for run {run_id}")
        result = await client.get_logs(run_id, skip=offset, limit=limit, reverse=reverse)
        await ctx.info(f"Fetched {len(result.logs)} log entries for run {run_id}")
        step += 1

        # Step 3: Format response
        await report(ctx, step, total, "Formatting log entries")
        response = json.dumps(
            {
                "run_id": result.id,
                "status": result.status,
                "total_logs": result.total_logs,
                "next_cursor": next_cursor_or_none(offset, limit, result.total_logs or 0),
                "logs": [
                    {
                        k: v
                        for k, v in {
                            "thought": log.thought,
                            "tool_name": log.tool_name,
                            "tool_input": log.tool_input,
                            "tool_output": (
                                str(log.tool_output)[:500] if log.tool_output else None
                            ),
                            "message_type": log.message_type,
                            "created_at": log.created_at,
                        }.items()
                        if v is not None
                    }
                    for log in result.logs
                ],
            }
        )

        await report(ctx, total, total, "Logs retrieved")
        return response
