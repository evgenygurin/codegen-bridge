"""Execution context models and registry with file-based persistence.

Tracks plan and ad-hoc executions, persists state to
.codegen-bridge/executions/ as JSON files, and supports
task status updates and report storage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

# ── Models ──────────────────────────────────────────────


class PRInfo(BaseModel):
    """Pull request information from a completed agent run."""

    url: str
    number: int | None = None
    title: str | None = None
    state: str | None = None


class TaskReport(BaseModel):
    """Report generated after a task completes."""

    summary: str = ""
    web_url: str | None = None
    pull_requests: list[PRInfo] = Field(default_factory=list)
    error: str | None = None


class TaskContext(BaseModel):
    """Single task within an execution plan."""

    title: str
    description: str = ""
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    run_id: int | None = None
    report: TaskReport | None = None


class ExecutionContext(BaseModel):
    """Full execution context for a plan or ad-hoc run."""

    id: str
    mode: Literal["plan", "adhoc"] = "adhoc"
    goal: str = ""
    status: Literal["active", "completed", "failed"] = "active"
    tasks: list[TaskContext] = Field(default_factory=list)


# ── Registry ────────────────────────────────────────────

_DEFAULT_STORAGE = Path(".codegen-bridge/executions")


class ContextRegistry:
    """Manages execution contexts with file-based persistence.

    Contexts are cached in memory and persisted to JSON files in the
    storage directory. On lookup, the registry checks cache first,
    then falls back to disk.
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._storage_dir = storage_dir or _DEFAULT_STORAGE
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, ExecutionContext] = {}

    def start_execution(
        self,
        *,
        execution_id: str,
        mode: Literal["plan", "adhoc"],
        goal: str,
        tasks: list[tuple[str, str]] | None = None,
        **kwargs: object,
    ) -> ExecutionContext:
        """Create and persist a new execution context.

        Args:
            execution_id: Unique identifier for the execution.
            mode: "plan" for multi-task plans, "adhoc" for single tasks.
            goal: High-level goal description.
            tasks: List of (title, description) tuples. For adhoc mode,
                   a single task is created from the goal if omitted.
        """
        if tasks:
            task_list = [
                TaskContext(title=title, description=desc)
                for title, desc in tasks
            ]
        elif mode == "adhoc":
            task_list = [TaskContext(title=goal)]
        else:
            task_list = []

        ctx = ExecutionContext(
            id=execution_id,
            mode=mode,
            goal=goal,
            tasks=task_list,
        )
        self._cache[execution_id] = ctx
        self._save(ctx)
        return ctx

    def get(self, execution_id: str) -> ExecutionContext | None:
        """Get execution context by ID (cache, then disk).

        Returns None if not found anywhere.
        """
        if execution_id in self._cache:
            return self._cache[execution_id]
        return self._load(execution_id)

    def get_active(self) -> ExecutionContext | None:
        """Find the first active execution (cache first, then disk).

        Returns None when no active execution exists.
        """
        # Check cache first
        for ctx in self._cache.values():
            if ctx.status == "active":
                return ctx

        # Scan disk
        for path in self._storage_dir.glob("*.json"):
            eid = path.stem
            if eid in self._cache:
                continue  # Already checked
            ctx = self._load(eid)
            if ctx is not None and ctx.status == "active":
                return ctx

        return None

    def update_task(
        self,
        *,
        execution_id: str,
        task_index: int,
        status: str | None = None,
        run_id: int | None = None,
        report: TaskReport | None = None,
    ) -> None:
        """Update a task within an execution context.

        Args:
            execution_id: ID of the execution to update.
            task_index: Index of the task in the tasks list.
            status: New task status (pending, running, completed, failed).
            run_id: Agent run ID associated with this task.
            report: Task completion report.
        """
        ctx = self.get(execution_id)
        if ctx is None:
            msg = f"Execution {execution_id!r} not found"
            raise KeyError(msg)

        task = ctx.tasks[task_index]
        if status is not None:
            task.status = status  # type: ignore[assignment]
        if run_id is not None:
            task.run_id = run_id
        if report is not None:
            task.report = report

        self._save(ctx)

    def _save(self, ctx: ExecutionContext) -> None:
        """Persist execution context to JSON file."""
        self._cache[ctx.id] = ctx
        path = self._storage_dir / f"{ctx.id}.json"
        path.write_text(ctx.model_dump_json(indent=2))

    def _load(self, execution_id: str) -> ExecutionContext | None:
        """Load execution context from disk and cache it."""
        path = self._storage_dir / f"{execution_id}.json"
        if not path.exists():
            return None

        data = json.loads(path.read_text())
        ctx = ExecutionContext.model_validate(data)
        self._cache[execution_id] = ctx
        return ctx
