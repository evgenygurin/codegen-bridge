"""MCP tool definitions that leverage server-side sampling.

Each tool uses ``SamplingService`` to request LLM completions via
``ctx.sample()`` — the actual inference is done by the connected
client or a configured fallback handler.

All sampling tools use ``task=TaskConfig(mode="optional")`` so they
can run as background tasks with progress reporting.  This prevents
timeout failures on the 30-60 second LLM invocations.
"""

from __future__ import annotations

import json
from contextlib import suppress
from datetime import timedelta
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.server.tasks import TaskConfig

from bridge.annotations import READ_ONLY
from bridge.client import CodegenClient
from bridge.context import ContextRegistry
from bridge.dependencies import CurrentContext, Depends, get_client, get_registry, get_run_service
from bridge.icons import ICON_SAMPLING_ANALYSIS, ICON_SAMPLING_PROMPT, ICON_SAMPLING_SUMMARY
from bridge.sampling.config import SamplingConfig
from bridge.sampling.service import SamplingService
from bridge.services.runs import RunService

# ── Task configurations for sampling operations ──────────
# Sampling tools invoke ctx.sample() which can take 30-60 seconds.
# Background task support prevents MCP protocol timeouts.

SAMPLING_TASK = TaskConfig(
    mode="optional",
    poll_interval=timedelta(seconds=5),
)
"""Standard task config for sampling tools — 5s poll interval."""


async def _report(ctx: Context, progress: float, total: float, message: str) -> None:
    """Best-effort progress report — never raises."""
    with suppress(Exception):
        await ctx.report_progress(progress=progress, total=total, message=message)


def _get_sampling_config(ctx: Context) -> SamplingConfig:
    """Resolve ``SamplingConfig`` from lifespan context, with a safe default."""
    lc = ctx.lifespan_context
    if lc and "sampling_config" in lc:
        cfg: SamplingConfig = lc["sampling_config"]
        return cfg
    return SamplingConfig()


def register_sampling_tools(mcp: FastMCP) -> None:
    """Register all sampling-powered tools on the given FastMCP server."""

    @mcp.tool(
        tags={"sampling", "monitoring"},
        icons=ICON_SAMPLING_SUMMARY,
        task=SAMPLING_TASK,
        timeout=120,
        annotations=READ_ONLY,
    )
    async def codegen_summarise_run(
        run_id: int,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service), # type: ignore[arg-type]
        client: CodegenClient = Depends(get_client), # type: ignore[arg-type]
    ) -> str:
        """Generate an AI-powered summary of an agent run.

        Uses server-side LLM sampling to produce a concise, actionable
        summary from the run's status, result, PRs, and parsed logs.
        Supports background execution with progress reporting.

        Args:
            run_id: Agent run ID to summarise.
        """
        total = 4
        step = 0

        # Step 1: Fetch run data
        await _report(ctx, step, total, "Fetching run data")
        await ctx.info(f"Sampling: summarising run {run_id}")
        run_data = await svc.get_run(run_id)
        step += 1

        # Step 2: Enrich with parsed logs
        await _report(ctx, step, total, "Fetching and parsing logs")
        try:
            logs_result = await client.get_logs(run_id, limit=50)
            if logs_result.logs:
                from bridge.log_parser import parse_logs

                parsed = parse_logs(logs_result.logs)
                run_data["parsed_logs"] = {
                    "files_changed": parsed.files_changed,
                    "key_decisions": parsed.key_decisions,
                    "test_results": parsed.test_results,
                    "total_steps": parsed.total_steps,
                }
        except (httpx.HTTPError, KeyError, ValueError):
            await ctx.warning(f"Could not fetch logs for run {run_id}; summarising without them")
        step += 1

        # Step 3: Generate AI summary via sampling
        await _report(ctx, step, total, "Generating AI summary")
        cfg = _get_sampling_config(ctx)
        service = SamplingService(ctx, cfg)
        summary = await service.summarise_run(run_data)
        step += 1

        await _report(ctx, total, total, "Summary complete")
        await ctx.info(f"Sampling: run {run_id} summary generated ({len(summary)} chars)")
        return json.dumps({"run_id": run_id, "ai_summary": summary})

    @mcp.tool(
        tags={"sampling", "monitoring"},
        icons=ICON_SAMPLING_SUMMARY,
        task=SAMPLING_TASK,
        timeout=120,
        annotations=READ_ONLY,
    )
    async def codegen_summarise_execution(
        execution_id: str | None = None,
        ctx: Context = CurrentContext(),
        registry: ContextRegistry = Depends(get_registry),    ) -> str: # type: ignore[arg-type]
        """Generate an AI-powered summary of a full execution plan.

        Summarises all tasks, their statuses, PRs, and key decisions
        into a concise report using server-side LLM sampling.
        Supports background execution with progress reporting.

        Args:
            execution_id: Execution ID. If not given, uses the active execution.
        """
        total = 3
        step = 0

        # Step 1: Fetch execution context
        await _report(ctx, step, total, "Fetching execution context")
        await ctx.info(f"Sampling: summarising execution {execution_id or 'active'}")
        if execution_id:
            exec_ctx = await registry.get(execution_id)
        else:
            exec_ctx = await registry.get_active()
        if exec_ctx is None:
            return json.dumps({"error": "No execution context found"})
        step += 1

        # Step 2: Generate AI summary via sampling
        await _report(ctx, step, total, "Generating AI summary")
        cfg = _get_sampling_config(ctx)
        service = SamplingService(ctx, cfg)
        summary = await service.summarise_execution(exec_ctx.model_dump_json(indent=2))
        step += 1

        await _report(ctx, total, total, "Summary complete")
        await ctx.info(f"Sampling: execution summary generated ({len(summary)} chars)")
        return json.dumps(
            {
                "execution_id": exec_ctx.id,
                "status": exec_ctx.status,
                "ai_summary": summary,
            }
        )

    @mcp.tool(
        tags={"sampling", "context"},
        icons=ICON_SAMPLING_PROMPT,
        task=SAMPLING_TASK,
        timeout=120,
        annotations=READ_ONLY,
    )
    async def codegen_generate_task_prompt(
        goal: str,
        task_description: str,
        tech_stack: list[str] | None = None,
        architecture: str | None = None,
        execution_id: str | None = None,
        ctx: Context = CurrentContext(),
        registry: ContextRegistry = Depends(get_registry),    ) -> str: # type: ignore[arg-type]
        """Use AI to generate a detailed, optimised prompt for a Codegen agent.

        The LLM produces a structured, self-contained prompt based on the
        provided goal, task, and optional context. Much richer than the
        static template in ``build_task_prompt``.
        Supports background execution with progress reporting.

        Args:
            goal: High-level project goal.
            task_description: What this specific task should accomplish.
            tech_stack: Technologies in use (e.g. ["Python", "FastAPI"]).
            architecture: Architecture overview string.
            execution_id: Optional execution ID to pull completed-task context from.
        """
        total = 3
        step = 0

        # Step 1: Gather context
        await _report(ctx, step, total, "Gathering context")
        await ctx.info("Sampling: generating task prompt")
        completed_tasks: list[dict[str, Any]] | None = None
        if execution_id:
            exec_ctx = await registry.get(execution_id)
            if exec_ctx is not None:
                completed_tasks = [
                    {
                        "title": t.title,
                        "status": t.status,
                        "summary": t.report.summary if t.report else "",
                    }
                    for t in exec_ctx.tasks
                    if t.status in ("completed", "failed")
                ]
                # Fill in from execution context if not explicitly provided
                if not tech_stack and exec_ctx.tech_stack:
                    tech_stack = exec_ctx.tech_stack
                if not architecture and exec_ctx.architecture:
                    architecture = exec_ctx.architecture
        step += 1

        # Step 2: Generate prompt via sampling
        await _report(ctx, step, total, "Generating optimised prompt")
        cfg = _get_sampling_config(ctx)
        service = SamplingService(ctx, cfg)
        prompt = await service.generate_task_prompt(
            goal=goal,
            task_description=task_description,
            tech_stack=tech_stack,
            architecture=architecture,
            completed_tasks=completed_tasks,
        )
        step += 1

        await _report(ctx, total, total, "Prompt generated")
        await ctx.info(f"Sampling: task prompt generated ({len(prompt)} chars)")
        return json.dumps({"generated_prompt": prompt})

    @mcp.tool(
        tags={"sampling", "monitoring"},
        icons=ICON_SAMPLING_ANALYSIS,
        task=SAMPLING_TASK,
        timeout=120,
        annotations=READ_ONLY,
    )
    async def codegen_analyse_run_logs(
        run_id: int,
        limit: int = 50,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service), # type: ignore[arg-type]
    ) -> str:
        """Analyse agent execution logs with AI to identify patterns and issues.

        Fetches logs for the given run and uses LLM sampling to produce
        structured insights: accomplishments, errors, test results, and
        improvement suggestions.
        Supports background execution with progress reporting.

        Args:
            run_id: Agent run ID whose logs to analyse.
            limit: Maximum log entries to analyse (default 50).
        """
        total = 3
        step = 0

        # Step 1: Fetch logs
        await _report(ctx, step, total, f"Fetching logs for run {run_id}")
        await ctx.info(f"Sampling: analysing logs for run {run_id}")
        logs_data = await svc.get_logs(run_id, limit=limit)
        log_dicts: list[dict[str, Any]] = logs_data["logs"]
        step += 1

        # Step 2: Analyse via sampling
        await _report(ctx, step, total, "Analysing logs with AI")
        cfg = _get_sampling_config(ctx)
        service = SamplingService(ctx, cfg)
        analysis = await service.analyse_logs(log_dicts)
        step += 1

        await _report(ctx, total, total, "Analysis complete")
        await ctx.info(f"Sampling: log analysis generated ({len(analysis)} chars)")
        return json.dumps(
            {
                "run_id": run_id,
                "logs_analysed": len(log_dicts),
                "ai_analysis": analysis,
            }
        )
