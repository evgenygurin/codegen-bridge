"""Organization and repository management tools.

Provides tools for listing organizations, fetching organization settings,
listing repositories, and generating setup commands for repositories.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context


from bridge.annotations import CREATES, READ_ONLY
from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.helpers.pagination import (
    DEFAULT_PAGE_SIZE,
    build_paginated_response,
    cursor_to_offset,
)
from bridge.icons import ICON_ORG, ICON_ORG_SETTINGS, ICON_REPO, ICON_SETUP_CMD


def register_organization_tools(mcp: FastMCP) -> None:
    """Register organization and repository management tools."""

    @mcp.tool(tags={"setup"}, icons=ICON_ORG, timeout=30, annotations=READ_ONLY)
    async def codegen_list_orgs(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),    ) -> str: # type: ignore[arg-type]
        """List Codegen organizations the authenticated user belongs to."""
        await ctx.info("Listing organizations")
        page = await client.list_orgs()
        await ctx.info(f"Found {len(page.items)} organizations")
        return json.dumps(
            {
                "organizations": [{"id": org.id, "name": org.name} for org in page.items],
            }
        )

    @mcp.tool(tags={"setup"}, icons=ICON_ORG_SETTINGS, timeout=30, annotations=READ_ONLY)
    async def codegen_get_organization_settings(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),    ) -> str: # type: ignore[arg-type]
        """Get organization feature-flag settings.

        Returns the current feature flags for the configured organization,
        such as whether PR creation and rules detection are enabled.
        """
        await ctx.info("Fetching organization settings")
        settings = await client.get_organization_settings()
        await ctx.info(
            f"Organization settings: pr_creation={settings.enable_pr_creation}, "
            f"rules_detection={settings.enable_rules_detection}"
        )
        return json.dumps(
            {
                "enable_pr_creation": settings.enable_pr_creation,
                "enable_rules_detection": settings.enable_rules_detection,
            }
        )

    @mcp.tool(tags={"setup"}, icons=ICON_REPO, timeout=30, annotations=READ_ONLY)
    async def codegen_list_repos(
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),    ) -> str: # type: ignore[arg-type]
        """List repositories in the configured Codegen organization.

        Supports cursor-based pagination for large repository lists.

        Args:
            limit: Maximum repos per page (default 20).
            cursor: Opaque cursor from a previous response's ``next_cursor``
                field.  Omit or pass ``null`` for the first page.
        """
        offset = cursor_to_offset(cursor)
        await ctx.info(f"Listing repos: limit={limit}, offset={offset}")
        page = await client.list_repos(skip=offset, limit=limit)
        await ctx.info(f"Listed {len(page.items)} of {page.total} repos")
        return json.dumps(
            build_paginated_response(
                items=[
                    {
                        "id": r.id,
                        "name": r.name,
                        "full_name": r.full_name,
                        "language": r.language,
                        "setup_status": r.setup_status,
                    }
                    for r in page.items
                ],
                total=page.total,
                offset=offset,
                page_size=limit,
                items_key="repos",
            )
        )

    @mcp.tool(tags={"setup", "creates-agent-run"}, icons=ICON_SETUP_CMD, timeout=60, annotations=CREATES)
    async def codegen_generate_setup_commands(
        repo_id: int,
        prompt: str | None = None,
        trigger_source: str = "setup-commands",
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),    ) -> str: # type: ignore[arg-type]
        """Generate setup commands for a repository.

        Creates an agent that analyzes the repository structure and generates
        appropriate setup commands. The generation runs asynchronously —
        use the returned agent_run_id to check results.

        Args:
            repo_id: Repository ID to generate setup commands for.
            prompt: Optional custom prompt to guide generation.
            trigger_source: Source trigger identifier (default "setup-commands").
        """
        await ctx.info(f"Generating setup commands: repo_id={repo_id}")
        result = await client.generate_setup_commands(
            repo_id, prompt=prompt, trigger_source=trigger_source
        )
        await ctx.info(
            f"Setup commands generation started: agent_run_id={result.agent_run_id}, "
            f"status={result.status}"
        )
        return json.dumps(
            {
                "agent_run_id": result.agent_run_id,
                "status": result.status,
                "url": result.url,
            }
        )
