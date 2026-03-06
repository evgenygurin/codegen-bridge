"""Shared progress-reporting helpers for agent tools.

Contains ``TaskConfig`` instances for long-running operations and
a best-effort progress reporter that never raises.
"""

from __future__ import annotations

from contextlib import suppress as _suppress
from datetime import timedelta

from fastmcp.server.context import Context
from fastmcp.server.tasks import TaskConfig

# ── Task configurations for long-running operations ──────

CREATE_RUN_TASK = TaskConfig(
    mode="optional",
    poll_interval=timedelta(seconds=5),
)
"""Create-run is multi-step (validate -> enrich -> detect repo -> API call -> track)."""

GET_LOGS_TASK = TaskConfig(
    mode="optional",
    poll_interval=timedelta(seconds=3),
)
"""Get-logs does a single API fetch + formatting — faster poll."""

MONITOR_RUN_TASK = TaskConfig(
    mode="optional",
    poll_interval=timedelta(seconds=5),
)
"""Monitor-run is a long-polling loop — reports progress at each poll interval."""

# Total progress steps for each operation
CREATE_RUN_STEPS = 5
GET_LOGS_STEPS = 3


async def report(ctx: Context, progress: float, total: float, message: str) -> None:
    """Best-effort progress report — never raises."""
    with _suppress(Exception):
        await ctx.report_progress(progress=progress, total=total, message=message)
