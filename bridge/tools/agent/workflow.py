"""Workflow composition tools: create-and-monitor.

High-level tool that combines run creation with an automatic
polling loop.  Uses ``RunService`` (not tool functions) so that
polling reads are side-effect-free and rate-budget-controlled.
"""

from __future__ import annotations

import asyncio
import json
from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context

from bridge.annotations import CREATES
from bridge.dependencies import CurrentContext, Depends, get_run_service
from bridge.elicitation import confirm_action, select_choice
from bridge.icons import ICON_MONITOR
from bridge.services.runs import RunService
from bridge.tools.agent._progress import MONITOR_TASK, report

# Terminal statuses that end the polling loop
_TERMINAL = frozenset({"completed", "failed", "error"})


def register_workflow_tools(mcp: FastMCP) -> None:
    """Register workflow composition tools on the given FastMCP server."""

    @mcp.tool(
        tags={"execution", "workflow"},
        icons=ICON_MONITOR,
        task=MONITOR_TASK,
        annotations=CREATES,
    )
    async def codegen_create_and_monitor(
        prompt: str,
        repo_id: int | None = None,
        model: str | None = None,
        agent_type: Literal["codegen", "claude_code"] = "claude_code",
        max_polls: int = 60,
        poll_interval: float = 10.0,
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service),
    ) -> str:
        """Create an agent run and poll until completion.

        Combines ``codegen_create_run`` + ``codegen_get_run`` into a
        single fire-and-wait workflow.  Progress is reported at each
        poll so the client can show status updates.

        Polling uses ``RunService.get_run()`` (pure read) — no
        execution-context side effects during the loop.  Rate budget
        in ``CodegenClient`` prevents API exhaustion.

        Args:
            prompt: Task description for the agent.
            repo_id: Repository ID (auto-detected if not provided).
            model: LLM model to use (None = org default or interactive).
            agent_type: Agent type — "codegen" or "claude_code".
            max_polls: Maximum number of status polls before timeout.
            poll_interval: Base seconds between polls (with backoff).
            confirmed: Skip interactive confirmations.
        """
        # ── Step 1: Detect repo ───────────────────────────────
        await report(ctx, 0, max_polls + 2, "Detecting repository")

        if repo_id is None:
            repo_id = await svc.detect_repo()
            if repo_id is None:
                await ctx.error("Auto-detect repository failed; no repo_id provided")
                raise ToolError(
                    "Could not auto-detect repository. "
                    "Provide repo_id explicitly or run from a git repository "
                    "that is registered in your Codegen organization."
                )

        # ── Elicitation ───────────────────────────────────────
        if model is None and not confirmed:
            available = ["claude-3-5-sonnet", "claude-3-5-haiku", "gpt-4o", "o3"]
            selected = await select_choice(
                ctx,
                "Choose a model for this agent run "
                "(or decline to use the organization default):",
                available,
            )
            if selected is not None:
                model = selected

        if not confirmed:
            ok = await confirm_action(
                ctx,
                f"Create and monitor agent run on repo_id={repo_id} "
                f"with model={model or 'org default'}?",
            )
            if not ok:
                return json.dumps(
                    {"action": "cancelled", "reason": "User declined"}
                )

        # ── Step 2: Create run ────────────────────────────────
        await report(ctx, 1, max_polls + 2, "Creating agent run")

        result = await svc.create_run(
            prompt,
            repo_id=repo_id,
            model=model,
            agent_type=agent_type,
        )
        run_id: int = result["id"]
        await ctx.info(f"Agent run created: id={run_id}")

        # ── Step 3: Poll loop ─────────────────────────────────
        last_data = result
        for i in range(max_polls):
            # Exponential backoff: doubles every 10 polls, capped at 4x
            delay = poll_interval * min(2 ** (i // 10), 4)
            await asyncio.sleep(delay)

            data = await svc.get_run(run_id)
            last_data = data
            status = data.get("status", "unknown")

            await report(
                ctx,
                i + 2,  # offset by 2 (detect + create steps)
                max_polls + 2,
                f"Poll {i + 1}/{max_polls}: {status}",
            )

            if status in _TERMINAL:
                data["polls"] = i + 1
                return json.dumps(data)

        # ── Timeout ───────────────────────────────────────────
        return json.dumps({
            "timeout": True,
            "run_id": run_id,
            "last_status": last_data.get("status", "unknown"),
            "polls": max_polls,
        })
