"""Background run monitoring tool.

Provides ``codegen_monitor_run_background`` — a standalone tool that
monitors an *existing* agent run by polling its status in a background
task.  Unlike ``codegen_create_and_monitor``, this tool does **not**
create a run; it only observes one that is already running.

Uses FastMCP's native ``task=True`` via ``TaskConfig`` and
``ctx.report_progress()`` for live progress updates.
"""

from __future__ import annotations

import asyncio
import json

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.annotations import READ_ONLY
from bridge.dependencies import CurrentContext, Depends, get_run_service
from bridge.icons import ICON_MONITOR
from bridge.services.runs import RunService
from bridge.tools.agent._progress import MONITOR_TASK, report

# Terminal statuses that end the polling loop
_TERMINAL = frozenset({"completed", "failed", "error"})


def register_background_tools(mcp: FastMCP) -> None:
    """Register background monitoring tools on the given FastMCP server."""

    @mcp.tool(
        tags={"agent", "monitoring"},
        icons=ICON_MONITOR,
        task=MONITOR_TASK,
        annotations=READ_ONLY,
    )
    async def codegen_monitor_run_background(
        run_id: int,
        poll_interval: float = 10.0,
        max_polls: int = 60,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service),  # type: ignore[arg-type]
    ) -> str:
        """Monitor an existing agent run in the background with live progress.

        Polls the run status at regular intervals, reporting progress
        via MCP progress notifications.  Runs as a background task
        (``task=True``) so the client can continue working while the
        monitor tracks completion.

        Use this when you have already created a run (or received a
        ``run_id`` from another tool) and want non-blocking status
        tracking.

        Args:
            run_id: ID of the agent run to monitor.
            poll_interval: Base seconds between polls (with exponential backoff).
            max_polls: Maximum number of status polls before timeout.
        """
        # ── Initial fetch ────────────────────────────────────
        await report(ctx, 0, max_polls, f"Fetching initial status for run {run_id}")

        data = await svc.get_run(run_id)
        status = data.get("status", "unknown")

        # Already terminal — return immediately
        if status in _TERMINAL:
            data["polls"] = 0
            return json.dumps(data)

        # ── Poll loop ────────────────────────────────────────
        for i in range(max_polls):
            # Exponential backoff: doubles every 10 polls, capped at 4x
            delay = poll_interval * min(2 ** (i // 10), 4)
            await asyncio.sleep(delay)

            data = await svc.get_run(run_id)
            status = data.get("status", "unknown")

            await report(
                ctx,
                i + 1,
                max_polls,
                f"Poll {i + 1}/{max_polls}: run {run_id} — {status}",
            )

            if status in _TERMINAL:
                data["polls"] = i + 1
                return json.dumps(data)

        # ── Timeout ──────────────────────────────────────────
        return json.dumps({
            "timeout": True,
            "run_id": run_id,
            "last_status": data.get("status", "unknown"),
            "polls": max_polls,
        })
