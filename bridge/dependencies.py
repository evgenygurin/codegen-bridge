"""Dependency injection providers for MCP tools.

Uses FastMCP ``Depends()`` and ``CurrentContext()`` to inject shared
resources into tool / resource functions.  Every value yielded by the
server lifespan has a corresponding DI provider here.

All providers resolve exclusively from ``lifespan_context``.  The server
lifespan (``bridge.server._lifespan``) is responsible for creating and
tearing down resources; providers simply expose them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context

from bridge.client import CodegenClient
from bridge.context import ContextRegistry
from bridge.helpers.repo_detection import RepoCache

if TYPE_CHECKING:
    from bridge.sampling.config import SamplingConfig

__all__ = [
    "CurrentContext",
    "Depends",
    "get_client",
    "get_org_id",
    "get_registry",
    "get_repo_cache",
    "get_sampling_config",
]


# ── DI provider functions ───────────────────────────────


async def get_client(ctx: Context = CurrentContext()) -> CodegenClient:
    """Provide the ``CodegenClient`` from lifespan context."""
    client: CodegenClient = ctx.lifespan_context["client"]
    return client


async def get_org_id(ctx: Context = CurrentContext()) -> int:
    """Provide the organisation ID from lifespan context."""
    org_id: int = ctx.lifespan_context["org_id"]
    return org_id


async def get_registry(ctx: Context = CurrentContext()) -> ContextRegistry:
    """Provide the ``ContextRegistry`` from lifespan context."""
    registry: ContextRegistry = ctx.lifespan_context["registry"]
    return registry


async def get_repo_cache(ctx: Context = CurrentContext()) -> RepoCache:
    """Provide the ``RepoCache`` from lifespan context."""
    repo_cache: RepoCache = ctx.lifespan_context["repo_cache"]
    return repo_cache


async def get_sampling_config(ctx: Context = CurrentContext()) -> SamplingConfig:
    """Provide the ``SamplingConfig`` from lifespan context."""
    from bridge.sampling.config import SamplingConfig

    lc = ctx.lifespan_context
    if lc and "sampling_config" in lc:
        cfg: SamplingConfig = lc["sampling_config"]
        return cfg
    return SamplingConfig()
