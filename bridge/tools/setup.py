"""Organization and repository setup tools."""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.helpers.pagination import (
    DEFAULT_PAGE_SIZE,
    build_paginated_response,
    cursor_to_offset,
)


def register_setup_tools(mcp: FastMCP) -> None:
    """Register all setup tools on the given FastMCP server."""

    @mcp.tool(tags={"setup"})
    async def codegen_list_orgs(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),
    ) -> str:
        """List Codegen organizations the authenticated user belongs to."""
        await ctx.info("Listing organizations")
        page = await client.list_orgs()
        await ctx.info(f"Found {len(page.items)} organizations")
        return json.dumps(
            {
                "organizations": [{"id": org.id, "name": org.name} for org in page.items],
            }
        )

    @mcp.tool(tags={"setup"})
    async def codegen_list_repos(
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),
    ) -> str:
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
