"""Agent run moderation tools: ban, unban, remove-from-pr.

Tools for managing CI/CD check-suite bans on PRs associated with
agent runs. Banning prevents future check-suite events from being
processed and stops all current agents for the PR.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.elicitation import confirm_action
from bridge.icons import ICON_BAN, ICON_REMOVE_FROM_PR, ICON_UNBAN


def register_moderation_tools(mcp: FastMCP) -> None:
    """Register agent run moderation tools (ban, unban, remove-from-pr)."""

    # ── Ban ───────────────────────────────────────────────

    @mcp.tool(tags={"execution", "dangerous"}, icons=ICON_BAN)
    async def codegen_ban_run(
        run_id: int,
        before_card_order_id: str | None = None,
        after_card_order_id: str | None = None,
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client)
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
        client: CodegenClient = Depends(get_client)
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
        client: CodegenClient = Depends(get_client)
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
