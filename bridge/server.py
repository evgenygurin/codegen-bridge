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

import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from bridge.client import CodegenClient
from bridge.context import ContextRegistry
from bridge.helpers.repo_detection import RepoCache
from bridge.middleware import configure_middleware
from bridge.openapi_utils import create_openapi_provider
from bridge.prompts import register_prompts
from bridge.resources import register_resources
from bridge.tools import register_agent_tools, register_execution_tools, register_setup_tools

logger = logging.getLogger("bridge.server")

# ── Lifespan ─────────────────────────────────────────────


@asynccontextmanager
async def _lifespan(server: FastMCP):
    """Manage lifecycle of HTTP clients and OpenAPI provider.

    Yields a dict that becomes ``ctx.lifespan_context`` in tools/resources.
    The DI providers in ``bridge.dependencies`` read from this dict.
    """
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

    logger.info("Starting Codegen Bridge: org_id=%s", org_id)
    client = CodegenClient(api_key=api_key, org_id=org_id)

    http_client = httpx.AsyncClient(
        base_url="https://api.codegen.com",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )

    # Add OpenAPI provider for auto-generated tools
    try:
        provider = create_openapi_provider(http_client, org_id)
        server.add_provider(provider)
    except Exception:
        logger.warning("OpenAPI provider unavailable; manual tools only", exc_info=True)

    registry = ContextRegistry()
    repo_cache = RepoCache()

    logger.info("Codegen Bridge ready")
    try:
        yield {
            "client": client,
            "org_id": org_id,
            "registry": registry,
            "repo_cache": repo_cache,
        }
    finally:
        logger.info("Shutting down Codegen Bridge")
        await client.close()
        await http_client.aclose()


# ── Server ───────────────────────────────────────────────

mcp = FastMCP(
    "Codegen Bridge",
    instructions="Tools for delegating tasks to Codegen AI agents. "
    "Create agent runs, monitor progress, view logs, and resume blocked runs.",
    lifespan=_lifespan,
)

# Configure middleware stack (error handling, ping, logging, timing,
# rate limiting, caching, response limiting)
configure_middleware(mcp)

# Register tools, resources, and prompts from submodules
register_agent_tools(mcp)
register_execution_tools(mcp)
register_setup_tools(mcp)
register_resources(mcp)
register_prompts(mcp)

# ── Entry Point ─────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
