"""Tests for TelemetryMiddleware."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from bridge.telemetry import TelemetryMiddleware, configure_telemetry
from bridge.telemetry.config import TelemetryConfig, TracingConfig


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset telemetry config to defaults after each test."""
    configure_telemetry(TelemetryConfig())
    yield
    configure_telemetry(TelemetryConfig())


class TestTelemetryMiddlewareInit:
    def test_uses_default_config_when_none(self):
        mw = TelemetryMiddleware()
        assert mw.config.enabled is True

    def test_accepts_custom_config(self):
        cfg = TelemetryConfig(enabled=False)
        mw = TelemetryMiddleware(config=cfg)
        assert mw.config.enabled is False


class TestTelemetryMiddlewareToolSpans:
    """Test that TelemetryMiddleware creates spans for tool calls."""

    async def test_tool_call_creates_bridge_span(
        self, trace_exporter: InMemorySpanExporter
    ):
        server = FastMCP("test-telemetry")
        server.add_middleware(TelemetryMiddleware())

        @server.tool()
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        result = await server.call_tool("greet", {"name": "World"})
        assert result.content[0].text == "Hello, World!"

        spans = trace_exporter.get_finished_spans()
        bridge_spans = [s for s in spans if s.name.startswith("bridge.tool.")]
        assert len(bridge_spans) >= 1
        span = bridge_spans[0]
        assert span.attributes["bridge.tool.name"] == "greet"
        assert span.attributes["bridge.operation"] == "tool_call"

    async def test_tool_error_records_on_span(
        self, trace_exporter: InMemorySpanExporter
    ):
        server = FastMCP("test-telemetry-error")
        server.add_middleware(TelemetryMiddleware())

        @server.tool()
        def fail_tool() -> str:
            raise ValueError("deliberate failure")

        # Without ErrorHandlingMiddleware, the exception propagates
        with pytest.raises(ToolError, match="deliberate failure"):
            await server.call_tool("fail_tool", {})

        spans = trace_exporter.get_finished_spans()
        bridge_spans = [s for s in spans if s.name.startswith("bridge.tool.")]
        assert len(bridge_spans) >= 1
        span = bridge_spans[0]
        assert span.status.status_code == trace.StatusCode.ERROR

    async def test_argument_keys_recorded_when_configured(
        self, trace_exporter: InMemorySpanExporter
    ):
        cfg = TelemetryConfig(tracing=TracingConfig(record_tool_args=True))
        configure_telemetry(cfg)
        server = FastMCP("test-telemetry-args")
        server.add_middleware(TelemetryMiddleware(config=cfg))

        @server.tool()
        def echo(message: str, count: int = 1) -> str:
            return message * count

        await server.call_tool("echo", {"message": "hi", "count": 2})

        spans = trace_exporter.get_finished_spans()
        bridge_spans = [s for s in spans if s.name.startswith("bridge.tool.")]
        span = bridge_spans[0]
        assert span.attributes["bridge.tool.argument_keys"] == "count,message"

    async def test_no_span_when_disabled(self, trace_exporter: InMemorySpanExporter):
        cfg = TelemetryConfig(enabled=False)
        server = FastMCP("test-telemetry-disabled")
        server.add_middleware(TelemetryMiddleware(config=cfg))

        @server.tool()
        def ping() -> str:
            return "pong"

        await server.call_tool("ping", {})

        spans = trace_exporter.get_finished_spans()
        bridge_spans = [s for s in spans if s.name.startswith("bridge.tool.")]
        assert len(bridge_spans) == 0


class TestTelemetryMiddlewareResourceSpans:
    """Test that TelemetryMiddleware creates spans for resource reads."""

    async def test_resource_read_creates_span(
        self, trace_exporter: InMemorySpanExporter
    ):
        server = FastMCP("test-telemetry-resource")
        server.add_middleware(TelemetryMiddleware())

        @server.resource("config://status")
        def status_resource() -> str:
            return "ok"

        await server.read_resource("config://status")

        spans = trace_exporter.get_finished_spans()
        bridge_spans = [s for s in spans if s.name == "bridge.resource.read"]
        assert len(bridge_spans) >= 1
        span = bridge_spans[0]
        assert span.attributes["bridge.operation"] == "resource_read"
        assert "config://status" in span.attributes["bridge.resource.uri"]


class TestTelemetryMiddlewarePromptSpans:
    """Test that TelemetryMiddleware creates spans for prompt renders."""

    async def test_prompt_render_creates_span(
        self, trace_exporter: InMemorySpanExporter
    ):
        server = FastMCP("test-telemetry-prompt")
        server.add_middleware(TelemetryMiddleware())

        @server.prompt()
        def greeting(name: str) -> str:
            return f"Say hello to {name}"

        await server.render_prompt("greeting", {"name": "Alice"})

        spans = trace_exporter.get_finished_spans()
        bridge_spans = [s for s in spans if s.name == "bridge.prompt.greeting"]
        assert len(bridge_spans) >= 1
        span = bridge_spans[0]
        assert span.attributes["bridge.prompt.name"] == "greeting"
        assert span.attributes["bridge.operation"] == "prompt_get"


class TestTelemetryMiddlewareInStack:
    """Test TelemetryMiddleware integration with the middleware stack."""

    def test_included_in_default_stack(self):
        from bridge.middleware.config import MiddlewareConfig
        from bridge.middleware.stack import _build_stack

        stack = _build_stack(MiddlewareConfig())
        types = [type(mw).__name__ for mw in stack]
        assert "TelemetryMiddleware" in types

    def test_stack_has_eight_middleware(self):
        from bridge.middleware.config import MiddlewareConfig
        from bridge.middleware.stack import _build_stack

        stack = _build_stack(MiddlewareConfig())
        assert len(stack) == 8

    def test_telemetry_position_in_stack(self):
        """Telemetry should be after logging but before timing."""
        from bridge.middleware.config import MiddlewareConfig
        from bridge.middleware.stack import _build_stack

        stack = _build_stack(MiddlewareConfig())
        names = [type(mw).__name__ for mw in stack]
        telemetry_idx = names.index("TelemetryMiddleware")
        logging_idx = names.index("LoggingMiddleware")
        timing_idx = names.index("TimingMiddleware")
        assert logging_idx < telemetry_idx < timing_idx

    def test_disabled_telemetry_excluded_from_stack(self):
        from bridge.middleware.config import MiddlewareConfig
        from bridge.middleware.stack import _build_stack

        cfg = MiddlewareConfig(telemetry=TelemetryConfig(enabled=False))
        stack = _build_stack(cfg)
        types = [type(mw).__name__ for mw in stack]
        assert "TelemetryMiddleware" not in types
        assert len(stack) == 7  # Back to original 7
