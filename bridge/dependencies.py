"""Dependency injection helpers for MCP tools.

Provides access to CodegenClient and ContextRegistry from either
the FastMCP lifespan context or a global/lazy fallback.
"""

from __future__ import annotations

import os

from fastmcp import Context
from fastmcp.exceptions import ToolError

from bridge.client import CodegenClient
from bridge.context import ContextRegistry

# Global fallbacks (set during lifespan)
_client: CodegenClient | None = None
_registry: ContextRegistry | None = None


def set_global_client(client: CodegenClient | None) -> None:
    """Set the global client instance (called from lifespan)."""
    global _client
    _client = client


def set_global_registry(registry: ContextRegistry | None) -> None:
    """Set the global registry instance (called from lifespan)."""
    global _registry
    _registry = registry


def get_client(ctx: Context | None = None) -> CodegenClient:
    """Get Codegen client from lifespan context or global fallback."""
    if ctx is not None:
        lc = ctx.lifespan_context
        if lc and "client" in lc:
            return lc["client"]
    if _client is not None:
        return _client
    # Fallback: lazy init (for testing without lifespan)
    api_key = os.environ.get("CODEGEN_API_KEY", "")
    org_id_str = os.environ.get("CODEGEN_ORG_ID", "0")
    try:
        org_id = int(org_id_str)
    except ValueError:
        raise ToolError("CODEGEN_ORG_ID must be a number.") from None
    if not api_key:
        raise ToolError("CODEGEN_API_KEY not set.")
    if not org_id:
        raise ToolError("CODEGEN_ORG_ID not set.")
    return CodegenClient(api_key=api_key, org_id=org_id)


def get_registry(ctx: Context | None = None) -> ContextRegistry:
    """Get ContextRegistry from lifespan context or global fallback."""
    global _registry
    if ctx is not None:
        lc = ctx.lifespan_context
        if lc and "registry" in lc:
            return lc["registry"]
    if _registry is not None:
        return _registry
    _registry = ContextRegistry()
    return _registry
