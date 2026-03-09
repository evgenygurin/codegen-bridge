"""Agent run lifecycle tools: create, resume, stop.

These tools manage the lifecycle of agent runs — creating new runs
(with optional execution context enrichment and repo auto-detection),
resuming paused runs, and stopping active runs.

Business logic lives in ``RunService``; these tools handle MCP
concerns: elicitation, progress reporting, and JSON serialisation.
"""

from __future__ import annotations

import json
from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context

from bridge.dependencies import CurrentContext, Depends, get_run_service
from bridge.elicitation import confirm_action, select_choice
from bridge.icons import ICON_RESUME, ICON_RUN, ICON_STOP
from bridge.services.runs import RunService
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
        svc: RunService = Depends(get_run_service),  # type: ignore[arg-type]
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
        await report(ctx, step, total, "Validating input")
        await ctx.info(
            f"Creating agent run: agent_type={agent_type}, "
            f"has_execution={execution_id is not None}"
        )
        step += 1

        # Step 2: Enrich prompt from execution context
        await report(ctx, step, total, "Enriching prompt")
        effective_prompt, ctx_repo_id = await svc.enrich_prompt(
            prompt, execution_id, task_index
        )
        if repo_id is None and ctx_repo_id is not None:
            repo_id = ctx_repo_id
        step += 1

        # Step 3: Detect repository
        await report(ctx, step, total, "Detecting repository")
        if repo_id is None:
            repo_id = await svc.detect_repo()
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

        # Elicit repo confirmation
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
        result = await svc.create_run(
            effective_prompt,
            repo_id=repo_id,
            model=model,
            agent_type=agent_type,
            images=images,
        )
        await ctx.info(f"Agent run created: id={result['id']}, status={result['status']}")
        step += 1

        # Step 5: Track in execution context
        await report(ctx, step, total, "Tracking in execution context")
        await svc.track_run_in_execution(result["id"], execution_id, task_index)

        await report(ctx, total, total, "Agent run created")
        return json.dumps(result)

    # ── Resume ────────────────────────────────────────────

    @mcp.tool(tags={"execution"}, icons=ICON_RESUME)
    async def codegen_resume_run(
        run_id: int,
        prompt: str,
        model: str | None = None,
        images: list[str] | None = None,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service),  # type: ignore[arg-type]
    ) -> str:
        """Resume a paused or blocked agent run with new instructions.

        Args:
            run_id: Agent run ID to resume.
            prompt: New instructions or clarification for the agent.
            model: Optionally switch model for the resumed run.
            images: Optional list of base64-encoded data URIs for image input.
        """
        await ctx.info(f"Resuming run: id={run_id}")
        result = await svc.resume_run(run_id, prompt, model=model, images=images)
        await ctx.info(f"Run resumed: id={result['id']}, status={result['status']}")
        return json.dumps(result)

    # ── Stop (legacy alias for ban) ──────────────────────

    @mcp.tool(tags={"execution", "dangerous"}, icons=ICON_STOP)
    async def codegen_stop_run(
        run_id: int,
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service),  # type: ignore[arg-type]
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
        result = await svc.stop_run(run_id)
        await ctx.info(f"Run stopped: id={run_id}")
        return json.dumps(result)
