"""MCP tool definitions that leverage server-side sampling.

Each tool uses ``SamplingService`` to request LLM completions via
``ctx.sample()`` — the actual inference is done by the connected
client or a configured fallback handler.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.annotations import READ_ONLY
from bridge.client import CodegenClient
from bridge.context import ContextRegistry
from bridge.dependencies import CurrentContext, Depends, get_client, get_registry, get_run_service
from bridge.icons import ICON_SAMPLING_ANALYSIS, ICON_SAMPLING_PROMPT, ICON_SAMPLING_SUMMARY
from bridge.sampling.config import SamplingConfig
from bridge.sampling.service import SamplingService
from bridge.services.runs import RunService


def _get_sampling_config(ctx: Context) -> SamplingConfig:
    """Resolve ``SamplingConfig`` from lifespan context, with a safe default."""
    lc = ctx.lifespan_context
    if lc and "sampling_config" in lc:
        cfg: SamplingConfig = lc["sampling_config"]
        return cfg
    return SamplingConfig()


def register_sampling_tools(mcp: FastMCP) -> None:
    """Register all sampling-powered tools on the given FastMCP server."""

    @mcp.tool(tags={"sampling", "monitoring"}, icons=ICON_SAMPLING_SUMMARY, annotations=READ_ONLY)
    async def codegen_summarise_run(
        run_id: int,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service),
        client: CodegenClient = Depends(get_client),
    ) -> str:
        """Generate an AI-powered summary of an agent run.

        Uses server-side LLM sampling to produce a concise, actionable
        summary from the run's status, result, PRs, and parsed logs.

        Args:
            run_id: Agent run ID to summarise.
        """
        await ctx.info(f"Sampling: summarising run {run_id}")

        run_data = await svc.get_run(run_id)

        # Optionally enrich with parsed logs (needs raw AgentLog objects)
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
        except Exception:
            await ctx.warning(f"Could not fetch logs for run {run_id}; summarising without them")

        cfg = _get_sampling_config(ctx)
        service = SamplingService(ctx, cfg)
        summary = await service.summarise_run(run_data)

        await ctx.info(f"Sampling: run {run_id} summary generated ({len(summary)} chars)")
        return json.dumps({"run_id": run_id, "ai_summary": summary})

    @mcp.tool(tags={"sampling", "monitoring"}, icons=ICON_SAMPLING_SUMMARY, annotations=READ_ONLY)
    async def codegen_summarise_execution(
        execution_id: str | None = None,
        ctx: Context = CurrentContext(),
        registry: ContextRegistry = Depends(get_registry),    ) -> str:
        """Generate an AI-powered summary of a full execution plan.

        Summarises all tasks, their statuses, PRs, and key decisions
        into a concise report using server-side LLM sampling.

        Args:
            execution_id: Execution ID. If not given, uses the active execution.
        """
        await ctx.info(f"Sampling: summarising execution {execution_id or 'active'}")

        if execution_id:
            exec_ctx = await registry.get(execution_id)
        else:
            exec_ctx = await registry.get_active()
        if exec_ctx is None:
            return json.dumps({"error": "No execution context found"})

        cfg = _get_sampling_config(ctx)
        service = SamplingService(ctx, cfg)
        summary = await service.summarise_execution(exec_ctx.model_dump_json(indent=2))

        await ctx.info(f"Sampling: execution summary generated ({len(summary)} chars)")
        return json.dumps(
            {
                "execution_id": exec_ctx.id,
                "status": exec_ctx.status,
                "ai_summary": summary,
            }
        )

    @mcp.tool(tags={"sampling", "context"}, icons=ICON_SAMPLING_PROMPT, annotations=READ_ONLY)
    async def codegen_generate_task_prompt(
        goal: str,
        task_description: str,
        tech_stack: list[str] | None = None,
        architecture: str | None = None,
        execution_id: str | None = None,
        ctx: Context = CurrentContext(),
        registry: ContextRegistry = Depends(get_registry),    ) -> str:
        """Use AI to generate a detailed, optimised prompt for a Codegen agent.

        The LLM produces a structured, self-contained prompt based on the
        provided goal, task, and optional context. Much richer than the
        static template in ``build_task_prompt``.

        Args:
            goal: High-level project goal.
            task_description: What this specific task should accomplish.
            tech_stack: Technologies in use (e.g. ["Python", "FastAPI"]).
            architecture: Architecture overview string.
            execution_id: Optional execution ID to pull completed-task context from.
        """
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

        cfg = _get_sampling_config(ctx)
        service = SamplingService(ctx, cfg)
        prompt = await service.generate_task_prompt(
            goal=goal,
            task_description=task_description,
            tech_stack=tech_stack,
            architecture=architecture,
            completed_tasks=completed_tasks,
        )

        await ctx.info(f"Sampling: task prompt generated ({len(prompt)} chars)")
        return json.dumps({"generated_prompt": prompt})

    @mcp.tool(tags={"sampling", "monitoring"}, icons=ICON_SAMPLING_ANALYSIS, annotations=READ_ONLY)
    async def codegen_analyse_run_logs(
        run_id: int,
        limit: int = 50,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service),
    ) -> str:
        """Analyse agent execution logs with AI to identify patterns and issues.

        Fetches logs for the given run and uses LLM sampling to produce
        structured insights: accomplishments, errors, test results, and
        improvement suggestions.

        Args:
            run_id: Agent run ID whose logs to analyse.
            limit: Maximum log entries to analyse (default 50).
        """
        await ctx.info(f"Sampling: analysing logs for run {run_id}")

        logs_data = await svc.get_logs(run_id, limit=limit)
        log_dicts: list[dict[str, Any]] = logs_data["logs"]

        cfg = _get_sampling_config(ctx)
        service = SamplingService(ctx, cfg)
        analysis = await service.analyse_logs(log_dicts)

        await ctx.info(f"Sampling: log analysis generated ({len(analysis)} chars)")
        return json.dumps(
            {
                "run_id": run_id,
                "logs_analysed": len(log_dicts),
                "ai_analysis": analysis,
            }
        )
