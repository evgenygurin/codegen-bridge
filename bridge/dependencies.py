"""Dependency injection providers for MCP tools.

Uses FastMCP ``Depends()`` and ``CurrentContext()`` to inject shared
resources into tool / resource functions.  Every value yielded by the
server lifespan has a corresponding DI provider here.

All providers resolve exclusively from ``lifespan_context``.  The server
lifespan (``bridge.server._lifespan``) is responsible for creating and
tearing down resources; providers simply expose them.
"""

from __future__ import annotations

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context

from bridge.client import CodegenClient
from bridge.context import ContextRegistry
from bridge.helpers.repo_detection import RepoCache

__all__ = [
    "CurrentContext",
    "Depends",
    "get_client",
    "get_org_id",
    "get_registry",
    "get_repo_cache",
]


# ── DI provider functions ───────────────────────────────


async def get_client(ctx: Context = CurrentContext()) -> CodegenClient:
    """Provide the ``CodegenClient`` from lifespan context."""
    return ctx.lifespan_context["client"]


async def get_org_id(ctx: Context = CurrentContext()) -> int:
    """Provide the organisation ID from lifespan context."""
    return ctx.lifespan_context["org_id"]


async def get_registry(ctx: Context = CurrentContext()) -> ContextRegistry:
    """Provide the ``ContextRegistry`` from lifespan context."""
    return ctx.lifespan_context["registry"]


async def get_repo_cache(ctx: Context = CurrentContext()) -> RepoCache:
    """Provide the ``RepoCache`` from lifespan context."""
    return ctx.lifespan_context["repo_cache"]
