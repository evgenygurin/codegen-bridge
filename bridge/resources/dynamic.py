"""Dynamic resource templates for Codegen Bridge.

Provides parameterized MCP resources that map to Codegen API endpoints:

- ``codegen://models``              — available AI models and providers

Note: ``codegen://runs/{run_id}`` and ``codegen://runs/{run_id}/logs``
are provided by ``bridge/resources/templates.py`` via the service layer.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.client import CodegenAPIError, CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.icons import ICON_MODEL


def register_dynamic_resources(mcp: FastMCP) -> None:
    """Register dynamic (parameterized) resources on the given FastMCP server."""

    @mcp.resource("codegen://models", icons=ICON_MODEL)
    async def get_models_resource(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """List all available AI model providers and their models.

        URI: ``codegen://models``
        """
        try:
            models_resp = await client.list_models()
            return json.dumps(models_resp.model_dump(mode="json"), indent=2)
        except CodegenAPIError as e:
            return json.dumps({"error": str(e), "hint": "Check CODEGEN_API_KEY"})
