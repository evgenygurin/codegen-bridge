"""Outbound rate budget — token-bucket rate limiter for API calls.

Throttles **outgoing** HTTP requests to the Codegen API to proactively
prevent 429 responses.  This is orthogonal to the *inbound*
``RateLimitingMiddleware`` which throttles MCP requests *from* Claude.

The token bucket starts full (``max_tokens``).  Each ``acquire()`` call
consumes one token.  Tokens are refilled at ``refill_rate`` per second.
When the bucket is empty, ``acquire()`` blocks (``asyncio.sleep``) until
a token becomes available or ``max_wait`` is exceeded.

Usage::

    budget = OutboundRateBudget(max_tokens=60, refill_rate=1.0)
    await budget.acquire()   # blocks if budget exhausted
    response = await httpx_client.get(...)

Configuration is encapsulated in the frozen ``RateBudgetConfig`` dataclass
so it can be injected alongside ``RetryConfig``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger("bridge.rate_budget")


@dataclass(frozen=True)
class RateBudgetConfig:
    """Configuration for the outbound rate budget.

    Attributes:
        max_tokens: Maximum burst capacity (bucket size).
        refill_rate: Tokens added per second (sustained throughput).
        max_wait: Maximum seconds ``acquire()`` will block before raising.
            Set to ``0`` to fail immediately when budget is exhausted.
    """

    max_tokens: int = 60
    refill_rate: float = 1.0
    max_wait: float = 30.0


# Sensible default: 60 req burst, 1 req/s sustained = 60 req/min
DEFAULT_RATE_BUDGET = RateBudgetConfig()

# No rate limiting — useful for tests
NO_RATE_BUDGET: RateBudgetConfig | None = None


class RateBudgetExhaustedError(Exception):
    """Raised when ``acquire()`` cannot obtain a token within ``max_wait``."""

    def __init__(self, wait_needed: float, max_wait: float) -> None:
        self.wait_needed = wait_needed
        self.max_wait = max_wait
        super().__init__(
            f"Rate budget exhausted: need {wait_needed:.1f}s wait but max_wait is {max_wait:.1f}s"
        )


class OutboundRateBudget:
    """Token-bucket rate limiter for outgoing API calls.

    Thread-safe for single-event-loop async use (standard asyncio).
    Uses ``time.monotonic()`` for clock-skew resistance.

    Args:
        config: Rate budget configuration. Defaults to 60 burst / 1 per second.
    """

    def __init__(self, config: RateBudgetConfig | None = None) -> None:
        cfg = config or DEFAULT_RATE_BUDGET
        self._max_tokens = cfg.max_tokens
        self._refill_rate = cfg.refill_rate
        self._max_wait = cfg.max_wait
        self._tokens = float(cfg.max_tokens)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        """Add tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(
                self._max_tokens,
                self._tokens + elapsed * self._refill_rate,
            )
            self._last_refill = now

    @property
    def available(self) -> float:
        """Current number of available tokens (may be fractional)."""
        self._refill()
        return self._tokens

    async def acquire(self, cost: int = 1) -> None:
        """Acquire ``cost`` tokens, blocking if necessary.

        If the bucket doesn't have enough tokens, sleeps until tokens
        are refilled.  Raises ``RateBudgetExhaustedError`` if the required
        wait exceeds ``max_wait``.

        Args:
            cost: Number of tokens to consume (default 1).

        Raises:
            RateBudgetExhaustedError: If the wait required exceeds ``max_wait``.
        """
        self._refill()

        if self._tokens >= cost:
            self._tokens -= cost
            return

        # Calculate wait time for enough tokens to refill
        deficit = cost - self._tokens
        if self._refill_rate <= 0:
            raise RateBudgetExhaustedError(float("inf"), self._max_wait)

        wait_needed = deficit / self._refill_rate

        if wait_needed > self._max_wait:
            raise RateBudgetExhaustedError(wait_needed, self._max_wait)

        logger.debug(
            "Rate budget: waiting %.2fs for %d token(s) (%.1f available)",
            wait_needed,
            cost,
            self._tokens,
        )
        await asyncio.sleep(wait_needed)

        # Refill after sleep and consume
        self._refill()
        self._tokens -= cost
