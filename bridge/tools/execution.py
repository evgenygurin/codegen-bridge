"""Execution context management tools: start, get context, agent rules.

Business logic lives in ``ExecutionService``; these tools handle
elicitation, MCP logging, and JSON serialisation.
"""

from __future__ import annotations

import json
from typing import Literal

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.annotations import CREATES, READ_ONLY, READ_ONLY_LOCAL
from bridge.dependencies import CurrentContext, Depends, get_execution_service
from bridge.elicitation import confirm_action
from bridge.icons import ICON_CONTEXT, ICON_EXECUTION, ICON_RULES
from bridge.services.execution import ExecutionService


def register_execution_tools(mcp: FastMCP) -> None:
    """Register all execution context management tools on the given FastMCP server."""

    @mcp.tool(tags={"context"}, icons=ICON_EXECUTION, timeout=60, annotations=CREATES)
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
        svc: ExecutionService = Depends(get_execution_service),    ) -> str: # type: ignore[arg-type]
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

        # Detect repo
        repo_id = await svc.detect_repo()
        if repo_id is not None and not confirmed:
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

        # Load agent rules
        agent_rules = await svc.load_agent_rules()

        result = await svc.start_execution(
            execution_id=execution_id,
            goal=goal,
            mode=mode,
            tasks=tasks,
            tech_stack=tech_stack,
            architecture=architecture,
            repo_structure=repo_structure,
            repo_id=repo_id,
            agent_rules=agent_rules or None,
        )
        await ctx.info(
            f"Execution started: id={result['execution_id']}, "
            f"tasks={result['tasks']}, has_rules={result['has_rules']}"
        )
        return json.dumps(result)

    @mcp.tool(tags={"context"}, icons=ICON_CONTEXT, timeout=10, annotations=READ_ONLY_LOCAL)
    async def codegen_get_execution_context(
        execution_id: str | None = None,
        ctx: Context = CurrentContext(),
        svc: ExecutionService = Depends(get_execution_service),    ) -> str: # type: ignore[arg-type]
        """Get full execution context — active or by ID.

        Returns the complete execution state including tasks, rules, and metadata.

        Args:
            execution_id: Specific execution ID. If not provided, returns the active execution.
        """
        await ctx.info(f"Fetching execution context: id={execution_id or 'active'}")
        exec_ctx = await svc.get_execution_context(execution_id)

        if exec_ctx is None:
            await ctx.warning(f"No execution context found for id={execution_id or 'active'}")
            return json.dumps({"error": "No execution context found"})

        return exec_ctx.model_dump_json(indent=2)

    @mcp.tool(tags={"context"}, icons=ICON_RULES, timeout=30, annotations=READ_ONLY)
    async def codegen_get_agent_rules(
        ctx: Context = CurrentContext(),
        svc: ExecutionService = Depends(get_execution_service),    ) -> str: # type: ignore[arg-type]
        """Fetch organization agent rules from the Codegen API.

        Returns organization-level rules and user custom prompts that should
        guide agent behavior.
        """
        await ctx.info("Fetching agent rules")
        rules = await svc.get_agent_rules()
        await ctx.info("Agent rules fetched successfully")
        return json.dumps(rules)
