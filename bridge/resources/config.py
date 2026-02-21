"""Configuration and execution state resources."""

from __future__ import annotations

import json
import os

from fastmcp import FastMCP

from bridge.context import ContextRegistry
from bridge.dependencies import Depends, get_registry


def register_resources(mcp: FastMCP) -> None:
    """Register all MCP resources on the given FastMCP server."""

    @mcp.resource("codegen://config")
    def get_config() -> str:
        """Current Codegen Bridge configuration and status."""
        org_id = os.environ.get("CODEGEN_ORG_ID", "not set")
        has_key = bool(os.environ.get("CODEGEN_API_KEY"))
        return json.dumps(
            {
                "org_id": org_id,
                "api_base": "https://api.codegen.com/v1",
                "has_api_key": has_key,
            }
        )

    @mcp.resource("codegen://execution/current")
    async def get_current_execution(
        registry: ContextRegistry = Depends(get_registry),
    ) -> str:
        """Current execution progress — plan status, task list, active run."""
        exec_ctx = registry.get_active()
        if exec_ctx is None:
            return json.dumps({"status": "no_active_execution"})
        return exec_ctx.model_dump_json(indent=2)
