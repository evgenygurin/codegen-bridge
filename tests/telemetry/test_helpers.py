"""Tests for telemetry helpers (tracing and metrics)."""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from bridge.telemetry.config import MetricsConfig, TelemetryConfig, TracingConfig
from bridge.telemetry.helpers import (
    bridge_span,
    configure,
    get_config,
    record_tool_call,
    tool_span,
)


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset telemetry config to defaults after each test."""
    configure(TelemetryConfig())
    yield
    configure(TelemetryConfig())


class TestConfigure:
    def test_default_config(self):
        cfg = get_config()
        assert cfg.enabled is True

    def test_custom_config(self):
        custom = TelemetryConfig(service_name="test-service")
        result = configure(custom)
        assert result.service_name == "test-service"
        assert get_config().service_name == "test-service"

    def test_none_returns_current(self):
        configure(TelemetryConfig(service_name="first"))
        result = configure(None)
        assert result.service_name == "first"


class TestBridgeSpan:
    def test_creates_span_with_name(self, trace_exporter: InMemorySpanExporter):
        with bridge_span("test.operation"):
            pass
        spans = trace_exporter.get_finished_spans()
        assert any(s.name == "test.operation" for s in spans)

    def test_span_has_attributes(self, trace_exporter: InMemorySpanExporter):
        with bridge_span("test.attrs", attributes={"key": "value"}):
            pass
        spans = trace_exporter.get_finished_spans()
        span = next(s for s in spans if s.name == "test.attrs")
        assert span.attributes["key"] == "value"

    def test_records_exception_on_error(self, trace_exporter: InMemorySpanExporter):
        with pytest.raises(ValueError, match="boom"), bridge_span("test.error"):
            raise ValueError("boom")
        spans = trace_exporter.get_finished_spans()
        span = next(s for s in spans if s.name == "test.error")
        assert span.status.status_code == trace.StatusCode.ERROR
        events = span.events
        assert any(e.name == "exception" for e in events)

    def test_noop_when_disabled(self, trace_exporter: InMemorySpanExporter):
        configure(TelemetryConfig(enabled=False))
        with bridge_span("test.disabled") as span:
            assert span is None
        spans = trace_exporter.get_finished_spans()
        assert not any(s.name == "test.disabled" for s in spans)

    def test_noop_when_tracing_disabled(self, trace_exporter: InMemorySpanExporter):
        configure(TelemetryConfig(tracing=TracingConfig(enabled=False)))
        with bridge_span("test.tracing_off") as span:
            assert span is None
        spans = trace_exporter.get_finished_spans()
        assert not any(s.name == "test.tracing_off" for s in spans)

    def test_exception_not_recorded_when_record_exceptions_false(
        self, trace_exporter: InMemorySpanExporter
    ):
        configure(TelemetryConfig(tracing=TracingConfig(record_exceptions=False)))
        with pytest.raises(ValueError, match="boom"), bridge_span("test.no_exc"):
            raise ValueError("boom")
        spans = trace_exporter.get_finished_spans()
        span = next(s for s in spans if s.name == "test.no_exc")
        # Status is still ERROR but no exception event recorded
        assert span.status.status_code == trace.StatusCode.ERROR
        assert not any(e.name == "exception" for e in span.events)


class TestToolSpan:
    def test_creates_span_for_tool(self, trace_exporter: InMemorySpanExporter):
        with tool_span("my_tool"):
            pass
        spans = trace_exporter.get_finished_spans()
        assert any(s.name == "bridge.tool.my_tool" for s in spans)

    def test_records_tool_name_attribute(self, trace_exporter: InMemorySpanExporter):
        with tool_span("my_tool"):
            pass
        spans = trace_exporter.get_finished_spans()
        span = next(s for s in spans if s.name == "bridge.tool.my_tool")
        assert span.attributes["bridge.tool.name"] == "my_tool"

    def test_records_org_id_when_provided(self, trace_exporter: InMemorySpanExporter):
        with tool_span("my_tool", org_id=42):
            pass
        spans = trace_exporter.get_finished_spans()
        span = next(s for s in spans if s.name == "bridge.tool.my_tool")
        assert span.attributes["bridge.org_id"] == 42

    def test_records_argument_keys_when_enabled(self, trace_exporter: InMemorySpanExporter):
        configure(TelemetryConfig(tracing=TracingConfig(record_tool_args=True)))
        with tool_span("my_tool", arguments={"repo_id": 1, "prompt": "hello"}):
            pass
        spans = trace_exporter.get_finished_spans()
        span = next(s for s in spans if s.name == "bridge.tool.my_tool")
        assert span.attributes["bridge.tool.argument_keys"] == "prompt,repo_id"

    def test_does_not_record_argument_keys_by_default(
        self, trace_exporter: InMemorySpanExporter
    ):
        with tool_span("my_tool", arguments={"secret": "value"}):
            pass
        spans = trace_exporter.get_finished_spans()
        span = next(s for s in spans if s.name == "bridge.tool.my_tool")
        assert "bridge.tool.argument_keys" not in span.attributes

    def test_noop_when_disabled(self, trace_exporter: InMemorySpanExporter):
        configure(TelemetryConfig(enabled=False))
        with tool_span("my_tool") as span:
            assert span is None

    def test_error_propagates(self, trace_exporter: InMemorySpanExporter):
        with pytest.raises(RuntimeError, match="fail"), tool_span("failing_tool"):
            raise RuntimeError("fail")


class TestRecordToolCall:
    def test_no_error_when_disabled(self):
        configure(TelemetryConfig(enabled=False))
        # Should not raise
        record_tool_call("my_tool", 0.5)

    def test_no_error_when_metrics_disabled(self):
        configure(TelemetryConfig(metrics=MetricsConfig(enabled=False)))
        # Should not raise
        record_tool_call("my_tool", 0.5)

    def test_records_without_error(self):
        configure(TelemetryConfig())
        # Should not raise — metrics are no-ops without SDK meter provider
        record_tool_call("my_tool", 0.123)

    def test_records_with_error_flag(self):
        configure(TelemetryConfig())
        record_tool_call("my_tool", 0.5, error=True)
