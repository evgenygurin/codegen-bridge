"""Agent run management tools: create, get, list, resume, stop, ban, unban, remove-from-pr, logs.

Long-running tools (``codegen_create_run``, ``codegen_get_logs``) use
``TaskConfig(mode="optional")`` so clients that support background tasks
can offload them, while clients without task support still get the
result synchronously.  Progress is reported via ``ctx.report_progress``
so callers can track multi-step operations in real time.

Endpoints coverage (per Codegen API v1):
- POST /v1/organizations/{org_id}/agent/run           — create
- GET  /v1/organizations/{org_id}/agent/run/{id}      — get
- GET  /v1/organizations/{org_id}/agent/runs           — list
- POST /v1/organizations/{org_id}/agent/run/resume     — resume
- POST /v1/organizations/{org_id}/agent/run/ban        — ban
- POST /v1/organizations/{org_id}/agent/run/unban      — unban
- POST /v1/organizations/{org_id}/agent/run/remove-from-pr — remove from PR
- GET  /v1/organizations/{org_id}/agent/run/{id}/logs  — logs
"""

from __future__ import annotations

import json
from contextlib import suppress as _suppress
from datetime import timedelta
from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.server.tasks import TaskConfig

from bridge.client import CodegenClient
from bridge.context import ContextRegistry, PRInfo, TaskReport
from bridge.dependencies import CurrentContext, Depends, get_client, get_registry, get_repo_cache
from bridge.elicitation import confirm_action, select_choice
from bridge.helpers.formatting import format_run_basic
from bridge.helpers.pagination import (
    DEFAULT_PAGE_SIZE,
    build_paginated_response,
    cursor_to_offset,
    next_cursor_or_none,
)
from bridge.helpers.repo_detection import RepoCache, detect_repo_id
from bridge.icons import (
    ICON_BAN,
    ICON_GET_RUN,
    ICON_LIST,
    ICON_LOGS,
    ICON_REMOVE_FROM_PR,
    ICON_RESUME,
    ICON_RUN,
    ICON_STOP,
    ICON_UNBAN,
)
from bridge.log_parser import parse_logs
from bridge.prompt_builder import build_task_prompt

# ── Task configurations for long-running operations ──────

CREATE_RUN_TASK = TaskConfig(
    mode="optional",
    poll_interval=timedelta(seconds=5),
)
"""Create-run is multi-step (validate → enrich → detect repo → API call → track)."""

GET_LOGS_TASK = TaskConfig(
    mode="optional",
    poll_interval=timedelta(seconds=3),
)
"""Get-logs does a single API fetch + formatting — faster poll."""

# Total progress steps for each operation
_CREATE_RUN_STEPS = 5
_GET_LOGS_STEPS = 3


async def _report(ctx: Context, progress: float, total: float, message: str) -> None:
    """Best-effort progress report — never raises."""
    with _suppress(Exception):
        await ctx.report_progress(progress=progress, total=total, message=message)


def register_agent_tools(mcp: FastMCP) -> None:
    """Register all agent run management tools on the given FastMCP server."""

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
        total = _CREATE_RUN_STEPS
        step = 0

        # Step 1: Validate input
        has_exec = execution_id is not None
        await _report(ctx, step, total, "Validating input")
        await ctx.info(f"Creating agent run: agent_type={agent_type}, has_execution={has_exec}")
        effective_prompt = prompt
        step += 1

        # Step 2: Enrich prompt from execution context
        await _report(ctx, step, total, "Enriching prompt")
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
        await _report(ctx, step, total, "Detecting repository")
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
                "Choose a model for this agent run (or decline to use the organization default):",
                available_models,
            )
            if selected is not None:
                model = selected

        # Elicit repo confirmation when auto-detected (not explicitly provided)
        if not confirmed:
            user_confirmed = await confirm_action(
                ctx,
                f"Create agent run on repo_id={repo_id} with model={model or 'org default'}?",
            )
            if not user_confirmed:
                return json.dumps(
                    {
                        "action": "cancelled",
                        "reason": "User declined to create run",
                    }
                )

        # Step 4: Create the agent run
        await _report(ctx, step, total, "Creating agent run")
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
        await _report(ctx, step, total, "Tracking in execution context")
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

        await _report(ctx, total, total, "Agent run created")
        return json.dumps(
            {
                "id": run.id,
                "status": run.status,
                "web_url": run.web_url,
            }
        )

    # ── Get ───────────────────────────────────────────────

    @mcp.tool(tags={"execution"}, icons=ICON_GET_RUN)
    async def codegen_get_run(
        run_id: int,
        execution_id: str | None = None,
        task_index: int | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
        registry: ContextRegistry = Depends(get_registry),  # type: ignore[arg-type]
    ) -> str:
        """Get agent run status, result, summary, and created PRs.

        Use this to poll for completion (check status field).

        Args:
            run_id: Agent run ID.
            execution_id: Optional execution context ID for auto-reporting.
            task_index: Task index within the execution (default: current_task_index).
        """
        await ctx.info(f"Fetching run: id={run_id}")
        run = await client.get_run(run_id)

        result: dict[str, Any] = {
            "id": run.id,
            "status": run.status,
            "web_url": run.web_url,
        }
        if run.result:
            result["result"] = run.result
        if run.summary:
            result["summary"] = run.summary
        if run.source_type:
            result["source_type"] = run.source_type

        pr_list: list[dict[str, Any]] = []
        if run.github_pull_requests:
            pr_list = [
                {
                    k: v
                    for k, v in {
                        "url": pr.url,
                        "title": pr.title,
                        "head_branch_name": pr.head_branch_name,
                        "number": pr.number,
                        "state": pr.state,
                    }.items()
                    if v is not None
                }
                for pr in run.github_pull_requests
            ]
            result["pull_requests"] = pr_list

        # Auto-report back to execution context on terminal status
        if execution_id is not None and run.status in ("completed", "failed"):
            exec_ctx = await registry.get(execution_id)
            if exec_ctx is not None:
                idx = task_index if task_index is not None else exec_ctx.current_task_index
                if idx < len(exec_ctx.tasks):
                    # Parse logs for structured data
                    parsed = None
                    try:
                        logs_result = await client.get_logs(run_id, limit=100)
                        parsed = parse_logs(logs_result.logs)
                        result["parsed_logs"] = {
                            "files_changed": parsed.files_changed,
                            "key_decisions": parsed.key_decisions,
                            "test_results": parsed.test_results,
                            "commands_run": parsed.commands_run,
                            "total_steps": parsed.total_steps,
                        }
                    except Exception as exc:
                        await ctx.warning(f"Log parsing failed for run {run_id}: {exc}")

                    # Build TaskReport
                    report = TaskReport(
                        summary=run.summary or run.result or "",
                        web_url=run.web_url or "",
                        pull_requests=[
                            PRInfo(
                                url=pr.get("url", ""),
                                number=pr.get("number", 0),
                                title=pr.get("title", ""),
                                state=pr.get("state", ""),
                            )
                            for pr in pr_list
                        ],
                        files_changed=parsed.files_changed if parsed else [],
                        key_decisions=parsed.key_decisions if parsed else [],
                        test_results=parsed.test_results if parsed else None,
                        agent_notes=parsed.agent_notes if parsed else None,
                        commands_run=parsed.commands_run if parsed else [],
                        total_steps=parsed.total_steps if parsed else 0,
                    )

                    task_status: Literal["completed", "failed"] = (
                        "completed" if run.status == "completed" else "failed"
                    )
                    await registry.update_task(
                        execution_id=execution_id,
                        task_index=idx,
                        status=task_status,
                        report=report,
                    )

                    # Advance current_task_index if completed
                    if run.status == "completed":
                        exec_ctx.current_task_index = idx + 1
                        await registry._save(exec_ctx)

        return json.dumps(result)

    # ── List ──────────────────────────────────────────────

    @mcp.tool(tags={"execution"}, icons=ICON_LIST)
    async def codegen_list_runs(
        limit: int = DEFAULT_PAGE_SIZE,
        source_type: str | None = None,
        user_id: int | None = None,
        cursor: str | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """List recent agent runs with cursor-based pagination.

        Args:
            limit: Maximum number of runs per page (default 20).
            source_type: Filter by source — API, LOCAL, GITHUB, etc.
            user_id: Filter by user ID who initiated the agent runs.
            cursor: Opaque cursor from a previous response's ``next_cursor``
                field.  Omit or pass ``null`` for the first page.
        """
        offset = cursor_to_offset(cursor)
        await ctx.info(f"Listing runs: limit={limit}, offset={offset}, source_type={source_type}")
        page = await client.list_runs(
            skip=offset, limit=limit, source_type=source_type, user_id=user_id
        )
        await ctx.info(f"Listed {len(page.items)} of {page.total} runs")
        return json.dumps(
            build_paginated_response(
                items=[
                    {
                        "id": r.id,
                        "status": r.status,
                        "created_at": r.created_at,
                        "web_url": r.web_url,
                        "summary": r.summary,
                        "source_type": r.source_type,
                    }
                    for r in page.items
                ],
                total=page.total,
                offset=offset,
                page_size=limit,
                items_key="runs",
            )
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
                f"Are you sure you want to stop agent run {run_id}? This action cannot be undone.",
            )
            if not user_confirmed:
                return json.dumps(
                    {"run_id": run_id, "action": "cancelled", "reason": "User declined to stop"}
                )

        await ctx.warning(f"Stopping run: id={run_id}")
        run = await client.stop_run(run_id)
        await ctx.info(f"Run stopped: id={run_id}")
        return format_run_basic(run)

    # ── Ban ───────────────────────────────────────────────

    @mcp.tool(tags={"execution", "dangerous"}, icons=ICON_BAN)
    async def codegen_ban_run(
        run_id: int,
        before_card_order_id: str | None = None,
        after_card_order_id: str | None = None,
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Ban all checks for a PR and stop all related agents.

        Flags the PR to prevent future CI/CD check suite events from
        being processed and stops all current agents for that PR.

        Args:
            run_id: Agent run ID associated with the PR.
            before_card_order_id: Kanban order key for the card before this run.
            after_card_order_id: Kanban order key for the card after this run.
            confirmed: Skip interactive confirmation when True.
        """
        if not confirmed:
            user_confirmed = await confirm_action(
                ctx,
                f"Ban all checks for agent run {run_id}? "
                "This will stop all current agents on the PR and prevent "
                "future CI/CD check events from being processed.",
            )
            if not user_confirmed:
                return json.dumps(
                    {"run_id": run_id, "action": "cancelled", "reason": "User declined to ban"}
                )

        await ctx.warning(f"Banning checks for run: id={run_id}")
        result = await client.ban_run(
            run_id,
            before_card_order_id=before_card_order_id,
            after_card_order_id=after_card_order_id,
        )
        await ctx.info(f"Checks banned for run: id={run_id}")
        return json.dumps(
            {
                "run_id": run_id,
                "action": "banned",
                "message": result.message,
            }
        )

    # ── Unban ─────────────────────────────────────────────

    @mcp.tool(tags={"execution"}, icons=ICON_UNBAN)
    async def codegen_unban_run(
        run_id: int,
        before_card_order_id: str | None = None,
        after_card_order_id: str | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Unban all checks for a PR.

        Removes the ban flag from the PR to allow future CI/CD check suite
        events to be processed.  Handles both URL-based bans and
        parent-agent-run-based bans.

        Args:
            run_id: Agent run ID associated with the PR.
            before_card_order_id: Kanban order key for the card before this run.
            after_card_order_id: Kanban order key for the card after this run.
        """
        await ctx.info(f"Unbanning checks for run: id={run_id}")
        result = await client.unban_run(
            run_id,
            before_card_order_id=before_card_order_id,
            after_card_order_id=after_card_order_id,
        )
        await ctx.info(f"Checks unbanned for run: id={run_id}")
        return json.dumps(
            {
                "run_id": run_id,
                "action": "unbanned",
                "message": result.message,
            }
        )

    # ── Remove from PR ────────────────────────────────────

    @mcp.tool(tags={"execution", "dangerous"}, icons=ICON_REMOVE_FROM_PR)
    async def codegen_remove_from_pr(
        run_id: int,
        before_card_order_id: str | None = None,
        after_card_order_id: str | None = None,
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Remove Codegen from a PR.

        Performs the same action as banning all checks but with more
        user-friendly naming.  Flags the PR to prevent future CI/CD check
        suite events and stops all current agents for that PR.

        Args:
            run_id: Agent run ID associated with the PR.
            before_card_order_id: Kanban order key for the card before this run.
            after_card_order_id: Kanban order key for the card after this run.
            confirmed: Skip interactive confirmation when True.
        """
        if not confirmed:
            user_confirmed = await confirm_action(
                ctx,
                f"Remove Codegen from the PR associated with run {run_id}? "
                "This will stop all current agents and prevent future CI/CD checks.",
            )
            if not user_confirmed:
                return json.dumps(
                    {
                        "run_id": run_id,
                        "action": "cancelled",
                        "reason": "User declined to remove from PR",
                    }
                )

        await ctx.warning(f"Removing Codegen from PR for run: id={run_id}")
        result = await client.remove_from_pr(
            run_id,
            before_card_order_id=before_card_order_id,
            after_card_order_id=after_card_order_id,
        )
        await ctx.info(f"Codegen removed from PR for run: id={run_id}")
        return json.dumps(
            {
                "run_id": run_id,
                "action": "removed_from_pr",
                "message": result.message,
            }
        )

    # ── Logs ──────────────────────────────────────────────

    @mcp.tool(tags={"monitoring"}, icons=ICON_LOGS, task=GET_LOGS_TASK)
    async def codegen_get_logs(
        run_id: int,
        limit: int = DEFAULT_PAGE_SIZE,
        reverse: bool = True,
        cursor: str | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Get step-by-step agent execution logs with cursor-based pagination.

        Shows agent thoughts, tool calls, and outputs for debugging.
        Supports background execution with progress reporting.

        Args:
            run_id: Agent run ID.
            limit: Max log entries per page (default 20).
            reverse: If true, newest entries first.
            cursor: Opaque cursor from a previous response's ``next_cursor``
                field.  Omit or pass ``null`` for the first page.
        """
        total = _GET_LOGS_STEPS
        step = 0

        # Step 1: Parse pagination
        await _report(ctx, step, total, "Preparing log request")
        offset = cursor_to_offset(cursor)
        await ctx.info(f"Fetching logs: run_id={run_id}, limit={limit}, offset={offset}")
        step += 1

        # Step 2: Fetch from API
        await _report(ctx, step, total, f"Fetching logs for run {run_id}")
        result = await client.get_logs(run_id, skip=offset, limit=limit, reverse=reverse)
        await ctx.info(f"Fetched {len(result.logs)} log entries for run {run_id}")
        step += 1

        # Step 3: Format response
        await _report(ctx, step, total, "Formatting log entries")
        response = json.dumps(
            {
                "run_id": result.id,
                "status": result.status,
                "total_logs": result.total_logs,
                "next_cursor": next_cursor_or_none(offset, limit, result.total_logs or 0),
                "logs": [
                    {
                        k: v
                        for k, v in {
                            "thought": log.thought,
                            "tool_name": log.tool_name,
                            "tool_input": log.tool_input,
                            "tool_output": (
                                str(log.tool_output)[:500] if log.tool_output else None
                            ),
                            "message_type": log.message_type,
                            "created_at": log.created_at,
                        }.items()
                        if v is not None
                    }
                    for log in result.logs
                ],
            }
        )

        await _report(ctx, total, total, "Logs retrieved")
        return response
