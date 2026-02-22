"""Agent run query tools: get, list.

Read-only tools for fetching agent run status and listing runs
with cursor-based pagination. ``codegen_get_run`` also supports
auto-reporting back to execution contexts on terminal status.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.client import CodegenClient
from bridge.context import ContextRegistry, PRInfo, TaskReport
from bridge.dependencies import CurrentContext, Depends, get_client, get_registry
from bridge.helpers.pagination import (
    DEFAULT_PAGE_SIZE,
    build_paginated_response,
    cursor_to_offset,
)
from bridge.icons import ICON_GET_RUN, ICON_LIST
from bridge.log_parser import parse_logs


def register_query_tools(mcp: FastMCP) -> None:
    """Register agent run query tools (get, list)."""

    # ── Get ───────────────────────────────────────────────

    @mcp.tool(tags={"execution"}, icons=ICON_GET_RUN)
    async def codegen_get_run(
        run_id: int,
        execution_id: str | None = None,
        task_index: int | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
        registry: ContextRegistry = Depends(get_registry),  # type: ignore[arg-type]
    ) -> str:
        """Get agent run status, result, summary, and created PRs.

        Use this to poll for completion (check status field).

        Args:
            run_id: Agent run ID.
            execution_id: Optional execution context ID for auto-reporting.
            task_index: Task index within the execution (default: current_task_index).
        """
        await ctx.info(f"Fetching run: id={run_id}")
        run = await client.get_run(run_id)

        result: dict[str, Any] = {
            "id": run.id,
            "status": run.status,
            "web_url": run.web_url,
        }
        if run.result:
            result["result"] = run.result
        if run.summary:
            result["summary"] = run.summary
        if run.source_type:
            result["source_type"] = run.source_type

        pr_list: list[dict[str, Any]] = []
        if run.github_pull_requests:
            pr_list = [
                {
                    k: v
                    for k, v in {
                        "url": pr.url,
                        "title": pr.title,
                        "head_branch_name": pr.head_branch_name,
                        "number": pr.number,
                        "state": pr.state,
                    }.items()
                    if v is not None
                }
                for pr in run.github_pull_requests
            ]
            result["pull_requests"] = pr_list

        # Auto-report back to execution context on terminal status
        if execution_id is not None and run.status in ("completed", "failed"):
            exec_ctx = await registry.get(execution_id)
            if exec_ctx is not None:
                idx = task_index if task_index is not None else exec_ctx.current_task_index
                if idx < len(exec_ctx.tasks):
                    # Parse logs for structured data
                    parsed = None
                    try:
                        logs_result = await client.get_logs(run_id, limit=100)
                        parsed = parse_logs(logs_result.logs)
                        result["parsed_logs"] = {
                            "files_changed": parsed.files_changed,
                            "key_decisions": parsed.key_decisions,
                            "test_results": parsed.test_results,
                            "commands_run": parsed.commands_run,
                            "total_steps": parsed.total_steps,
                        }
                    except Exception as exc:
                        await ctx.warning(f"Log parsing failed for run {run_id}: {exc}")

                    # Build TaskReport
                    report = TaskReport(
                        summary=run.summary or run.result or "",
                        web_url=run.web_url or "",
                        pull_requests=[
                            PRInfo(
                                url=pr.get("url", ""),
                                number=pr.get("number", 0),
                                title=pr.get("title", ""),
                                state=pr.get("state", ""),
                            )
                            for pr in pr_list
                        ],
                        files_changed=parsed.files_changed if parsed else [],
                        key_decisions=parsed.key_decisions if parsed else [],
                        test_results=parsed.test_results if parsed else None,
                        agent_notes=parsed.agent_notes if parsed else None,
                        commands_run=parsed.commands_run if parsed else [],
                        total_steps=parsed.total_steps if parsed else 0,
                    )

                    task_status: Literal["completed", "failed"] = (
                        "completed" if run.status == "completed" else "failed"
                    )
                    await registry.update_task(
                        execution_id=execution_id,
                        task_index=idx,
                        status=task_status,
                        report=report,
                    )

                    # Advance current_task_index if completed
                    if run.status == "completed":
                        exec_ctx.current_task_index = idx + 1
                        await registry._save(exec_ctx)

        return json.dumps(result)

    # ── List ──────────────────────────────────────────────

    @mcp.tool(tags={"execution"}, icons=ICON_LIST)
    async def codegen_list_runs(
        limit: int = DEFAULT_PAGE_SIZE,
        source_type: str | None = None,
        user_id: int | None = None,
        cursor: str | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """List recent agent runs with cursor-based pagination.

        Args:
            limit: Maximum number of runs per page (default 20).
            source_type: Filter by source — API, LOCAL, GITHUB, etc.
            user_id: Filter by user ID who initiated the agent runs.
            cursor: Opaque cursor from a previous response's ``next_cursor``
                field.  Omit or pass ``null`` for the first page.
        """
        offset = cursor_to_offset(cursor)
        await ctx.info(
            f"Listing runs: limit={limit}, offset={offset}, source_type={source_type}"
        )
        page = await client.list_runs(
            skip=offset, limit=limit, source_type=source_type, user_id=user_id
        )
        await ctx.info(f"Listed {len(page.items)} of {page.total} runs")
        return json.dumps(
            build_paginated_response(
                items=[
                    {
                        "id": r.id,
                        "status": r.status,
                        "created_at": r.created_at,
                        "web_url": r.web_url,
                        "summary": r.summary,
                        "source_type": r.source_type,
                    }
                    for r in page.items
                ],
                total=page.total,
                offset=offset,
                page_size=limit,
                items_key="runs",
            )
        )
