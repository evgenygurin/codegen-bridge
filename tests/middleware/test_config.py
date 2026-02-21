"""Tests for middleware configuration models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bridge.middleware.config import (
    CachingConfig,
    ErrorHandlingConfig,
    LoggingConfig,
    MiddlewareConfig,
    PingConfig,
    RateLimitingConfig,
    ResponseLimitingConfig,
    TimingConfig,
)


class TestMiddlewareConfig:
    """Top-level MiddlewareConfig tests."""

    def test_default_creates_all_enabled(self):
        cfg = MiddlewareConfig()
        assert cfg.error_handling.enabled is True
        assert cfg.ping.enabled is True
        assert cfg.logging.enabled is True
        assert cfg.telemetry.enabled is True
        assert cfg.timing.enabled is True
        assert cfg.rate_limiting.enabled is True
        assert cfg.caching.enabled is True
        assert cfg.response_limiting.enabled is True

    def test_partial_override(self):
        cfg = MiddlewareConfig(
            rate_limiting=RateLimitingConfig(enabled=False),
            caching=CachingConfig(tool_ttl=120),
        )
        assert cfg.rate_limiting.enabled is False
        assert cfg.caching.tool_ttl == 120
        # others remain defaults
        assert cfg.error_handling.enabled is True

    def test_serialise_round_trip(self):
        cfg = MiddlewareConfig()
        data = cfg.model_dump()
        restored = MiddlewareConfig.model_validate(data)
        assert restored == cfg


class TestErrorHandlingConfig:
    def test_defaults(self):
        cfg = ErrorHandlingConfig()
        assert cfg.enabled is True
        assert cfg.include_traceback is False
        assert cfg.transform_errors is True


class TestPingConfig:
    def test_defaults(self):
        cfg = PingConfig()
        assert cfg.interval_ms == 30_000

    def test_interval_must_be_positive(self):
        with pytest.raises(ValidationError):
            PingConfig(interval_ms=0)

    def test_custom_interval(self):
        cfg = PingConfig(interval_ms=5_000)
        assert cfg.interval_ms == 5_000


class TestLoggingConfig:
    def test_defaults(self):
        cfg = LoggingConfig()
        assert cfg.include_payloads is False
        assert cfg.include_payload_length is True
        assert cfg.estimate_payload_tokens is False
        assert cfg.max_payload_length == 1_000

    def test_max_payload_length_must_be_positive(self):
        with pytest.raises(ValidationError):
            LoggingConfig(max_payload_length=0)


class TestTimingConfig:
    def test_defaults(self):
        cfg = TimingConfig()
        assert cfg.enabled is True


class TestRateLimitingConfig:
    def test_defaults(self):
        cfg = RateLimitingConfig()
        assert cfg.max_requests_per_second == 50.0
        assert cfg.burst_capacity == 200
        assert cfg.global_limit is False

    def test_rps_must_be_positive(self):
        with pytest.raises(ValidationError):
            RateLimitingConfig(max_requests_per_second=0)

    def test_custom_burst(self):
        cfg = RateLimitingConfig(burst_capacity=50)
        assert cfg.burst_capacity == 50


class TestCachingConfig:
    def test_defaults(self):
        cfg = CachingConfig()
        assert cfg.tool_ttl == 60
        assert cfg.resource_ttl == 30
        assert cfg.list_ttl == 30
        assert cfg.max_item_size == 1_048_576

    def test_ttl_allows_zero(self):
        cfg = CachingConfig(tool_ttl=0)
        assert cfg.tool_ttl == 0

    def test_max_item_size_must_be_positive(self):
        with pytest.raises(ValidationError):
            CachingConfig(max_item_size=0)


class TestResponseLimitingConfig:
    def test_defaults(self):
        cfg = ResponseLimitingConfig()
        assert cfg.max_size == 500_000
        assert "truncated" in cfg.truncation_suffix.lower()

    def test_max_size_must_be_positive(self):
        with pytest.raises(ValidationError):
            ResponseLimitingConfig(max_size=0)

    def test_custom_suffix(self):
        cfg = ResponseLimitingConfig(truncation_suffix="...cut")
        assert cfg.truncation_suffix == "...cut"
