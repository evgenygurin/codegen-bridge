"""Execution context management tools: start, get context, agent rules."""

from __future__ import annotations

import json
from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.client import CodegenClient
from bridge.context import ContextRegistry
from bridge.dependencies import CurrentContext, Depends, get_client, get_registry, get_repo_cache
from bridge.elicitation import confirm_action
from bridge.helpers.repo_detection import RepoCache, detect_repo_id
from bridge.icons import ICON_CONTEXT, ICON_EXECUTION, ICON_RULES


def register_execution_tools(mcp: FastMCP) -> None:
    """Register all execution context management tools on the given FastMCP server."""

    @mcp.tool(tags={"context"}, icons=ICON_EXECUTION)
    async def codegen_start_execution(
        execution_id: str,
        goal: str,
        mode: Literal["plan", "adhoc"] = "adhoc",
        tasks: list[dict[str, str]] | None = None,
        tech_stack: list[str] | None = None,
        architecture: str | None = None,
        repo_structure: str | None = None,
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),
        registry: ContextRegistry = Depends(get_registry),
        repo_cache: RepoCache = Depends(get_repo_cache),
    ) -> str:
        """Initialize an execution context, load agent rules and integrations.

        Call this at the start of a plan or ad-hoc task to set up full context
        that will be available to all subsequent agent runs.
        When a repository is auto-detected and the client supports elicitation,
        the user is prompted to confirm the detected repo.

        Args:
            execution_id: Unique identifier for the execution.
            goal: High-level goal description.
            mode: "plan" for multi-task plans, "adhoc" for single tasks.
            tasks: List of {"title": ..., "description": ...} for plan mode.
            tech_stack: Technologies used (e.g. ["Python", "FastAPI"]).
            architecture: Architecture description.
            repo_structure: Repository structure overview.
            confirmed: Skip interactive repo confirmation when True (programmatic use).
        """
        await ctx.info(f"Starting execution: id={execution_id}, mode={mode}")

        # Build task tuples from dicts
        task_tuples: list[tuple[str, str]] | None = None
        if tasks:
            task_tuples = [(t["title"], t.get("description", t["title"])) for t in tasks]

        # Build extra kwargs for ExecutionContext
        kwargs: dict[str, Any] = {}
        if tech_stack:
            kwargs["tech_stack"] = tech_stack
        if architecture:
            kwargs["architecture"] = architecture
        if repo_structure:
            kwargs["repo_structure"] = repo_structure

        # Detect repo
        repo_id = await detect_repo_id(client, repo_cache)
        if repo_id is not None:
            # Elicit confirmation for auto-detected repository
            if not confirmed:
                user_confirmed = await confirm_action(
                    ctx,
                    f"Start execution '{goal}' using detected repo_id={repo_id}?",
                )
                if not user_confirmed:
                    return json.dumps(
                        {
                            "action": "cancelled",
                            "reason": "User declined to use detected repository",
                        }
                    )
            kwargs["repo_id"] = repo_id

        # Load agent rules
        try:
            rules = await client.get_rules()
            org_rules = rules.get("organization_rules", "")
            user_prompt = rules.get("user_custom_prompt", "")
            combined = "\n\n".join(filter(None, [org_rules, user_prompt]))
            if combined:
                kwargs["agent_rules"] = combined
        except Exception as exc:
            await ctx.warning(f"Rules enrichment failed, continuing without rules: {exc}")

        exec_ctx = await registry.start_execution(
            execution_id=execution_id,
            mode=mode,
            goal=goal,
            tasks=task_tuples,
            **kwargs,
        )
        await ctx.info(
            f"Execution started: id={exec_ctx.id}, tasks={len(exec_ctx.tasks)}, "
            f"has_rules={bool(exec_ctx.agent_rules)}"
        )
        return json.dumps(
            {
                "execution_id": exec_ctx.id,
                "mode": exec_ctx.mode,
                "status": exec_ctx.status,
                "tasks": len(exec_ctx.tasks),
                "has_rules": bool(exec_ctx.agent_rules),
            }
        )

    @mcp.tool(tags={"context"}, icons=ICON_CONTEXT)
    async def codegen_get_execution_context(
        execution_id: str | None = None,
        ctx: Context = CurrentContext(),
        registry: ContextRegistry = Depends(get_registry)
    ) -> str:
        """Get full execution context — active or by ID.

        Returns the complete execution state including tasks, rules, and metadata.

        Args:
            execution_id: Specific execution ID. If not provided, returns the active execution.
        """
        await ctx.info(f"Fetching execution context: id={execution_id or 'active'}")
        if execution_id:
            exec_ctx = await registry.get(execution_id)
        else:
            exec_ctx = await registry.get_active()

        if exec_ctx is None:
            await ctx.warning(f"No execution context found for id={execution_id or 'active'}")
            return json.dumps({"error": "No execution context found"})

        return exec_ctx.model_dump_json(indent=2)

    @mcp.tool(tags={"context"}, icons=ICON_RULES)
    async def codegen_get_agent_rules(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client)
    ) -> str:
        """Fetch organization agent rules from the Codegen API.

        Returns organization-level rules and user custom prompts that should
        guide agent behavior.
        """
        await ctx.info("Fetching agent rules")
        rules = await client.get_rules()
        await ctx.info("Agent rules fetched successfully")
        return json.dumps(rules)
