"""Agent run query and reporting tools.

- ``codegen_get_run``: Pure read — fetch run status, PRs, summary.
- ``codegen_list_runs``: Pure read — paginated list of runs.
- ``codegen_report_run_result``: Explicit mutation — write TaskReport
  to ContextRegistry and advance execution task index.

Business logic lives in ``RunService``; these tools handle MCP
concerns (logging, JSON serialisation).
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.annotations import MUTATES, READ_ONLY
from bridge.dependencies import CurrentContext, Depends, get_run_service
from bridge.helpers.pagination import DEFAULT_PAGE_SIZE
from bridge.icons import ICON_GET_RUN, ICON_LIST
from bridge.services.runs import RunService


def register_query_tools(mcp: FastMCP) -> None:
    """Register agent run query and reporting tools."""

    # ── Get (pure read) ────────────────────────────────────

    @mcp.tool(tags={"execution"}, icons=ICON_GET_RUN, timeout=30, annotations=READ_ONLY)
    async def codegen_get_run(
        run_id: int,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service),    ) -> str: # type: ignore[arg-type]
        """Get agent run status, result, summary, and created PRs.

        Pure read — safe to poll repeatedly without side effects.
        Use ``codegen_report_run_result`` to record results to an execution context.

        Args:
            run_id: Agent run ID.
        """
        await ctx.info(f"Fetching run: id={run_id}")
        result = await svc.get_run(run_id)
        return json.dumps(result)

    # ── Report Run Result (explicit mutation) ──────────────

    @mcp.tool(tags={"execution"}, icons=ICON_GET_RUN, timeout=30, annotations=MUTATES)
    async def codegen_report_run_result(
        run_id: int,
        execution_id: str,
        task_index: int | None = None,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service),    ) -> str: # type: ignore[arg-type]
        """Report a completed/failed agent run back to an execution context.

        Fetches the run, parses its logs, writes a TaskReport to the
        execution context, and advances the current task index on success.

        Only operates on terminal statuses (completed, failed).
        Non-terminal runs return the run data without mutation.

        Args:
            run_id: Agent run ID.
            execution_id: Execution context ID to report to.
            task_index: Task index within the execution (default: current_task_index).
        """
        await ctx.info(f"Reporting run result: run_id={run_id}, execution_id={execution_id}")
        result = await svc.report_run_result(run_id, execution_id, task_index)
        return json.dumps(result)

    # ── List ───────────────────────────────────────────────

    @mcp.tool(tags={"execution"}, icons=ICON_LIST, timeout=30, annotations=READ_ONLY)
    async def codegen_list_runs(
        limit: int = DEFAULT_PAGE_SIZE,
        source_type: str | None = None,
        user_id: int | None = None,
        cursor: str | None = None,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service),    ) -> str: # type: ignore[arg-type]
        """List recent agent runs with cursor-based pagination.

        Args:
            limit: Maximum number of runs per page (default 20).
            source_type: Filter by source — API, LOCAL, GITHUB, etc.
            user_id: Filter by user ID who initiated the agent runs.
            cursor: Opaque cursor from a previous response's ``next_cursor``
                field.  Omit or pass ``null`` for the first page.
        """
        await ctx.info(
            f"Listing runs: limit={limit}, source_type={source_type}"
        )
        result = await svc.list_runs(
            limit=limit, cursor=cursor, source_type=source_type, user_id=user_id
        )
        await ctx.info(f"Listed {len(result.get('runs', []))} runs")
        return json.dumps(result)
