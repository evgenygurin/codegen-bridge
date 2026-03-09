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
    from bridge.services.execution import ExecutionService
    from bridge.services.runs import RunService

__all__ = [
    "CurrentContext",
    "Depends",
    "get_client",
    "get_execution_service",
    "get_org_id",
    "get_registry",
    "get_repo_cache",
    "get_run_service",
    "get_sampling_config",
    "get_session_state",
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


async def get_run_service(ctx: Context = CurrentContext()) -> RunService:
    """Provide a ``RunService`` constructed from lifespan context.

    Created per-request rather than stored in the lifespan dict — keeps
    ``server.py`` unchanged while giving tools a high-level API.
    """
    from bridge.services.runs import RunService

    return RunService(
        client=ctx.lifespan_context["client"],
        registry=ctx.lifespan_context["registry"],
        repo_cache=ctx.lifespan_context["repo_cache"],
    )


async def get_execution_service(ctx: Context = CurrentContext()) -> ExecutionService:
    """Provide an ``ExecutionService`` constructed from lifespan context."""
    from bridge.services.execution import ExecutionService

    return ExecutionService(
        client=ctx.lifespan_context["client"],
        registry=ctx.lifespan_context["registry"],
        repo_cache=ctx.lifespan_context["repo_cache"],
    )


async def get_sampling_config(ctx: Context = CurrentContext()) -> SamplingConfig:
    """Provide the ``SamplingConfig`` from lifespan context."""
    from bridge.sampling.config import SamplingConfig

    lc = ctx.lifespan_context
    if lc and "sampling_config" in lc:
        cfg: SamplingConfig = lc["sampling_config"]
        return cfg
    return SamplingConfig()


async def get_session_state(ctx: Context = CurrentContext()) -> dict[str, str]:
    """Provide the per-session state dict from lifespan context.

    The dict is shared across all tools within a single MCP session and
    is reset when the session ends (server restart or client disconnect).
    """
    state: dict[str, str] = ctx.lifespan_context["session_state"]
    return state
