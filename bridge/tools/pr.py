"""Pull request management tools: edit PR state.

Two flavours are exposed:

* ``codegen_edit_pr`` — RESTful endpoint requiring ``repo_id`` and ``pr_id``.
* ``codegen_edit_pr_simple`` — simplified endpoint requiring only ``pr_id``.

Both tools are tagged ``dangerous`` because they mutate external state
(closing / re-opening a PR).
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context


from bridge.annotations import DESTRUCTIVE
from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.elicitation import confirm_action
from bridge.icons import ICON_PR_EDIT
from bridge.models import PRState


def register_pr_tools(mcp: FastMCP) -> None:
    """Register all pull-request management tools on the given FastMCP server."""

    @mcp.tool(tags={"pull-requests", "dangerous"}, icons=ICON_PR_EDIT, timeout=30, annotations=DESTRUCTIVE)
    async def codegen_edit_pr(
        repo_id: int,
        pr_id: int,
        state: PRState,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),    ) -> str: # type: ignore[arg-type]
        """Edit pull request properties (RESTful endpoint).

        Update the state of a pull request (open, closed, draft, ready_for_review).
        This endpoint requires both ``repo_id`` and ``pr_id`` for RESTful
        compliance.  The requesting user must have write permissions to the
        repository.

        Args:
            repo_id: Repository ID containing the pull request.
            pr_id: Pull request ID to edit.
            state: New state — "open", "closed", "draft", or "ready_for_review".
        """
        confirmed = await confirm_action(ctx, f"Change PR #{pr_id} state to '{state}'?")
        if not confirmed:
            return json.dumps({"cancelled": True, "reason": "User declined"})
        await ctx.info(f"Editing PR: repo_id={repo_id}, pr_id={pr_id}, state={state}")
        result = await client.edit_pr(repo_id=repo_id, pr_id=pr_id, state=state)
        await ctx.info(f"PR edited: success={result.success}, state={result.state}")

        response: dict[str, object] = {"success": result.success}
        if result.url is not None:
            response["url"] = result.url
        if result.number is not None:
            response["number"] = result.number
        if result.title is not None:
            response["title"] = result.title
        if result.state is not None:
            response["state"] = result.state
        if result.error is not None:
            response["error"] = result.error
        return json.dumps(response)

    @mcp.tool(tags={"pull-requests", "dangerous"}, icons=ICON_PR_EDIT, timeout=30, annotations=DESTRUCTIVE)
    async def codegen_edit_pr_simple(
        pr_id: int,
        state: PRState,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),    ) -> str: # type: ignore[arg-type]
        """Edit pull request properties (simple endpoint).

        Update the state of a pull request (open, closed, draft, ready_for_review).
        This endpoint only requires the PR ID, not the repo ID.
        The requesting user must have write permissions to the repository.

        Args:
            pr_id: Pull request ID to edit.
            state: New state — "open", "closed", "draft", or "ready_for_review".
        """
        confirmed = await confirm_action(ctx, f"Change PR #{pr_id} state to '{state}'?")
        if not confirmed:
            return json.dumps({"cancelled": True, "reason": "User declined"})
        await ctx.info(f"Editing PR (simple): pr_id={pr_id}, state={state}")
        result = await client.edit_pr_simple(pr_id=pr_id, state=state)
        await ctx.info(f"PR edited: success={result.success}, state={result.state}")

        response: dict[str, object] = {"success": result.success}
        if result.url is not None:
            response["url"] = result.url
        if result.number is not None:
            response["number"] = result.number
        if result.title is not None:
            response["title"] = result.title
        if result.state is not None:
            response["state"] = result.state
        if result.error is not None:
            response["error"] = result.error
        return json.dumps(response)
