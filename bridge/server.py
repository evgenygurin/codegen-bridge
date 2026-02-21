"""FastMCP server for Codegen AI agent platform.

Hybrid architecture:
- 8 manual core tools with business logic (auto-detect repo_id, response formatting)
- ~21 auto-generated tools from OpenAPI spec via OpenAPIProvider
- 3 resources for monitoring + command resources via CommandsProvider
- Agent skills via SkillsDirectoryProvider
- 4 prompts for common workflows

Providers registered during lifespan:
- OpenAPIProvider — auto-generated tools from Codegen REST API
- SkillsDirectoryProvider — agent skills from skills/ directory
- CommandsProvider — slash-command resources from commands/ directory

Tools, resources, and prompts are defined in submodules:
- bridge.tools.agent — agent run management
- bridge.tools.execution — execution context management
- bridge.tools.setup — organization and repository setup
- bridge.resources.config — configuration and execution state
- bridge.prompts.templates — prompt templates
- bridge.providers — custom and built-in MCP providers
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
from bridge.providers import create_all_providers
from bridge.resources import register_resources
from bridge.sampling import SamplingConfig, register_sampling_tools
from bridge.tools import register_agent_tools, register_execution_tools, register_setup_tools
from bridge.transforms import configure_transforms

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

    # Add filesystem-based providers (skills + commands)
    for fs_provider in create_all_providers():
        try:
            server.add_provider(fs_provider)
            logger.info("Registered provider: %s", type(fs_provider).__name__)
        except Exception:
            logger.warning(
                "Failed to register provider: %s",
                type(fs_provider).__name__,
                exc_info=True,
            )

    registry = ContextRegistry()
    repo_cache = RepoCache()
    sampling_config = SamplingConfig()

    logger.info("Codegen Bridge ready")
    try:
        yield {
            "client": client,
            "org_id": org_id,
            "registry": registry,
            "repo_cache": repo_cache,
            "sampling_config": sampling_config,
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

# Configure middleware stack (error handling, ping, logging, telemetry,
# timing, rate limiting, caching, response limiting)
configure_middleware(mcp)

# Register tools, resources, and prompts from submodules
register_agent_tools(mcp)
register_execution_tools(mcp)
register_setup_tools(mcp)
register_resources(mcp)
register_prompts(mcp)
register_sampling_tools(mcp)

# Configure transform chain (namespace, tool transforms, visibility,
# version filter).  Default: passthrough (no transforms applied).
configure_transforms(mcp)

# ── Entry Point ─────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
