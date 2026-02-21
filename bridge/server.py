"""FastMCP server for Codegen AI agent platform.

Hybrid architecture:
- 8 manual core tools with business logic (auto-detect repo_id, response formatting)
- ~13 auto-generated tools from OpenAPI spec via OpenAPIProvider
- 3 resources for monitoring
- 4 prompts for common workflows

Tools, resources, and prompts are defined in submodules:
- bridge.tools.agent — agent run management
- bridge.tools.execution — execution context management
- bridge.tools.setup — organization and repository setup
- bridge.resources.config — configuration and execution state
- bridge.prompts.templates — prompt templates
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from bridge.client import CodegenClient
from bridge.context import ContextRegistry
from bridge.dependencies import set_global_client, set_global_registry
from bridge.openapi_utils import create_openapi_provider
from bridge.prompts import register_prompts
from bridge.resources import register_resources
from bridge.tools import register_agent_tools, register_execution_tools, register_setup_tools

# ── Lifespan ─────────────────────────────────────────────

_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def _lifespan(server: FastMCP):
    """Manage lifecycle of HTTP clients and OpenAPI provider."""
    global _http_client

    api_key = os.environ.get("CODEGEN_API_KEY", "")
    org_id_str = os.environ.get("CODEGEN_ORG_ID", "0")
    try:
        org_id = int(org_id_str)
    except ValueError:
        raise ToolError(
            "CODEGEN_ORG_ID must be a number. Set it in your environment or plugin config."
        ) from None
    if not api_key:
        raise ToolError("CODEGEN_API_KEY not set.")
    if not org_id:
        raise ToolError("CODEGEN_ORG_ID not set.")

    client = CodegenClient(api_key=api_key, org_id=org_id)
    set_global_client(client)

    _http_client = httpx.AsyncClient(
        base_url="https://api.codegen.com",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )

    # Add OpenAPI provider for auto-generated tools
    try:
        provider = create_openapi_provider(_http_client, org_id)
        server.add_provider(provider)
    except Exception:
        pass  # OpenAPI provider is optional; manual tools always work

    registry = ContextRegistry()
    set_global_registry(registry)

    try:
        yield {"client": client, "org_id": org_id, "registry": registry}
    finally:
        await client.close()
        set_global_client(None)
        if _http_client is not None:
            await _http_client.aclose()
            _http_client = None
        set_global_registry(None)


# ── Server ───────────────────────────────────────────────

mcp = FastMCP(
    "Codegen Bridge",
    instructions="Tools for delegating tasks to Codegen AI agents. "
    "Create agent runs, monitor progress, view logs, and resume blocked runs.",
    lifespan=_lifespan,
)

# Register tools, resources, and prompts from submodules
register_agent_tools(mcp)
register_execution_tools(mcp)
register_setup_tools(mcp)
register_resources(mcp)
register_prompts(mcp)

# ── Entry Point ─────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
