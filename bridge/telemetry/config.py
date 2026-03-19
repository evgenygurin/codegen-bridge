"""Telemetry configuration model and OTLP exporter setup.

Uses Pydantic ``BaseModel`` for validation and serialisation.
Configures OpenTelemetry tracing and metrics for the Codegen Bridge
MCP server.

When ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, ``setup_otlp_exporter``
configures the SDK TracerProvider with an OTLP span exporter.  Without
that env var, all operations remain no-ops with zero overhead.

Follows the same pattern as ``bridge.middleware.config``.
"""

from __future__ import annotations

import logging
import os

from pydantic import BaseModel, Field

logger = logging.getLogger("bridge.telemetry")


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


def telemetry_config_from_env() -> TelemetryConfig:
    """Build a ``TelemetryConfig`` from environment variables.

    Reads:
    - ``OTEL_SERVICE_NAME`` — overrides default service name
    - ``OTEL_EXPORTER_OTLP_ENDPOINT`` — when absent, telemetry stays disabled

    Returns a config with ``enabled=False`` when no OTLP endpoint is set.
    """
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    service_name = os.environ.get("OTEL_SERVICE_NAME", "codegen-bridge")
    enabled = bool(endpoint)
    return TelemetryConfig(enabled=enabled, service_name=service_name)


def setup_otlp_exporter(config: TelemetryConfig | None = None) -> bool:
    """Configure the OpenTelemetry SDK with an OTLP exporter.

    Reads ``OTEL_EXPORTER_OTLP_ENDPOINT`` to determine the collector
    address.  When the env var is absent or empty, returns ``False``
    and leaves the SDK unconfigured (all operations remain no-ops).

    Parameters
    ----------
    config:
        Telemetry config to use.  When ``None``, reads from env vars
        via ``telemetry_config_from_env()``.

    Returns
    -------
    bool
        ``True`` if the exporter was configured, ``False`` otherwise.
    """
    if config is None:
        config = telemetry_config_from_env()

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint:
        logger.debug("OTEL_EXPORTER_OTLP_ENDPOINT not set — OTLP export disabled")
        return False

    if not config.enabled:
        logger.debug("Telemetry disabled in config — OTLP export skipped")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "opentelemetry-sdk or opentelemetry-exporter-otlp not installed — "
            "OTLP export unavailable"
        )
        return False

    resource = Resource.create({"service.name": config.service_name})
    exporter = OTLPSpanExporter(endpoint=endpoint)
    processor = BatchSpanProcessor(exporter)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    logger.info(
        "OTLP exporter configured: endpoint=%s, service=%s",
        endpoint,
        config.service_name,
    )
    return True
