"""Execution context models and registry for structured agent communication."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class PRInfo(BaseModel):
    """Pull request created by an agent."""

    url: str
    number: int
    title: str
    state: str
    branch: str | None = None


class TaskReport(BaseModel):
    """Structured result from a completed agent task."""

    summary: str
    web_url: str

    # PRs
    pull_requests: list[PRInfo] = []

    # Parsed from logs
    files_changed: list[str] = []
    key_decisions: list[str] = []
    test_results: str | None = None
    agent_notes: str | None = None
    commands_run: list[str] = []

    # Integrations
    linear_issue: str | None = None
    slack_thread: str | None = None

    # Meta
    total_steps: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None


class TaskContext(BaseModel):
    """Single task within an execution."""

    index: int
    title: str
    description: str

    status: Literal["pending", "running", "completed", "failed", "skipped"] = "pending"
    run_id: int | None = None
    report: TaskReport | None = None


class ExecutionContext(BaseModel):
    """Full execution context — plan or ad-hoc."""

    id: str
    mode: Literal["plan", "adhoc"]
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    # Plan metadata
    goal: str
    architecture: str | None = None
    tech_stack: list[str] = []
    repo_structure: str | None = None

    # Codegen context
    repo_id: int | None = None
    repo_full_name: str | None = None
    agent_rules: str | None = None
    integrations: dict[str, bool] = {}
    available_models: list[str] = []

    # Tasks
    tasks: list[TaskContext] = []
    current_task_index: int = 0

    # State
    status: Literal["active", "completed", "failed", "paused"] = "active"


class ContextRegistry:
    """Manages execution contexts with file-based persistence."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        if storage_dir is None:
            storage_dir = Path(".codegen-bridge") / "executions"
        self._storage_dir = storage_dir
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
        """Create and persist a new execution context."""
        task_list: list[TaskContext] = []
        if tasks:
            for i, (title, desc) in enumerate(tasks):
                task_list.append(TaskContext(index=i, title=title, description=desc))
        elif mode == "adhoc":
            task_list.append(TaskContext(index=0, title=goal, description=goal))

        ctx = ExecutionContext(
            id=execution_id,
            mode=mode,
            goal=goal,
            tasks=task_list,
            status="active",
            **kwargs,
        )
        self._cache[execution_id] = ctx
        self._save(ctx)
        return ctx

    def get(self, execution_id: str) -> ExecutionContext | None:
        """Retrieve an execution context by ID (cache first, then disk)."""
        if execution_id in self._cache:
            return self._cache[execution_id]
        return self._load(execution_id)

    def get_active(self) -> ExecutionContext | None:
        """Find the first active execution context (cache then disk scan)."""
        for ctx in self._cache.values():
            if ctx.status == "active":
                return ctx
        for f in self._storage_dir.glob("*.json"):
            ctx = self._load(f.stem)
            if ctx and ctx.status == "active":
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
        """Update a task's status, run_id, or report within an execution."""
        ctx = self.get(execution_id)
        if ctx is None or task_index >= len(ctx.tasks):
            return
        task = ctx.tasks[task_index]
        if status is not None:
            task.status = status
        if run_id is not None:
            task.run_id = run_id
        if report is not None:
            task.report = report
        self._save(ctx)

    def _save(self, ctx: ExecutionContext) -> None:
        """Persist an execution context to cache and disk."""
        self._cache[ctx.id] = ctx
        path = self._storage_dir / f"{ctx.id}.json"
        path.write_text(ctx.model_dump_json(indent=2))

    def _load(self, execution_id: str) -> ExecutionContext | None:
        """Load an execution context from disk into cache."""
        path = self._storage_dir / f"{execution_id}.json"
        if not path.exists():
            return None
        ctx = ExecutionContext.model_validate_json(path.read_text())
        self._cache[execution_id] = ctx
        return ctx
