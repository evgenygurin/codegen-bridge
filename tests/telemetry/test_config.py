"""Tests for telemetry configuration models."""

from __future__ import annotations

from bridge.telemetry.config import MetricsConfig, TelemetryConfig, TracingConfig


class TestTelemetryConfig:
    """Top-level TelemetryConfig tests."""

    def test_default_creates_all_enabled(self):
        cfg = TelemetryConfig()
        assert cfg.enabled is True
        assert cfg.tracing.enabled is True
        assert cfg.metrics.enabled is True

    def test_default_service_name(self):
        cfg = TelemetryConfig()
        assert cfg.service_name == "codegen-bridge"

    def test_custom_service_name(self):
        cfg = TelemetryConfig(service_name="my-bridge")
        assert cfg.service_name == "my-bridge"

    def test_partial_override(self):
        cfg = TelemetryConfig(
            tracing=TracingConfig(enabled=False),
        )
        assert cfg.tracing.enabled is False
        assert cfg.metrics.enabled is True

    def test_serialise_round_trip(self):
        cfg = TelemetryConfig()
        data = cfg.model_dump()
        restored = TelemetryConfig.model_validate(data)
        assert restored == cfg

    def test_disabled_master_switch(self):
        cfg = TelemetryConfig(enabled=False)
        assert cfg.enabled is False
        # Sub-configs remain independently configurable
        assert cfg.tracing.enabled is True
        assert cfg.metrics.enabled is True


class TestTracingConfig:
    def test_defaults(self):
        cfg = TracingConfig()
        assert cfg.enabled is True
        assert cfg.record_tool_args is False
        assert cfg.record_exceptions is True

    def test_enable_tool_args(self):
        cfg = TracingConfig(record_tool_args=True)
        assert cfg.record_tool_args is True

    def test_disable_exceptions(self):
        cfg = TracingConfig(record_exceptions=False)
        assert cfg.record_exceptions is False


class TestMetricsConfig:
    def test_defaults(self):
        cfg = MetricsConfig()
        assert cfg.enabled is True
        assert len(cfg.histogram_boundaries) > 0

    def test_custom_boundaries(self):
        boundaries = [0.1, 0.5, 1.0, 5.0]
        cfg = MetricsConfig(histogram_boundaries=boundaries)
        assert cfg.histogram_boundaries == boundaries

    def test_boundaries_are_floats(self):
        cfg = MetricsConfig()
        for b in cfg.histogram_boundaries:
            assert isinstance(b, float)
