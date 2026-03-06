"""Background task manager for run monitoring.

Tracks active and completed run monitors. Each ``MonitorRecord`` represents
a single monitoring session — one ``codegen_monitor_run`` invocation that
polls the Codegen API at intervals and reports progress.

The manager is instantiated once in the server lifespan and injected into
tools via ``Depends(get_task_manager)``.  It is purely in-memory (monitors
are transient — they exist only for the duration of the server process).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


# ── Terminal states ──────────────────────────────────────────────

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"completed", "failed", "cancelled", "timed_out", "error", "stopped"}
)

# ── Defaults ─────────────────────────────────────────────────────

DEFAULT_POLL_INTERVAL: int = 5  # seconds
DEFAULT_MAX_DURATION: int = 300  # seconds (5 minutes)
MAX_POLL_INTERVAL: int = 30  # seconds
MAX_DURATION_LIMIT: int = 600  # seconds (10 minutes hard cap)
MIN_POLL_INTERVAL: int = 2  # seconds
MIN_DURATION: int = 10  # seconds


# ── Monitor record ───────────────────────────────────────────────


@dataclass
class MonitorRecord:
    """State of a single run monitoring session."""

    monitor_id: str
    run_id: int
    started_at: str
    last_polled_at: str | None = None
    last_status: str | None = None
    poll_count: int = 0
    terminal: bool = False
    final_result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict."""
        return {
            "monitor_id": self.monitor_id,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "last_polled_at": self.last_polled_at,
            "last_status": self.last_status,
            "poll_count": self.poll_count,
            "active": not self.terminal,
            "error": self.error,
        }


# ── Background task manager ─────────────────────────────────────


class BackgroundTaskManager:
    """In-memory tracker for run monitoring sessions.

    This class does **not** drive the polling — the ``codegen_monitor_run``
    tool does.  The manager simply *records* state so that other tools
    (``codegen_list_monitors``) can inspect what is happening.

    Thread-safety note: MCP tools run as concurrent ``asyncio`` tasks in
    the same event loop.  Because Python's GIL and asyncio's cooperative
    scheduling guarantee that dict mutations within a single coroutine
    step are atomic, no explicit locking is needed.
    """

    def __init__(self) -> None:
        self._monitors: dict[str, MonitorRecord] = {}

    # ── Lifecycle ────────────────────────────────────────────

    def create_monitor(self, run_id: int) -> MonitorRecord:
        """Start tracking a new monitoring session."""
        monitor_id = uuid.uuid4().hex[:12]
        record = MonitorRecord(
            monitor_id=monitor_id,
            run_id=run_id,
            started_at=datetime.now(UTC).isoformat(),
        )
        self._monitors[monitor_id] = record
        return record

    def update_monitor(
        self,
        monitor_id: str,
        *,
        status: str,
        terminal: bool = False,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Record the latest poll result for a monitor."""
        record = self._monitors.get(monitor_id)
        if record is None:
            return
        record.last_polled_at = datetime.now(UTC).isoformat()
        record.last_status = status
        record.poll_count += 1
        record.terminal = terminal
        if result is not None:
            record.final_result = result

    def fail_monitor(self, monitor_id: str, error: str) -> None:
        """Mark a monitor as failed due to an unexpected error."""
        record = self._monitors.get(monitor_id)
        if record is None:
            return
        record.terminal = True
        record.error = error

    # ── Queries ──────────────────────────────────────────────

    def get_monitor(self, monitor_id: str) -> MonitorRecord | None:
        """Retrieve a single monitor by ID."""
        return self._monitors.get(monitor_id)

    def list_monitors(self, *, active_only: bool = False) -> list[MonitorRecord]:
        """List all monitors, optionally filtering to active-only."""
        records = list(self._monitors.values())
        if active_only:
            records = [r for r in records if not r.terminal]
        return records

    def get_monitors_for_run(self, run_id: int) -> list[MonitorRecord]:
        """List all monitors (active + completed) for a specific run."""
        return [r for r in self._monitors.values() if r.run_id == run_id]

    # ── Cleanup ──────────────────────────────────────────────

    def clear_completed(self) -> int:
        """Remove all terminal monitors.  Returns the count removed."""
        to_remove = [mid for mid, r in self._monitors.items() if r.terminal]
        for mid in to_remove:
            del self._monitors[mid]
        return len(to_remove)
