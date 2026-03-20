"""CI check-suite settings tools.

Provides tools for reading and updating CI check-suite settings
for repositories, including retry counts, ignored checks,
custom prompts, and high-priority app configuration.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context

from bridge.annotations import MUTATES, READ_ONLY
from bridge.client import CodegenClient, ServerError
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.icons import ICON_CHECK_SUITE


def register_check_suite_tools(mcp: FastMCP) -> None:
    """Register CI check-suite settings tools (get, update)."""

    @mcp.tool(tags={"setup"}, icons=ICON_CHECK_SUITE, timeout=30, annotations=READ_ONLY)
    async def codegen_get_check_suite_settings(
        repo_id: int,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),    ) -> str: # type: ignore[arg-type]
        """Get CI check-suite settings for a repository.

        Returns retry counts, ignored checks, custom prompts, high-priority
        apps, and available check suite names.

        Args:
            repo_id: Repository ID to get check suite settings for.
        """
        await ctx.info(f"Fetching check suite settings: repo_id={repo_id}")
        try:
            settings = await client.get_check_suite_settings(repo_id)
        except ServerError as exc:
            await ctx.warning(
                f"Check suite settings API returned server error: {exc.status_code}"
            )
            return json.dumps({
                "error": "server_error",
                "status_code": exc.status_code,
                "repo_id": repo_id,
                "detail": exc.detail or "The Codegen API returned an internal error",
                "hint": (
                    "This endpoint may not be available for this repository. "
                    "Verify repo_id is correct and check-suite feature is enabled."
                ),
            })
        await ctx.info(
            f"Check suite settings retrieved: "
            f"{len(settings.ignored_checks)} ignored checks, "
            f"retry_count={settings.check_retry_count}"
        )
        return json.dumps(
            {
                "check_retry_count": settings.check_retry_count,
                "ignored_checks": settings.ignored_checks,
                "check_retry_counts": settings.check_retry_counts,
                "custom_prompts": settings.custom_prompts,
                "high_priority_apps": settings.high_priority_apps,
                "available_check_suite_names": settings.available_check_suite_names,
            }
        )

    @mcp.tool(tags={"setup"}, icons=ICON_CHECK_SUITE, timeout=30, annotations=MUTATES)
    async def codegen_update_check_suite_settings(
        repo_id: int,
        check_retry_count: int | None = None,
        ignored_checks: list[str] | None = None,
        check_retry_counts: dict[str, int] | None = None,
        custom_prompts: dict[str, str] | None = None,
        high_priority_apps: list[str] | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),    ) -> str: # type: ignore[arg-type]
        """Update CI check-suite settings for a repository.

        Only the fields you provide will be updated; omitted fields
        are left unchanged.

        Args:
            repo_id: Repository ID to update settings for.
            check_retry_count: Global retry count for failed checks (0-10).
            ignored_checks: List of check names to ignore.
            check_retry_counts: Per-check retry counts (check_name -> count).
            custom_prompts: Per-check custom prompts (check_name -> prompt).
            high_priority_apps: Apps whose checks are treated as high priority.
        """
        body: dict[str, object] = {}
        if check_retry_count is not None:
            body["check_retry_count"] = check_retry_count
        if ignored_checks is not None:
            body["ignored_checks"] = ignored_checks
        if check_retry_counts is not None:
            body["check_retry_counts"] = check_retry_counts
        if custom_prompts is not None:
            body["custom_prompts"] = custom_prompts
        if high_priority_apps is not None:
            body["high_priority_apps"] = high_priority_apps

        if not body:
            raise ToolError("At least one setting field must be provided")

        await ctx.info(f"Updating check suite settings: repo_id={repo_id}, fields={list(body)}")
        try:
            result = await client.update_check_suite_settings(repo_id, body)
        except ServerError as exc:
            await ctx.warning(
                f"Check suite update API returned server error: {exc.status_code}"
            )
            return json.dumps({
                "error": "server_error",
                "status_code": exc.status_code,
                "repo_id": repo_id,
                "detail": exc.detail or "The Codegen API returned an internal error",
                "hint": (
                    "This endpoint may not be available for this repository. "
                    "Verify repo_id is correct and check-suite feature is enabled."
                ),
            })
        await ctx.info("Check suite settings updated")
        return json.dumps({"status": "updated", "result": result})
