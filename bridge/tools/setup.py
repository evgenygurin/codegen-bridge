"""Organization and repository setup tools."""

from __future__ import annotations

import json

from fastmcp import FastMCP

from bridge.client import CodegenClient
from bridge.dependencies import Depends, get_client


def register_setup_tools(mcp: FastMCP) -> None:
    """Register all setup tools on the given FastMCP server."""

    @mcp.tool(tags={"setup"})
    async def codegen_list_orgs(
        client: CodegenClient = Depends(get_client),
    ) -> str:
        """List Codegen organizations the authenticated user belongs to."""
        page = await client.list_orgs()
        return json.dumps(
            {
                "organizations": [{"id": org.id, "name": org.name} for org in page.items],
            }
        )

    @mcp.tool(tags={"setup"})
    async def codegen_list_repos(
        limit: int = 50,
        client: CodegenClient = Depends(get_client),
    ) -> str:
        """List repositories in the configured Codegen organization.

        Args:
            limit: Maximum repos to return (default 50).
        """
        page = await client.list_repos(limit=limit)
        return json.dumps(
            {
                "total": page.total,
                "repos": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "full_name": r.full_name,
                        "language": r.language,
                        "setup_status": r.setup_status,
                    }
                    for r in page.items
                ],
            }
        )
