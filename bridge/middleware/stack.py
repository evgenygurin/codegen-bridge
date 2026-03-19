"""Middleware stack assembly.

Configures and registers the full middleware pipeline on a FastMCP server
instance.  Ordering is deliberate and encodes the **Chain of Responsibility**
pattern — each layer wraps the next, so the first added middleware becomes
the outermost handler.

The public entry point is :func:`configure_middleware`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastmcp.server.middleware.caching import (
    CallToolSettings,
    ListResourcesSettings,
    ListToolsSettings,
    ReadResourceSettings,
    ResponseCachingMiddleware,
)
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware
from fastmcp.server.middleware.ping import PingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware

from bridge.middleware.authorization import DangerousToolGuardMiddleware
from bridge.middleware.config import MiddlewareConfig
from bridge.telemetry import TelemetryMiddleware, configure_telemetry

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from fastmcp.server.middleware import Middleware

logger = logging.getLogger("bridge.middleware")


def _build_stack(config: MiddlewareConfig) -> list[Middleware]:
    """Instantiate enabled middleware in the correct chain order.

    Returns a list ordered outermost → innermost.  The caller must
    register them on the server via ``add_middleware`` in this order
    (FastMCP treats first-added as outermost).
    """
    stack: list[Middleware] = []

    # 1. Error handling — outermost; catches everything
    if config.error_handling.enabled:
        stack.append(
            ErrorHandlingMiddleware(
                logger=logger,
                include_traceback=config.error_handling.include_traceback,
                transform_errors=config.error_handling.transform_errors,
            )
        )

    # 2. Ping — keep connections alive
    if config.ping.enabled:
        stack.append(PingMiddleware(interval_ms=config.ping.interval_ms))

    # 3. Authorization — block dangerous tools unless explicitly allowed
    if config.authorization.enabled:
        stack.append(DangerousToolGuardMiddleware(config=config.authorization))

    # 4. Logging — structured request/response logging
    if config.logging.enabled:
        stack.append(
            LoggingMiddleware(
                logger=logger,
                include_payloads=config.logging.include_payloads,
                include_payload_length=config.logging.include_payload_length,
                estimate_payload_tokens=config.logging.estimate_payload_tokens,
                max_payload_length=config.logging.max_payload_length,
            )
        )

    # 5. Telemetry — OpenTelemetry tracing and metrics
    if config.telemetry.enabled:
        configure_telemetry(config.telemetry)
        stack.append(TelemetryMiddleware(config=config.telemetry))

    # 6. Timing — execution duration per operation
    if config.timing.enabled:
        stack.append(TimingMiddleware(logger=logger))

    # 7. Rate limiting — token-bucket throttling
    if config.rate_limiting.enabled:
        stack.append(
            RateLimitingMiddleware(
                max_requests_per_second=config.rate_limiting.max_requests_per_second,
                burst_capacity=config.rate_limiting.burst_capacity,
                global_limit=config.rate_limiting.global_limit,
            )
        )

    # 8. Caching — TTL-based response caching with real-time tool exclusions
    if config.caching.enabled:
        call_tool_cfg = CallToolSettings(
            enabled=config.caching.tool_call_enabled,
            ttl=config.caching.tool_ttl,
        )
        if config.caching.realtime_tools:
            call_tool_cfg["excluded_tools"] = config.caching.realtime_tools
        stack.append(
            ResponseCachingMiddleware(
                list_tools_settings=ListToolsSettings(ttl=config.caching.list_ttl),
                list_resources_settings=ListResourcesSettings(ttl=config.caching.list_ttl),
                call_tool_settings=call_tool_cfg,
                read_resource_settings=ReadResourceSettings(ttl=config.caching.resource_ttl),
                max_item_size=config.caching.max_item_size,
            )
        )

    # 9. Response limiting — truncate oversized tool output
    if config.response_limiting.enabled:
        stack.append(
            ResponseLimitingMiddleware(
                max_size=config.response_limiting.max_size,
                truncation_suffix=config.response_limiting.truncation_suffix,
            )
        )

    return stack


def configure_middleware(
    server: FastMCP,
    config: MiddlewareConfig | None = None,
) -> list[Middleware]:
    """Build and register the middleware stack on *server*.

    Parameters
    ----------
    server:
        The FastMCP server instance to configure.
    config:
        Optional configuration; defaults to ``MiddlewareConfig()`` which
        enables all middleware with production-ready defaults.

    Returns
    -------
    list[Middleware]
        The middleware instances that were registered, in chain order.
        Useful for testing or post-registration inspection.
    """
    if config is None:
        config = MiddlewareConfig()

    stack = _build_stack(config)

    for mw in stack:
        server.add_middleware(mw)

    enabled = [type(mw).__name__ for mw in stack]
    logger.info("Middleware stack configured: %s", " → ".join(enabled))

    return stack
