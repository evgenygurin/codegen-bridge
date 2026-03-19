"""OpenTelemetry integration for Codegen Bridge MCP server.

Provides distributed tracing and metrics via the OpenTelemetry API.
FastMCP 3.x already creates ``tools/call``, ``resources/read``, and
``prompts/get`` spans; this module adds bridge-specific instrumentation:

- **Custom spans** with application-level attributes (org_id, tool args)
- **Metrics** — invocation counters and latency histograms
- **Middleware** — ``TelemetryMiddleware`` hooks into the FastMCP pipeline
- **Helpers** — ``bridge_span``, ``tool_span``, ``record_tool_call``

No OpenTelemetry SDK is required at runtime.  Without an SDK all
operations are no-ops with zero overhead.  To enable export, install
``opentelemetry-sdk`` and configure a tracer/meter provider (or use
``opentelemetry-instrument`` on the command line).

Usage::

    from bridge.telemetry import configure_telemetry, TelemetryConfig

    # Configure (optional — defaults are sensible)
    configure_telemetry(TelemetryConfig(service_name="my-bridge"))

    # In middleware stack (added automatically by configure_middleware)
    from bridge.telemetry import TelemetryMiddleware
    server.add_middleware(TelemetryMiddleware())

    # Custom spans in tool handlers
    from bridge.telemetry import bridge_span
    with bridge_span("my_operation", attributes={"key": "value"}):
        ...
"""

from __future__ import annotations

from bridge.telemetry.config import (
    MetricsConfig,
    TelemetryConfig,
    TracingConfig,
    setup_otlp_exporter,
    telemetry_config_from_env,
)
from bridge.telemetry.helpers import (
    bridge_span,
    configure,
    get_config,
    record_tool_call,
    set_span_attributes,
    tool_span,
)
from bridge.telemetry.middleware import TelemetryMiddleware

__all__ = [
    "MetricsConfig",
    "TelemetryConfig",
    "TelemetryMiddleware",
    "TracingConfig",
    "bridge_span",
    "configure_telemetry",
    "get_config",
    "record_tool_call",
    "set_span_attributes",
    "setup_otlp_exporter",
    "telemetry_config_from_env",
    "tool_span",
]


def configure_telemetry(config: TelemetryConfig | None = None) -> TelemetryConfig:
    """Configure the telemetry subsystem.

    Convenience wrapper around ``bridge.telemetry.helpers.configure``.
    Returns the active configuration.
    """
    return configure(config)
