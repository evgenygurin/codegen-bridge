"""Middleware configuration model.

Uses Pydantic ``BaseModel`` for validation and serialisation.  Every
middleware has an ``enabled`` flag and its own parameters with sensible
defaults tuned for a Codegen Bridge MCP server.

Environment variable overrides are *not* handled here — the server
lifespan already reads ``os.environ`` and can pass values into
``MiddlewareConfig`` if needed.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorHandlingConfig(BaseModel):
    """Configuration for :class:`ErrorHandlingMiddleware`."""

    enabled: bool = True
    include_traceback: bool = False
    transform_errors: bool = True


class PingConfig(BaseModel):
    """Configuration for :class:`PingMiddleware`.

    Keeps stateful HTTP connections alive by sending periodic pings.
    """

    enabled: bool = True
    interval_ms: int = Field(default=30_000, gt=0)


class LoggingConfig(BaseModel):
    """Configuration for :class:`LoggingMiddleware`."""

    enabled: bool = True
    include_payloads: bool = False
    include_payload_length: bool = True
    estimate_payload_tokens: bool = False
    max_payload_length: int = Field(default=1_000, gt=0)


class TimingConfig(BaseModel):
    """Configuration for :class:`TimingMiddleware`."""

    enabled: bool = True


class RateLimitingConfig(BaseModel):
    """Configuration for :class:`RateLimitingMiddleware`.

    Uses a token-bucket algorithm: ``max_requests_per_second`` is the
    sustained rate, ``burst_capacity`` allows short bursts above that.
    """

    enabled: bool = True
    max_requests_per_second: float = Field(default=50.0, gt=0)
    burst_capacity: int | None = Field(default=200)
    global_limit: bool = False


class CachingConfig(BaseModel):
    """Configuration for :class:`ResponseCachingMiddleware`.

    ``tool_ttl`` and ``resource_ttl`` control per-operation cache
    lifetimes in seconds.  ``max_item_size`` caps individual cached
    items (bytes).
    """

    enabled: bool = True
    tool_ttl: int = Field(default=60, ge=0)
    resource_ttl: int = Field(default=30, ge=0)
    list_ttl: int = Field(default=30, ge=0)
    max_item_size: int = Field(default=1_048_576, gt=0)


class ResponseLimitingConfig(BaseModel):
    """Configuration for :class:`ResponseLimitingMiddleware`.

    Truncates tool responses that exceed ``max_size`` bytes to prevent
    overwhelming LLM context windows.
    """

    enabled: bool = True
    max_size: int = Field(default=500_000, gt=0)
    truncation_suffix: str = "\n\n[Response truncated due to size limit]"


class MiddlewareConfig(BaseModel):
    """Top-level configuration for the full middleware stack.

    Each sub-config can be individually enabled/disabled and tuned.
    """

    error_handling: ErrorHandlingConfig = Field(default_factory=ErrorHandlingConfig)
    ping: PingConfig = Field(default_factory=PingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    timing: TimingConfig = Field(default_factory=TimingConfig)
    rate_limiting: RateLimitingConfig = Field(default_factory=RateLimitingConfig)
    caching: CachingConfig = Field(default_factory=CachingConfig)
    response_limiting: ResponseLimitingConfig = Field(default_factory=ResponseLimitingConfig)
