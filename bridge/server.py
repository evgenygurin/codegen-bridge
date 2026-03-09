"""FastMCP server for Codegen AI agent platform.

Hybrid architecture:
- 15 manual core tools with business logic (auto-detect repo_id, response formatting)
- ~21 auto-generated tools from OpenAPI spec via OpenAPIProvider
- 5 resources for monitoring, platform docs + command resources via CommandsProvider
- Agent skills via SkillsDirectoryProvider
- 4 prompts for common workflows

Providers registered during lifespan:
- OpenAPIProvider — auto-generated tools from Codegen REST API
- SkillsDirectoryProvider — agent skills from skills/ directory
- CommandsProvider — slash-command resources from commands/ directory

Tools, resources, and prompts are defined in submodules:
- bridge.tools.agent — agent run management
- bridge.tools.execution — execution context management
- bridge.tools.pr — pull request management
- bridge.tools.setup — organization and repository setup + setup commands
- bridge.tools.integrations — integrations, webhooks, sandbox, Slack connect
- bridge.tools.settings — plugin settings management
- bridge.resources.config — configuration and execution state
- bridge.resources.platform — platform integrations guide and CLI/SDK docs
- bridge.prompts.templates — prompt templates
- bridge.providers — custom and built-in MCP providers
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from bridge.client import CodegenClient
from bridge.context import ContextRegistry
from bridge.helpers.repo_detection import RepoCache
from bridge.middleware import configure_middleware
from bridge.openapi_utils import create_openapi_provider
from bridge.prompts import register_prompts
from bridge.providers import create_all_providers, create_remote_proxy
from bridge.resources import register_resources
from bridge.sampling import SamplingConfig, register_sampling_tools
from bridge.storage import FileStorage
from bridge.tools import (
    register_agent_tools,
    register_execution_tools,
    register_integration_tools,
    register_pr_tools,
    register_session_tools,
    register_settings_tools,
    register_setup_tools,
)
from bridge.transforms import configure_transforms

logger = logging.getLogger("bridge.server")

# ── Lifespan ─────────────────────────────────────────────


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
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

    # Providers are registered in lifespan, so remove previously attached
    # external providers to avoid stale duplicates across Client() sessions.
    # Keep FastMCP's built-in LocalProvider (manual tools/resources/prompts).
    server.providers[:] = [
        provider for provider in server.providers
        if provider is server.local_provider
    ]

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

    # Mount remote Codegen MCP server as a proxy (doubles tool surface)
    try:
        remote_proxy = create_remote_proxy(api_key=api_key)
        if remote_proxy is not None:
            server.mount(remote_proxy, namespace="remote")
            logger.info("Remote Codegen MCP proxy mounted (namespace='remote')")
    except Exception:
        logger.warning("Remote MCP proxy unavailable; local tools only", exc_info=True)

    storage = FileStorage()
    registry = ContextRegistry(storage=storage)
    await registry.setup()
    repo_cache = RepoCache()
    sampling_config = SamplingConfig()
    session_state: dict[str, str] = {}

    logger.info("Codegen Bridge ready")
    try:
        yield {
            "client": client,
            "org_id": org_id,
            "registry": registry,
            "repo_cache": repo_cache,
            "sampling_config": sampling_config,
            "session_state": session_state,
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
register_pr_tools(mcp)
register_setup_tools(mcp)
register_integration_tools(mcp)
register_settings_tools(mcp)
register_session_tools(mcp)
register_resources(mcp)
register_prompts(mcp)
register_sampling_tools(mcp)

# Configure transform chain (namespace, tool transforms, visibility,
# version filter).  Default: passthrough (no transforms applied).
configure_transforms(mcp)

# ── Entry Point ─────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
