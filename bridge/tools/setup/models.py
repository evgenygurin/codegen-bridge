"""Model discovery tool: list available AI models and providers.

Exposes `codegen_list_models` which calls the Codegen REST API to
retrieve all available AI model providers (Anthropic, OpenAI, Google, etc.)
and their model options, plus the organization's default model.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context
from mcp.types import ToolAnnotations

from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.icons import ICON_MODEL


def register_models_tools(mcp: FastMCP) -> None:
    """Register model discovery tools on the given FastMCP server."""

    @mcp.tool(
        tags={"setup"},
        icons=ICON_MODEL,
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def codegen_list_models(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """List available AI models grouped by provider.

        Returns all model providers (e.g. Anthropic, OpenAI, Google, XAI)
        along with each provider's models and the organization's default.
        Useful for choosing a model before creating an agent run.
        """
        await ctx.info("Fetching available models")
        models_resp = await client.list_models()
        providers = [
            {
                "name": p.name,
                "models": [{"label": m.label, "value": m.value} for m in p.models],
            }
            for p in models_resp.providers
        ]
        await ctx.info(
            f"Found {sum(len(p['models']) for p in providers)} models "
            f"across {len(providers)} providers"
        )
        return json.dumps(
            {
                "providers": providers,
                "default_model": models_resp.default_model,
            }
        )
