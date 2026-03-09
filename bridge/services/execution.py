"""Execution context business logic.

``ExecutionService`` manages execution contexts: starting new
executions with repo detection and rules loading, retrieving
context state, and fetching agent rules.

Services never touch MCP ``Context`` — they use ``logging`` for
diagnostics and return plain dicts / model instances for the tool
layer to serialise.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from bridge.client import CodegenClient
from bridge.context import ContextRegistry, ExecutionContext
from bridge.helpers.repo_detection import RepoCache, detect_repo_id

logger = logging.getLogger("bridge.services.execution")


class ExecutionService:
    """Domain service for execution context operations.

    Constructed per-request via DI — receives pre-existing resources
    from the lifespan context.
    """

    def __init__(
        self,
        client: CodegenClient,
        registry: ContextRegistry,
        repo_cache: RepoCache,
    ) -> None:
        self._client = client
        self._registry = registry
        self._repo_cache = repo_cache

    # ── Repo detection ────────────────────────────────────

    async def detect_repo(self) -> int | None:
        """Auto-detect repository ID from git remote."""
        return await detect_repo_id(self._client, self._repo_cache)

    # ── Rules ─────────────────────────────────────────────

    async def load_agent_rules(self) -> str:
        """Load and combine organization rules and user custom prompt.

        Returns the combined rules string (may be empty).
        Logs a warning and returns empty string on failure.
        """
        try:
            rules = await self._client.get_rules()
            org_rules = rules.get("organization_rules", "")
            user_prompt = rules.get("user_custom_prompt", "")
            return "\n\n".join(filter(None, [org_rules, user_prompt]))
        except Exception as exc:
            logger.warning("Rules enrichment failed: %s", exc)
            return ""

    async def get_agent_rules(self) -> dict[str, Any]:
        """Fetch raw agent rules from the Codegen API."""
        return await self._client.get_rules()

    # ── Lifecycle ─────────────────────────────────────────

    async def start_execution(
        self,
        *,
        execution_id: str,
        goal: str,
        mode: Literal["plan", "adhoc"] = "adhoc",
        tasks: list[dict[str, str]] | None = None,
        tech_stack: list[str] | None = None,
        architecture: str | None = None,
        repo_structure: str | None = None,
        repo_id: int | None = None,
        agent_rules: str | None = None,
    ) -> dict[str, Any]:
        """Create a new execution context.

        Builds task tuples, applies optional metadata, and persists
        via the registry.  Returns a summary dict for the tool layer.
        """
        # Build task tuples from dicts
        task_tuples: list[tuple[str, str]] | None = None
        if tasks:
            task_tuples = [
                (t["title"], t.get("description", t["title"])) for t in tasks
            ]

        # Build extra kwargs for ExecutionContext
        kwargs: dict[str, Any] = {}
        if tech_stack:
            kwargs["tech_stack"] = tech_stack
        if architecture:
            kwargs["architecture"] = architecture
        if repo_structure:
            kwargs["repo_structure"] = repo_structure
        if repo_id is not None:
            kwargs["repo_id"] = repo_id
        if agent_rules:
            kwargs["agent_rules"] = agent_rules

        exec_ctx = await self._registry.start_execution(
            execution_id=execution_id,
            mode=mode,
            goal=goal,
            tasks=task_tuples,
            **kwargs,
        )
        logger.info(
            "Execution started: id=%s, tasks=%d, has_rules=%s",
            exec_ctx.id,
            len(exec_ctx.tasks),
            bool(exec_ctx.agent_rules),
        )
        return {
            "execution_id": exec_ctx.id,
            "mode": exec_ctx.mode,
            "status": exec_ctx.status,
            "tasks": len(exec_ctx.tasks),
            "has_rules": bool(exec_ctx.agent_rules),
        }

    # ── Queries ───────────────────────────────────────────

    async def get_execution_context(
        self,
        execution_id: str | None = None,
    ) -> ExecutionContext | None:
        """Retrieve execution context — by ID or the active one.

        Returns the ``ExecutionContext`` model (or ``None``).
        The tool layer decides on serialisation format.
        """
        if execution_id:
            return await self._registry.get(execution_id)
        return await self._registry.get_active()
