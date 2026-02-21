"""Tests for middleware stack assembly and integration."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.middleware.caching import ResponseCachingMiddleware
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware
from fastmcp.server.middleware.ping import PingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware

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
from bridge.middleware.stack import _build_stack, configure_middleware

# FastMCP adds a built-in DereferenceRefsMiddleware by default.
_FASTMCP_DEFAULT_MIDDLEWARE_COUNT = len(FastMCP("_probe").middleware)


class TestBuildStack:
    """Unit tests for _build_stack (no server needed)."""

    def test_default_config_creates_all_seven(self):
        stack = _build_stack(MiddlewareConfig())
        assert len(stack) == 7

    def test_default_order(self):
        """Middleware are ordered outermost → innermost."""
        stack = _build_stack(MiddlewareConfig())
        types = [type(mw) for mw in stack]
        assert types == [
            ErrorHandlingMiddleware,
            PingMiddleware,
            LoggingMiddleware,
            TimingMiddleware,
            RateLimitingMiddleware,
            ResponseCachingMiddleware,
            ResponseLimitingMiddleware,
        ]

    def test_disable_single_middleware(self):
        cfg = MiddlewareConfig(rate_limiting=RateLimitingConfig(enabled=False))
        stack = _build_stack(cfg)
        types = [type(mw) for mw in stack]
        assert RateLimitingMiddleware not in types
        assert len(stack) == 6

    def test_disable_all_middleware(self):
        cfg = MiddlewareConfig(
            error_handling=ErrorHandlingConfig(enabled=False),
            ping=PingConfig(enabled=False),
            logging=LoggingConfig(enabled=False),
            timing=TimingConfig(enabled=False),
            rate_limiting=RateLimitingConfig(enabled=False),
            caching=CachingConfig(enabled=False),
            response_limiting=ResponseLimitingConfig(enabled=False),
        )
        stack = _build_stack(cfg)
        assert stack == []

    def test_only_error_handling_enabled(self):
        cfg = MiddlewareConfig(
            ping=PingConfig(enabled=False),
            logging=LoggingConfig(enabled=False),
            timing=TimingConfig(enabled=False),
            rate_limiting=RateLimitingConfig(enabled=False),
            caching=CachingConfig(enabled=False),
            response_limiting=ResponseLimitingConfig(enabled=False),
        )
        stack = _build_stack(cfg)
        assert len(stack) == 1
        assert isinstance(stack[0], ErrorHandlingMiddleware)

    def test_custom_rate_limit_params(self):
        cfg = MiddlewareConfig(
            error_handling=ErrorHandlingConfig(enabled=False),
            ping=PingConfig(enabled=False),
            logging=LoggingConfig(enabled=False),
            timing=TimingConfig(enabled=False),
            rate_limiting=RateLimitingConfig(
                max_requests_per_second=5.0,
                burst_capacity=10,
            ),
            caching=CachingConfig(enabled=False),
            response_limiting=ResponseLimitingConfig(enabled=False),
        )
        stack = _build_stack(cfg)
        assert len(stack) == 1
        rl = stack[0]
        assert isinstance(rl, RateLimitingMiddleware)
        assert rl.max_requests_per_second == 5.0
        assert rl.burst_capacity == 10

    def test_custom_response_limiting_params(self):
        cfg = MiddlewareConfig(
            error_handling=ErrorHandlingConfig(enabled=False),
            ping=PingConfig(enabled=False),
            logging=LoggingConfig(enabled=False),
            timing=TimingConfig(enabled=False),
            rate_limiting=RateLimitingConfig(enabled=False),
            caching=CachingConfig(enabled=False),
            response_limiting=ResponseLimitingConfig(
                max_size=100_000,
                truncation_suffix="...truncated",
            ),
        )
        stack = _build_stack(cfg)
        assert len(stack) == 1
        rl = stack[0]
        assert isinstance(rl, ResponseLimitingMiddleware)
        assert rl.max_size == 100_000
        assert rl.truncation_suffix == "...truncated"


class TestConfigureMiddleware:
    """Integration tests for configure_middleware."""

    def test_registers_middleware_on_server(self):
        server = FastMCP("test")
        stack = configure_middleware(server)
        assert len(server.middleware) == _FASTMCP_DEFAULT_MIDDLEWARE_COUNT + 7
        assert len(stack) == 7

    def test_returns_instances_registered_on_server(self):
        server = FastMCP("test")
        stack = configure_middleware(server)
        # Our middleware are appended after FastMCP's built-in ones
        added = server.middleware[_FASTMCP_DEFAULT_MIDDLEWARE_COUNT:]
        assert added == stack

    def test_default_config_when_none(self):
        server = FastMCP("test")
        stack = configure_middleware(server, config=None)
        assert len(stack) == 7

    def test_custom_config(self):
        server = FastMCP("test")
        cfg = MiddlewareConfig(
            ping=PingConfig(enabled=False),
            caching=CachingConfig(enabled=False),
        )
        stack = configure_middleware(server, config=cfg)
        assert len(stack) == 5
        types = [type(mw) for mw in stack]
        assert PingMiddleware not in types
        assert ResponseCachingMiddleware not in types

    def test_empty_config_registers_nothing_extra(self):
        server = FastMCP("test")
        baseline = len(server.middleware)
        cfg = MiddlewareConfig(
            error_handling=ErrorHandlingConfig(enabled=False),
            ping=PingConfig(enabled=False),
            logging=LoggingConfig(enabled=False),
            timing=TimingConfig(enabled=False),
            rate_limiting=RateLimitingConfig(enabled=False),
            caching=CachingConfig(enabled=False),
            response_limiting=ResponseLimitingConfig(enabled=False),
        )
        stack = configure_middleware(server, config=cfg)
        assert stack == []
        assert len(server.middleware) == baseline

    def test_does_not_duplicate_on_repeated_call(self):
        """Each call appends; caller should call once."""
        server = FastMCP("test")
        baseline = len(server.middleware)
        configure_middleware(server)
        assert len(server.middleware) == baseline + 7
        # Calling again adds more (this is expected FastMCP behaviour)
        configure_middleware(server)
        assert len(server.middleware) == baseline + 14
