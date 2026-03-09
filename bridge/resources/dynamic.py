"""Dynamic resource templates for Codegen Bridge.

Provides parameterized MCP resources that map to Codegen API endpoints:

- ``codegen://runs/{run_id}``       — single agent run details
- ``codegen://runs/{run_id}/logs``  — agent run log entries
- ``codegen://models``              — available AI models and providers
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.icons import ICON_GET_RUN, ICON_LOGS, ICON_MODEL


def register_dynamic_resources(mcp: FastMCP) -> None:
    """Register dynamic (parameterized) resources on the given FastMCP server."""

    @mcp.resource("codegen://runs/{run_id}", icons=ICON_GET_RUN)
    async def get_run_resource(
        run_id: int,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Fetch a single agent run by ID.

        URI pattern: ``codegen://runs/{run_id}``
        """
        run = await client.get_run(run_id)
        return json.dumps(run.model_dump(mode="json"), indent=2)

    @mcp.resource("codegen://runs/{run_id}/logs", icons=ICON_LOGS)
    async def get_run_logs_resource(
        run_id: int,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Fetch log entries for an agent run.

        URI pattern: ``codegen://runs/{run_id}/logs``
        """
        data = await client.get_logs(run_id)
        return json.dumps(data.model_dump(mode="json"), indent=2)

    @mcp.resource("codegen://models", icons=ICON_MODEL)
    async def get_models_resource(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """List all available AI model providers and their models.

        URI: ``codegen://models``
        """
        models_resp = await client.list_models()
        return json.dumps(models_resp.model_dump(mode="json"), indent=2)
