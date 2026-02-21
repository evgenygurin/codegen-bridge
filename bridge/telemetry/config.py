"""Telemetry configuration model.

Uses Pydantic ``BaseModel`` for validation and serialisation.
Configures OpenTelemetry tracing and metrics for the Codegen Bridge
MCP server.

The actual OpenTelemetry SDK setup is optional and controlled externally
(via ``opentelemetry-instrument`` CLI or programmatic SDK configuration).
This module only controls *what* gets instrumented, not *how* it is exported.

Follows the same pattern as ``bridge.middleware.config``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TracingConfig(BaseModel):
    """Configuration for OpenTelemetry distributed tracing.

    When ``enabled`` is ``True``, custom bridge-level spans are created
    for tool calls, resource reads, and prompt renders.  FastMCP itself
    always creates its own spans; these add *application-level* context
    (e.g. ``bridge.org_id``, ``bridge.repo_id``).
    """

    enabled: bool = True
    record_tool_args: bool = Field(
        default=False,
        description="Include tool argument names in span attributes (may contain PII).",
    )
    record_exceptions: bool = Field(
        default=True,
        description="Record exception details on spans.",
    )


class MetricsConfig(BaseModel):
    """Configuration for OpenTelemetry metrics.

    Tracks counters and histograms for tool invocations, errors,
    and latency.  Requires ``opentelemetry-sdk`` with a meter provider
    to actually export.
    """

    enabled: bool = True
    histogram_boundaries: list[float] = Field(
        default=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        description="Bucket boundaries (seconds) for latency histograms.",
    )


class TelemetryConfig(BaseModel):
    """Top-level configuration for the telemetry subsystem.

    Each sub-config can be individually enabled/disabled and tuned.
    """

    enabled: bool = Field(
        default=True,
        description="Master switch for all telemetry instrumentation.",
    )
    service_name: str = Field(
        default="codegen-bridge",
        description="OpenTelemetry service name attribute.",
    )
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
