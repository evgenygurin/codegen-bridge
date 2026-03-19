"""Agent run analytics tools.

Aggregates statistics from recent runs: totals, success rate, and
status distribution.
"""

from __future__ import annotations

import json
from collections import Counter

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.annotations import READ_ONLY
from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client, get_org_id
from bridge.icons import ICON_DASHBOARD


def register_analytics_tools(mcp: FastMCP) -> None:
    """Register analytics tools on the given FastMCP server."""

    @mcp.tool(tags={"analytics"}, icons=ICON_DASHBOARD, timeout=30, annotations=READ_ONLY)
    async def codegen_get_run_analytics(
        limit: int = 100,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
        org_id: int = Depends(get_org_id),  # type: ignore[arg-type]
    ) -> str:
        """Aggregate stats: total runs, success rate, status distribution.

        Fetches the most recent runs and computes summary statistics
        including total count, success/failure rates, and a breakdown
        by status.

        Args:
            limit: Maximum number of recent runs to analyse (default 100).
        """
        await ctx.info(f"Fetching up to {limit} runs for analytics (org_id={org_id})")
        page = await client.list_runs(limit=limit)
        runs = page.items

        total = len(runs)
        if total == 0:
            return json.dumps({
                "organization_id": org_id,
                "total_runs": 0,
                "success_rate": 0.0,
                "status_distribution": {},
            })

        status_counts: Counter[str] = Counter()
        for run in runs:
            status_counts[run.status or "unknown"] += 1

        completed = status_counts.get("completed", 0)
        failed = status_counts.get("failed", 0)
        terminal = completed + failed
        success_rate = round(completed / terminal, 4) if terminal > 0 else 0.0

        await ctx.info(
            f"Analytics: {total} runs, {completed} completed, "
            f"{failed} failed, success_rate={success_rate}"
        )

        return json.dumps({
            "organization_id": org_id,
            "total_runs": total,
            "completed": completed,
            "failed": failed,
            "success_rate": success_rate,
            "status_distribution": dict(status_counts),
        })
