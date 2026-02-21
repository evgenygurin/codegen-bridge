"""Execution context models and registry for structured agent communication."""

from __future__ import annotations

from datetime import datetime, timezone
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
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
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
    """Registry for managing execution contexts.

    Stores and retrieves execution contexts by ID. Provides methods
    to create, update, and query contexts for structured agent communication.
    """

    def __init__(self) -> None:
        self._contexts: dict[str, ExecutionContext] = {}

    def register(self, context: ExecutionContext) -> None:
        """Register an execution context."""
        self._contexts[context.id] = context

    def get(self, context_id: str) -> ExecutionContext | None:
        """Retrieve an execution context by ID."""
        return self._contexts.get(context_id)

    def list_active(self) -> list[ExecutionContext]:
        """List all active execution contexts."""
        return [ctx for ctx in self._contexts.values() if ctx.status == "active"]

    def remove(self, context_id: str) -> bool:
        """Remove an execution context. Returns True if it existed."""
        return self._contexts.pop(context_id, None) is not None
