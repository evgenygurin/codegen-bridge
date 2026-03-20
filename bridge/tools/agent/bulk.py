"""Bulk agent run operations.

Create multiple agent runs from a list of tasks in a single batch
call, with per-task progress reporting.
"""

from __future__ import annotations

import json

import httpx
from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.annotations import CREATES
from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.icons import ICON_RUN
from bridge.tools.agent._progress import report


def register_bulk_tools(mcp: FastMCP) -> None:
    """Register bulk agent run tools on the given FastMCP server."""

    @mcp.tool(tags={"agent", "bulk"}, icons=ICON_RUN, timeout=120, annotations=CREATES)
    async def codegen_bulk_create_runs(
        tasks: list[dict[str, str]],
        repo_id: int | None = None,
        model: str | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Create multiple agent runs from a list of tasks (batch delegation).

        Each task dict must contain a ``prompt`` key describing the task.
        Tasks may optionally override ``repo_id`` and ``model`` at the
        per-task level; top-level values serve as defaults.

        Progress is reported after each run is created so the client can
        track batch progress.

        Args:
            tasks: List of task dicts, each with a ``prompt`` key and
                optional ``repo_id`` (int as string) and ``model`` overrides.
            repo_id: Default repository ID for all tasks (per-task overrides win).
            model: Default LLM model for all tasks (per-task overrides win).
        """
        if not tasks:
            return json.dumps({"error": "No tasks provided", "runs": []})

        total = len(tasks)
        await ctx.info(f"Bulk creating {total} agent runs")
        await report(ctx, 0, total, f"Starting batch: {total} tasks")

        results: list[dict[str, object]] = []
        created = 0
        failed = 0

        for i, task in enumerate(tasks):
            prompt = task.get("prompt", "")
            if not prompt:
                results.append({"index": i, "error": "Missing prompt"})
                failed += 1
                await report(ctx, i + 1, total, f"Task {i + 1}/{total}: skipped (no prompt)")
                continue

            # Per-task overrides fall back to batch-level defaults
            task_repo_id = task.get("repo_id")
            effective_repo_id = int(task_repo_id) if task_repo_id is not None else repo_id
            effective_model = task.get("model") or model

            try:
                run = await client.create_run(
                    prompt,
                    repo_id=effective_repo_id,
                    model=effective_model,
                )
                results.append(
                    {
                        "index": i,
                        "id": run.id,
                        "status": run.status,
                        "web_url": run.web_url,
                    }
                )
                created += 1
            except httpx.HTTPStatusError as exc:
                results.append({"index": i, "error": str(exc)})
                failed += 1

            await report(ctx, i + 1, total, f"Task {i + 1}/{total}: done")

        await ctx.info(f"Bulk create complete: {created} created, {failed} failed")
        return json.dumps(
            {
                "total": total,
                "created": created,
                "failed": failed,
                "runs": results,
            }
        )
