"""Agent run moderation tools: ban, unban, remove-from-pr.

Tools for managing CI/CD check-suite bans on PRs associated with
agent runs.  Business logic lives in ``RunService``; these tools
handle elicitation, MCP logging, and JSON serialisation.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context


from bridge.annotations import DESTRUCTIVE, MUTATES
from bridge.dependencies import CurrentContext, Depends, get_run_service
from bridge.elicitation import confirm_action
from bridge.icons import ICON_BAN, ICON_REMOVE_FROM_PR, ICON_UNBAN
from bridge.services.runs import RunService


def register_moderation_tools(mcp: FastMCP) -> None:
    """Register agent run moderation tools (ban, unban, remove-from-pr)."""

    # ── Ban ───────────────────────────────────────────────

    @mcp.tool(tags={"execution", "dangerous"}, icons=ICON_BAN, timeout=30, annotations=DESTRUCTIVE)
    async def codegen_ban_run(
        run_id: int,
        before_card_order_id: str | None = None,
        after_card_order_id: str | None = None,
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service),    ) -> str: # type: ignore[arg-type]
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
        result = await svc.ban_run(
            run_id,
            before_card_order_id=before_card_order_id,
            after_card_order_id=after_card_order_id,
        )
        await ctx.info(f"Checks banned for run: id={run_id}")
        return json.dumps(result)

    # ── Unban ─────────────────────────────────────────────

    @mcp.tool(tags={"execution"}, icons=ICON_UNBAN, timeout=30, annotations=MUTATES)
    async def codegen_unban_run(
        run_id: int,
        before_card_order_id: str | None = None,
        after_card_order_id: str | None = None,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service),    ) -> str: # type: ignore[arg-type]
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
        result = await svc.unban_run(
            run_id,
            before_card_order_id=before_card_order_id,
            after_card_order_id=after_card_order_id,
        )
        await ctx.info(f"Checks unbanned for run: id={run_id}")
        return json.dumps(result)

    # ── Remove from PR ────────────────────────────────────

    @mcp.tool(tags={"execution", "dangerous"}, icons=ICON_REMOVE_FROM_PR, timeout=30, annotations=DESTRUCTIVE)
    async def codegen_remove_from_pr(
        run_id: int,
        before_card_order_id: str | None = None,
        after_card_order_id: str | None = None,
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        svc: RunService = Depends(get_run_service),    ) -> str: # type: ignore[arg-type]
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
        result = await svc.remove_from_pr(
            run_id,
            before_card_order_id=before_card_order_id,
            after_card_order_id=after_card_order_id,
        )
        await ctx.info(f"Codegen removed from PR for run: id={run_id}")
        return json.dumps(result)
