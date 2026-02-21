"""Telemetry helpers for OpenTelemetry tracing and metrics.

Wraps the OpenTelemetry API to provide bridge-specific spans and metrics.
All operations are no-ops when no OpenTelemetry SDK is configured, so
there is zero overhead in production if telemetry is not enabled.

Uses ``fastmcp.telemetry.get_tracer`` for spans and the standard
``opentelemetry.metrics`` API for counters/histograms.
"""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from fastmcp.server.telemetry import get_tracer  # type: ignore[attr-defined]
from opentelemetry import metrics as otel_metrics

from bridge.telemetry.config import TelemetryConfig

# ── Module-level state ──────────────────────────────────────

_config: TelemetryConfig = TelemetryConfig()

# Meter for bridge-specific metrics
_meter: otel_metrics.Meter | None = None

# Instruments (lazily initialised)
_tool_call_counter: otel_metrics.Counter | None = None
_tool_error_counter: otel_metrics.Counter | None = None
_tool_duration_histogram: otel_metrics.Histogram | None = None


# ── Configuration ───────────────────────────────────────────


def configure(config: TelemetryConfig | None = None) -> TelemetryConfig:
    """Set the telemetry configuration.

    Must be called before any spans or metrics are recorded.
    Returns the active configuration.
    """
    global _config
    if config is not None:
        _config = config
    return _config


def get_config() -> TelemetryConfig:
    """Return the current telemetry configuration."""
    return _config


# ── Meter / Instruments ────────────────────────────────────


def _get_meter() -> otel_metrics.Meter:
    """Return (or create) the bridge metrics meter."""
    global _meter
    if _meter is None:
        _meter = otel_metrics.get_meter("bridge", "0.1.0")
    return _meter


def _get_tool_call_counter() -> otel_metrics.Counter:
    global _tool_call_counter
    if _tool_call_counter is None:
        _tool_call_counter = _get_meter().create_counter(
            name="bridge.tool.calls",
            description="Number of MCP tool invocations",
            unit="1",
        )
    return _tool_call_counter


def _get_tool_error_counter() -> otel_metrics.Counter:
    global _tool_error_counter
    if _tool_error_counter is None:
        _tool_error_counter = _get_meter().create_counter(
            name="bridge.tool.errors",
            description="Number of MCP tool invocation errors",
            unit="1",
        )
    return _tool_error_counter


def _get_tool_duration_histogram() -> otel_metrics.Histogram:
    global _tool_duration_histogram
    if _tool_duration_histogram is None:
        _tool_duration_histogram = _get_meter().create_histogram(
            name="bridge.tool.duration",
            description="Tool execution duration in seconds",
            unit="s",
        )
    return _tool_duration_histogram


# ── Tracing helpers ─────────────────────────────────────────


@contextmanager
def bridge_span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """Create a bridge-level span for custom application instrumentation.

    When tracing is disabled or no SDK is configured, this is a no-op.

    Parameters
    ----------
    name:
        Span name, e.g. ``"bridge.create_run"``.
    attributes:
        Extra span attributes to set.

    Yields
    ------
    opentelemetry.trace.Span
        The active span (may be a no-op span).
    """
    cfg = get_config()
    if not cfg.enabled or not cfg.tracing.enabled:
        yield None
        return

    tracer = get_tracer()
    with tracer.start_as_current_span(
        name,
        record_exception=cfg.tracing.record_exceptions,
        set_status_on_exception=True,
    ) as span:
        if attributes:
            span.set_attributes(attributes)
        yield span


@contextmanager
def tool_span(
    tool_name: str,
    *,
    arguments: dict[str, Any] | None = None,
    org_id: int | None = None,
) -> Generator[Any, None, None]:
    """Create a span and record metrics for a bridge tool invocation.

    Combines tracing (span) and metrics (counter + histogram) in one
    context manager for use inside tool handlers or middleware.

    Parameters
    ----------
    tool_name:
        Name of the tool being invoked.
    arguments:
        Tool arguments (only argument *names* are recorded, not values,
        unless ``TracingConfig.record_tool_args`` is ``True``).
    org_id:
        Organisation ID, recorded as a span attribute when available.
    """
    cfg = get_config()
    if not cfg.enabled:
        yield None
        return

    attrs: dict[str, Any] = {
        "bridge.tool.name": tool_name,
    }
    if org_id is not None:
        attrs["bridge.org_id"] = org_id
    if arguments is not None and cfg.tracing.record_tool_args:
        # Record argument keys (values may be sensitive)
        attrs["bridge.tool.argument_keys"] = ",".join(sorted(arguments.keys()))

    start = time.monotonic()
    error_occurred = False

    with bridge_span(f"bridge.tool.{tool_name}", attributes=attrs) as span:
        try:
            yield span
        except Exception:
            error_occurred = True
            raise
        finally:
            duration = time.monotonic() - start
            metric_attrs = {"tool.name": tool_name}

            if cfg.metrics.enabled:
                _get_tool_call_counter().add(1, metric_attrs)
                _get_tool_duration_histogram().record(duration, metric_attrs)
                if error_occurred:
                    _get_tool_error_counter().add(1, metric_attrs)


# ── Metrics-only helpers ────────────────────────────────────


def record_tool_call(
    tool_name: str,
    duration_s: float,
    *,
    error: bool = False,
) -> None:
    """Record tool call metrics without creating a span.

    Useful when the span is already created by FastMCP middleware
    but you still want bridge-level metrics.
    """
    cfg = get_config()
    if not cfg.enabled or not cfg.metrics.enabled:
        return

    attrs = {"tool.name": tool_name}
    _get_tool_call_counter().add(1, attrs)
    _get_tool_duration_histogram().record(duration_s, attrs)
    if error:
        _get_tool_error_counter().add(1, attrs)
