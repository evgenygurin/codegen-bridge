"""Dependency injection providers for MCP tools.

Uses FastMCP ``Depends()`` and ``CurrentContext()`` to inject
``CodegenClient`` and ``ContextRegistry`` into tool / resource functions.

Providers first try to resolve from ``lifespan_context`` (production),
falling back to lazy initialisation from environment variables (testing).
"""

from __future__ import annotations

import os

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context

from bridge.client import CodegenClient
from bridge.context import ContextRegistry

__all__ = [
    "CurrentContext",
    "Depends",
    "get_client",
    "get_registry",
]


# ── DI provider functions ───────────────────────────────


async def get_client(ctx: Context = CurrentContext()) -> CodegenClient:
    """Provide a ``CodegenClient`` instance.

    Resolution order:
    1. ``ctx.lifespan_context["client"]`` (set by server lifespan)
    2. Lazy creation from ``CODEGEN_API_KEY`` / ``CODEGEN_ORG_ID`` env vars
    """
    try:
        lc = ctx.lifespan_context
        if lc and "client" in lc:
            return lc["client"]
    except Exception:
        pass  # Context may not have lifespan_context in tests

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


# Module-level fallback for registry (stateful, survives across requests)
_fallback_registry: ContextRegistry | None = None


async def get_registry(ctx: Context = CurrentContext()) -> ContextRegistry:
    """Provide a ``ContextRegistry`` instance.

    Resolution order:
    1. ``ctx.lifespan_context["registry"]`` (set by server lifespan)
    2. Module-level singleton (for testing without lifespan)
    """
    global _fallback_registry

    try:
        lc = ctx.lifespan_context
        if lc and "registry" in lc:
            return lc["registry"]
    except Exception:
        pass  # Context may not have lifespan_context in tests

    if _fallback_registry is None:
        _fallback_registry = ContextRegistry()
    return _fallback_registry
