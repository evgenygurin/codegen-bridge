"""OAuth and MCP provider management tools.

Provides tools for listing MCP-enabled OAuth providers, checking
OAuth token status, and revoking OAuth tokens.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from mcp.types import ToolAnnotations

from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.elicitation import confirm_action
from bridge.icons import ICON_MCP, ICON_OAUTH


def register_oauth_tools(mcp: FastMCP) -> None:
    """Register OAuth and MCP provider management tools."""

    @mcp.tool(
        tags={"setup"},
        icons=ICON_MCP,
        timeout=30,
        annotations=ToolAnnotations(
            title="Get MCP Providers",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def codegen_get_mcp_providers(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """List available MCP-enabled OAuth providers.

        Returns all providers registered in Codegen with ``is_mcp=True``.
        Use these provider names when checking OAuth token status or
        configuring MCP server integrations.
        """
        await ctx.info("Fetching MCP providers")
        providers = await client.get_mcp_providers()
        await ctx.info(f"Found {len(providers)} MCP providers")
        return json.dumps(
            {
                "providers": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "issuer": p.issuer,
                        "authorization_endpoint": p.authorization_endpoint,
                        "token_endpoint": p.token_endpoint,
                        "default_scopes": p.default_scopes,
                    }
                    for p in providers
                ],
                "total": len(providers),
            }
        )

    @mcp.tool(
        tags={"setup"},
        icons=ICON_OAUTH,
        timeout=30,
        annotations=ToolAnnotations(
            title="Get OAuth Status",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def codegen_get_oauth_status(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Get OAuth token status for the current user and organization.

        Returns a list of connected OAuth providers that have active tokens.
        Use this to check which MCP providers are already authorized before
        prompting the user to connect new ones.
        """
        await ctx.info("Fetching OAuth token status")
        statuses = await client.get_oauth_status()
        await ctx.info(f"Found {len(statuses)} connected providers")
        return json.dumps(
            {
                "connected_providers": [
                    {"provider": s.provider, "active": s.active} for s in statuses
                ],
                "total": len(statuses),
            }
        )

    @mcp.tool(
        tags={"setup", "dangerous"},
        icons=ICON_OAUTH,
        timeout=30,
        annotations=ToolAnnotations(
            title="Revoke OAuth Token",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )
    async def codegen_revoke_oauth(
        provider: str,
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Revoke/disconnect an OAuth token for a specific provider.

        Marks ALL tokens as inactive for the current user and organization.
        This action cannot be undone — the user will need to re-authorize.

        Args:
            provider: Provider name to revoke (e.g. from ``codegen_get_mcp_providers``).
            confirmed: Skip interactive confirmation when True (for programmatic use).
        """
        if not provider:
            raise ToolError("provider is required")

        if not confirmed:
            user_confirmed = await confirm_action(
                ctx,
                f"Revoke OAuth token for provider '{provider}'? "
                "All active tokens will be deactivated. This cannot be undone.",
            )
            if not user_confirmed:
                return json.dumps(
                    {
                        "action": "cancelled",
                        "reason": "User declined to revoke OAuth token",
                    }
                )

        await ctx.warning(f"Revoking OAuth token for provider: {provider}")
        await client.revoke_oauth(provider)
        await ctx.info(f"OAuth token revoked for provider: {provider}")
        return json.dumps(
            {
                "action": "revoked",
                "provider": provider,
            }
        )
