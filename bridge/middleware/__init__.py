"""Middleware stack for Codegen Bridge MCP server.

Provides a configurable middleware pipeline built on FastMCP 3.x built-in
middleware classes.  The stack follows the **Chain of Responsibility** pattern:
each middleware can inspect, transform, or short-circuit requests before
forwarding them to the next handler.

Ordering (outermost → innermost):
1. ErrorHandling   — catches all exceptions, logs them, returns MCP errors
2. Ping            — keeps long-lived connections alive with periodic pings
3. Authorization   — blocks dangerous tools unless explicitly allowed
4. Logging         — structured request/response logging
5. Telemetry       — OpenTelemetry tracing spans and metrics
6. Timing          — records execution duration per operation
7. RateLimiting    — token-bucket throttling per client
8. Caching         — TTL-based response caching for idempotent operations
9. ResponseLimit   — truncates oversized tool responses

Usage::

    from bridge.middleware import configure_middleware

    mcp = FastMCP("Codegen Bridge", ...)
    configure_middleware(mcp)  # uses sensible defaults

    # or with custom config:
    from bridge.middleware import MiddlewareConfig
    configure_middleware(mcp, MiddlewareConfig(rate_limit_rps=5.0))
"""

from __future__ import annotations

from bridge.middleware.authorization import AuthorizationConfig, DangerousToolGuardMiddleware
from bridge.middleware.config import MiddlewareConfig
from bridge.middleware.stack import configure_middleware

__all__ = [
    "AuthorizationConfig",
    "DangerousToolGuardMiddleware",
    "MiddlewareConfig",
    "configure_middleware",
]
