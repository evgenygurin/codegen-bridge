"""Run monitoring tools with background task support and progress reporting.

Provides ``codegen_monitor_run`` — a long-running polling tool that watches
an agent run until it reaches a terminal state, reporting progress at each
poll interval via ``ctx.report_progress()``.

Also provides ``codegen_list_monitors`` for inspecting active and completed
monitoring sessions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.client import CodegenClient
from bridge.context import ContextRegistry, PRInfo, TaskReport
from bridge.dependencies import (
    CurrentContext,
    Depends,
    get_client,
    get_registry,
    get_task_manager,
)
from bridge.helpers.formatting import format_run
from bridge.icons import ICON_LIST_MONITORS, ICON_MONITOR_RUN
from bridge.log_parser import parse_logs
from bridge.monitoring import (
    DEFAULT_MAX_DURATION,
    DEFAULT_POLL_INTERVAL,
    MAX_DURATION_LIMIT,
    MAX_POLL_INTERVAL,
    MIN_DURATION,
    MIN_POLL_INTERVAL,
    TERMINAL_STATUSES,
    BackgroundTaskManager,
)
from bridge.tools.agent._progress import MONITOR_RUN_TASK, report

logger = logging.getLogger("bridge.tools.agent.monitor")


def register_monitor_tools(mcp: FastMCP) -> None:
    """Register run monitoring tools (monitor_run, list_monitors)."""

    # ── Monitor ──────────────────────────────────────────

    @mcp.tool(tags={"monitoring"}, icons=ICON_MONITOR_RUN, task=MONITOR_RUN_TASK)
    async def codegen_monitor_run(
        run_id: int,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        max_duration: int = DEFAULT_MAX_DURATION,
        execution_id: str | None = None,
        task_index: int | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
        registry: ContextRegistry = Depends(get_registry),  # type: ignore[arg-type]
        task_manager: BackgroundTaskManager = Depends(get_task_manager),  # type: ignore[arg-type]
    ) -> str:
        """Monitor an agent run until completion with real-time progress reporting.

        Polls the Codegen API at regular intervals, reporting status via MCP
        progress notifications. Returns the final result when the run reaches
        a terminal state (completed, failed, etc.) or the monitoring times out.

        Supports background execution with progress reporting via FastMCP tasks.

        Args:
            run_id: Agent run ID to monitor.
            poll_interval: Seconds between status polls (2-30, default 5).
            max_duration: Maximum monitoring duration in seconds (10-600, default 300).
            execution_id: Optional execution context ID for auto-reporting on completion.
            task_index: Task index within the execution (default: current_task_index).
        """
        # Clamp inputs to safe ranges
        poll_interval = max(MIN_POLL_INTERVAL, min(poll_interval, MAX_POLL_INTERVAL))
        max_duration = max(MIN_DURATION, min(max_duration, MAX_DURATION_LIMIT))
        total_polls = max_duration // poll_interval

        await ctx.info(
            f"Monitoring run {run_id}: poll_interval={poll_interval}s, "
            f"max_duration={max_duration}s"
        )

        # Create tracking record
        record = task_manager.create_monitor(run_id)
        await report(ctx, 0, total_polls, f"Starting monitor for run {run_id}")

        start = time.monotonic()
        step = 0

        try:
            while (time.monotonic() - start) < max_duration:
                # Fetch current run status
                run = await client.get_run(run_id)
                status = run.status or "unknown"
                is_terminal = status in TERMINAL_STATUSES

                # Update tracking record
                task_manager.update_monitor(
                    record.monitor_id,
                    status=status,
                    terminal=is_terminal,
                    result=format_run(run) if is_terminal else None,
                )

                step += 1
                elapsed = int(time.monotonic() - start)

                # Report progress
                message = (
                    f"Run {run_id}: {status} "
                    f"(poll {step}/{total_polls}, {elapsed}s elapsed)"
                )
                await report(ctx, step, total_polls, message)

                if is_terminal:
                    await ctx.info(f"Run {run_id} reached terminal state: {status}")

                    # Build result
                    result = _build_terminal_result(
                        record.monitor_id, run_id, status, step, elapsed, run
                    )

                    # Auto-report to execution context if applicable
                    if execution_id is not None:
                        await _report_to_execution(
                            client=client,
                            registry=registry,
                            ctx=ctx,
                            execution_id=execution_id,
                            task_index=task_index,
                            run=run,
                            result=result,
                        )

                    await report(ctx, total_polls, total_polls, f"Run {run_id}: {status}")
                    return json.dumps(result)

                # Wait before next poll
                await asyncio.sleep(poll_interval)

            # Monitoring timed out — run may still be active
            elapsed = int(time.monotonic() - start)
            last_api_status = record.last_status
            task_manager.update_monitor(
                record.monitor_id,
                status="monitor_timeout",
                terminal=True,
            )
            await ctx.warning(
                f"Monitoring timed out for run {run_id} after {elapsed}s"
            )

            return json.dumps({
                "monitor_id": record.monitor_id,
                "run_id": run_id,
                "outcome": "monitor_timeout",
                "last_known_status": last_api_status,
                "poll_count": step,
                "elapsed_seconds": elapsed,
                "message": (
                    f"Monitoring timed out after {max_duration}s. "
                    f"Run may still be in progress. "
                    f"Use codegen_get_run to check current status."
                ),
            })

        except Exception as exc:
            task_manager.fail_monitor(record.monitor_id, str(exc))
            await ctx.error(f"Monitor failed for run {run_id}: {exc}")
            raise

    # ── List Monitors ────────────────────────────────────

    @mcp.tool(tags={"monitoring"}, icons=ICON_LIST_MONITORS)
    async def codegen_list_monitors(
        active_only: bool = False,
        run_id: int | None = None,
        ctx: Context = CurrentContext(),
        task_manager: BackgroundTaskManager = Depends(get_task_manager),  # type: ignore[arg-type]
    ) -> str:
        """List active and completed run monitors.

        Returns information about all monitoring sessions in the current
        server process — useful for checking what runs are being watched.

        Args:
            active_only: If True, only return monitors that are still polling.
            run_id: If provided, only return monitors for this specific run.
        """
        if run_id is not None:
            records = task_manager.get_monitors_for_run(run_id)
        else:
            records = task_manager.list_monitors(active_only=active_only)

        await ctx.info(f"Found {len(records)} monitor(s)")
        return json.dumps({
            "total": len(records),
            "monitors": [r.to_dict() for r in records],
        })


# ── Internal helpers ─────────────────────────────────────────


def _build_terminal_result(
    monitor_id: str,
    run_id: int,
    status: str,
    poll_count: int,
    elapsed_seconds: int,
    run: Any,
) -> dict[str, Any]:
    """Build the JSON result for a run that reached a terminal state."""
    result: dict[str, Any] = {
        "monitor_id": monitor_id,
        "run_id": run_id,
        "outcome": status,
        "poll_count": poll_count,
        "elapsed_seconds": elapsed_seconds,
        **format_run(run),
    }

    # Include PR info if available
    if run.github_pull_requests:
        result["pull_requests"] = [
            {
                k: v
                for k, v in {
                    "url": pr.url,
                    "title": pr.title,
                    "number": pr.number,
                    "state": pr.state,
                    "head_branch_name": pr.head_branch_name,
                }.items()
                if v is not None
            }
            for pr in run.github_pull_requests
        ]

    return result


async def _report_to_execution(
    *,
    client: CodegenClient,
    registry: ContextRegistry,
    ctx: Context,
    execution_id: str,
    task_index: int | None,
    run: Any,
    result: dict[str, Any],
) -> None:
    """Report run completion back to an execution context (best-effort)."""
    try:
        exec_ctx = await registry.get(execution_id)
        if exec_ctx is None:
            return
        idx = task_index if task_index is not None else exec_ctx.current_task_index
        if idx >= len(exec_ctx.tasks):
            return

        # Parse logs for structured data
        parsed = None
        try:
            logs_result = await client.get_logs(run.id, limit=100)
            parsed = parse_logs(logs_result.logs)
        except Exception as exc:
            await ctx.warning(f"Log parsing failed for run {run.id}: {exc}")

        # Build PR info from result
        pr_list = result.get("pull_requests", [])
        pr_infos = [
            PRInfo(
                url=pr.get("url", ""),
                number=pr.get("number", 0),
                title=pr.get("title", ""),
                state=pr.get("state", ""),
            )
            for pr in pr_list
        ]

        # Build task report
        task_report = TaskReport(
            summary=run.summary or run.result or "",
            web_url=run.web_url or "",
            pull_requests=pr_infos,
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
            report=task_report,
        )

        # Advance current_task_index if completed
        if run.status == "completed":
            exec_ctx = await registry.get(execution_id)
            if exec_ctx is not None:
                exec_ctx.current_task_index = idx + 1
                await registry._save(exec_ctx)

        await ctx.info(
            f"Execution context {execution_id} updated: "
            f"task {idx} → {task_status}"
        )
    except Exception as exc:
        await ctx.warning(f"Failed to update execution context: {exc}")
