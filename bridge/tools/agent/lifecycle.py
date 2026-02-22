"""Agent run lifecycle tools: create, resume, stop.

These tools manage the lifecycle of agent runs — creating new runs
(with optional execution context enrichment and repo auto-detection),
resuming paused runs, and stopping active runs.
"""

from __future__ import annotations

import json
from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context

from bridge.client import CodegenClient
from bridge.context import ContextRegistry
from bridge.dependencies import CurrentContext, Depends, get_client, get_registry, get_repo_cache
from bridge.elicitation import confirm_action, select_choice
from bridge.helpers.formatting import format_run_basic
from bridge.helpers.repo_detection import RepoCache, detect_repo_id
from bridge.icons import ICON_RESUME, ICON_RUN, ICON_STOP
from bridge.prompt_builder import build_task_prompt
from bridge.tools.agent._progress import CREATE_RUN_STEPS, CREATE_RUN_TASK, report


def register_lifecycle_tools(mcp: FastMCP) -> None:
    """Register agent run lifecycle tools (create, resume, stop)."""

    # ── Create ───────────────────────────────────────────

    @mcp.tool(tags={"execution"}, icons=ICON_RUN, task=CREATE_RUN_TASK)
    async def codegen_create_run(
        prompt: str,
        repo_id: int | None = None,
        model: str | None = None,
        agent_type: Literal["codegen", "claude_code"] = "claude_code",
        images: list[str] | None = None,
        execution_id: str | None = None,
        task_index: int | None = None,
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
        registry: ContextRegistry = Depends(get_registry),  # type: ignore[arg-type]
        repo_cache: RepoCache = Depends(get_repo_cache),  # type: ignore[arg-type]
    ) -> str:
        """Create a new Codegen agent run.

        The agent will execute the task in a cloud sandbox and may create a PR.
        Supports background execution with progress reporting.
        When ``model`` is not provided and the client supports elicitation,
        the user is prompted to choose a model interactively.

        Args:
            prompt: Task description for the agent (natural language, full context).
            repo_id: Repository ID. If not provided, auto-detected from git remote.
            model: LLM model to use. None = organization default or interactive selection.
            agent_type: Agent type — "codegen" or "claude_code".
            images: Optional list of base64-encoded data URIs for image input.
            execution_id: Optional execution context ID for prompt enrichment.
            task_index: Task index within the execution (default: current_task_index).
            confirmed: Skip interactive repo confirmation when True (for programmatic use).
        """
        total = CREATE_RUN_STEPS
        step = 0

        # Step 1: Validate input
        has_exec = execution_id is not None
        await report(ctx, step, total, "Validating input")
        await ctx.info(f"Creating agent run: agent_type={agent_type}, has_execution={has_exec}")
        effective_prompt = prompt
        step += 1

        # Step 2: Enrich prompt from execution context
        await report(ctx, step, total, "Enriching prompt")
        if execution_id is not None:
            exec_ctx = await registry.get(execution_id)
            if exec_ctx is not None:
                idx = task_index if task_index is not None else exec_ctx.current_task_index
                if idx < len(exec_ctx.tasks):
                    effective_prompt = build_task_prompt(exec_ctx, idx)
                    await registry.update_task(
                        execution_id=execution_id,
                        task_index=idx,
                        status="running",
                    )
                if repo_id is None and exec_ctx.repo_id is not None:
                    repo_id = exec_ctx.repo_id
        step += 1

        # Step 3: Detect repository
        await report(ctx, step, total, "Detecting repository")
        if repo_id is None:
            repo_id = await detect_repo_id(client, repo_cache)
            if repo_id is None:
                await ctx.error("Auto-detect repository failed; no repo_id provided")
                raise ToolError(
                    "Could not auto-detect repository. "
                    "Provide repo_id explicitly or run from a git repository "
                    "that is registered in your Codegen organization."
                )
        step += 1

        # Elicit model selection when not explicitly provided
        if model is None and not confirmed:
            available_models = ["claude-3-5-sonnet", "claude-3-5-haiku", "gpt-4o", "o3"]
            selected = await select_choice(
                ctx,
                "Choose a model for this agent run "
                "(or decline to use the organization default):",
                available_models,
            )
            if selected is not None:
                model = selected

        # Elicit repo confirmation when auto-detected (not explicitly provided)
        if not confirmed:
            user_confirmed = await confirm_action(
                ctx,
                f"Create agent run on repo_id={repo_id} "
                f"with model={model or 'org default'}?",
            )
            if not user_confirmed:
                return json.dumps(
                    {
                        "action": "cancelled",
                        "reason": "User declined to create run",
                    }
                )

        # Step 4: Create the agent run
        await report(ctx, step, total, "Creating agent run")
        run = await client.create_run(
            effective_prompt,
            repo_id=repo_id,
            model=model,
            agent_type=agent_type,
            images=images,
        )
        await ctx.info(f"Agent run created: id={run.id}, status={run.status}")
        step += 1

        # Step 5: Track in execution context
        await report(ctx, step, total, "Tracking in execution context")
        if execution_id is not None:
            exec_ctx = await registry.get(execution_id)
            if exec_ctx is not None:
                idx = task_index if task_index is not None else exec_ctx.current_task_index
                if idx < len(exec_ctx.tasks):
                    await registry.update_task(
                        execution_id=execution_id,
                        task_index=idx,
                        run_id=run.id,
                    )

        await report(ctx, total, total, "Agent run created")
        return json.dumps(
            {
                "id": run.id,
                "status": run.status,
                "web_url": run.web_url,
            }
        )

    # ── Resume ────────────────────────────────────────────

    @mcp.tool(tags={"execution"}, icons=ICON_RESUME)
    async def codegen_resume_run(
        run_id: int,
        prompt: str,
        model: str | None = None,
        images: list[str] | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Resume a paused or blocked agent run with new instructions.

        Args:
            run_id: Agent run ID to resume.
            prompt: New instructions or clarification for the agent.
            model: Optionally switch model for the resumed run.
            images: Optional list of base64-encoded data URIs for image input.
        """
        await ctx.info(f"Resuming run: id={run_id}")
        run = await client.resume_run(run_id, prompt, model=model, images=images)
        await ctx.info(f"Run resumed: id={run.id}, status={run.status}")
        return format_run_basic(run)

    # ── Stop (legacy alias for ban) ──────────────────────

    @mcp.tool(tags={"execution", "dangerous"}, icons=ICON_STOP)
    async def codegen_stop_run(
        run_id: int,
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Stop a running agent. Use when a task needs to be cancelled.

        Asks for user confirmation before stopping unless ``confirmed=True``.
        This is a convenience alias for ``codegen_ban_run``.

        Args:
            run_id: Agent run ID to stop.
            confirmed: Skip interactive confirmation when True (for programmatic use).
        """
        if not confirmed:
            user_confirmed = await confirm_action(
                ctx,
                f"Are you sure you want to stop agent run {run_id}? "
                "This action cannot be undone.",
            )
            if not user_confirmed:
                return json.dumps(
                    {"run_id": run_id, "action": "cancelled", "reason": "User declined to stop"}
                )

        await ctx.warning(f"Stopping run: id={run_id}")
        run = await client.stop_run(run_id)
        await ctx.info(f"Run stopped: id={run_id}")
        return format_run_basic(run)
