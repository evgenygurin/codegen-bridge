"""OpenTelemetry instrumentation middleware for the MCP server.

Extends the FastMCP ``Middleware`` base class to add bridge-specific
tracing spans and metrics for tool calls, resource reads, and prompt
renders.  FastMCP already creates its own spans (``tools/call {name}``,
etc.); this middleware adds an *inner* ``bridge.*`` span with
application-level attributes (org_id, argument keys, etc.) and records
counters/histograms for operational dashboards.

Position in the stack: should be placed **after** error handling and
logging but **before** caching and rate limiting so that the timing
reflects actual execution, not cached short-circuits.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import mcp.types as mt
from fastmcp.server.middleware import Middleware
from opentelemetry.trace import StatusCode

from bridge.telemetry.config import TelemetryConfig
from bridge.telemetry.helpers import (
    bridge_span,
    get_config,
    record_tool_call,
)

if TYPE_CHECKING:
    from fastmcp.server.middleware import CallNext, MiddlewareContext
    from fastmcp.tools import ToolResult


class TelemetryMiddleware(Middleware):
    """Middleware that instruments MCP operations with OpenTelemetry.

    Creates bridge-level spans for each operation type and records
    invocation metrics (counters + latency histograms).

    Parameters
    ----------
    config:
        Telemetry configuration.  When ``None``, uses the module-level
        configuration from ``bridge.telemetry.helpers.get_config()``.
    """

    def __init__(self, config: TelemetryConfig | None = None) -> None:
        self.config = config or get_config()

    # ── Tool calls ──────────────────────────────────────────

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> Any:
        """Instrument tool invocations with spans and metrics."""
        cfg = self.config
        if not cfg.enabled:
            return await call_next(context)

        tool_name = context.message.name
        arguments = context.message.arguments

        attrs: dict[str, Any] = {
            "bridge.tool.name": tool_name,
            "bridge.operation": "tool_call",
        }
        if cfg.tracing.record_tool_args and arguments:
            attrs["bridge.tool.argument_keys"] = ",".join(sorted(arguments.keys()))

        start = time.monotonic()
        error_occurred = False

        with bridge_span(f"bridge.tool.{tool_name}", attributes=attrs) as span:
            try:
                result = await call_next(context)
            except Exception as exc:
                error_occurred = True
                if span is not None and cfg.tracing.record_exceptions:
                    span.record_exception(exc)
                    span.set_status(StatusCode.ERROR, str(exc))
                raise
            finally:
                duration = time.monotonic() - start
                if cfg.metrics.enabled:
                    record_tool_call(tool_name, duration, error=error_occurred)

        return result

    # ── Resource reads ──────────────────────────────────────

    async def on_read_resource(
        self,
        context: MiddlewareContext[mt.ReadResourceRequestParams],
        call_next: CallNext[mt.ReadResourceRequestParams, Any],
    ) -> Any:
        """Instrument resource read operations."""
        cfg = self.config
        if not cfg.enabled:
            return await call_next(context)

        resource_uri = str(context.message.uri)
        attrs: dict[str, Any] = {
            "bridge.resource.uri": resource_uri,
            "bridge.operation": "resource_read",
        }

        with bridge_span("bridge.resource.read", attributes=attrs):
            return await call_next(context)

    # ── Prompt renders ──────────────────────────────────────

    async def on_get_prompt(
        self,
        context: MiddlewareContext[mt.GetPromptRequestParams],
        call_next: CallNext[mt.GetPromptRequestParams, Any],
    ) -> Any:
        """Instrument prompt render operations."""
        cfg = self.config
        if not cfg.enabled:
            return await call_next(context)

        prompt_name = context.message.name
        attrs: dict[str, Any] = {
            "bridge.prompt.name": prompt_name,
            "bridge.operation": "prompt_get",
        }

        with bridge_span(f"bridge.prompt.{prompt_name}", attributes=attrs):
            return await call_next(context)
