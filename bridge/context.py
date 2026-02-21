"""Execution context models and registry for structured agent communication."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from bridge.storage import MemoryStorage, StorageBackend


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
    """Manages execution contexts with pluggable storage backends.

    Uses a ``StorageBackend`` (Strategy pattern) for persistence and keeps
    an in-memory write-through cache for fast lookups.  All public mutating
    methods are ``async`` because the underlying storage may perform I/O.

    The default backend is ``MemoryStorage`` — swap to ``FileStorage`` for
    persistence across restarts.
    """

    def __init__(self, storage: StorageBackend | None = None) -> None:
        self._storage: StorageBackend = storage or MemoryStorage()
        self._cache: dict[str, ExecutionContext] = {}

    async def setup(self) -> None:
        """Initialise the storage backend and warm the in-memory cache."""
        await self._storage.setup()
        # Warm cache from any data already in the store.
        for key in await self._storage.keys():
            data = await self._storage.get(key)
            if data is not None:
                self._cache[key] = ExecutionContext.model_validate(data)

    async def start_execution(
        self,
        *,
        execution_id: str,
        mode: Literal["plan", "adhoc"],
        goal: str,
        tasks: list[tuple[str, str]] | None = None,
        **kwargs: Any,
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
        await self._save(ctx)
        return ctx

    async def get(self, execution_id: str) -> ExecutionContext | None:
        """Retrieve an execution context by ID (cache first, then store)."""
        if execution_id in self._cache:
            return self._cache[execution_id]
        return await self._load(execution_id)

    async def get_active(self) -> ExecutionContext | None:
        """Find the first active execution context (cache then store scan)."""
        # Check cache first
        for ctx in self._cache.values():
            if ctx.status == "active":
                return ctx
        # Fall back to scanning the store
        for key in await self._storage.keys():
            if key in self._cache:
                continue  # Already checked above
            loaded = await self._load(key)
            if loaded is not None and loaded.status == "active":
                return loaded
        return None

    async def update_task(
        self,
        *,
        execution_id: str,
        task_index: int,
        status: Literal["pending", "running", "completed", "failed", "skipped"] | None = None,
        run_id: int | None = None,
        report: TaskReport | None = None,
    ) -> None:
        """Update a task's status, run_id, or report within an execution."""
        ctx = await self.get(execution_id)
        if ctx is None or task_index >= len(ctx.tasks):
            return
        task = ctx.tasks[task_index]
        if status is not None:
            task.status = status
        if run_id is not None:
            task.run_id = run_id
        if report is not None:
            task.report = report
        await self._save(ctx)

    async def _save(self, ctx: ExecutionContext) -> None:
        """Persist an execution context to cache and store."""
        self._cache[ctx.id] = ctx
        await self._storage.put(ctx.id, ctx.model_dump(mode="json"))

    async def _load(self, execution_id: str) -> ExecutionContext | None:
        """Load an execution context from the store into cache."""
        data = await self._storage.get(execution_id)
        if data is None:
            return None
        ctx = ExecutionContext.model_validate(data)
        self._cache[execution_id] = ctx
        return ctx
