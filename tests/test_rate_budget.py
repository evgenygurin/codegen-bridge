"""Tests for outbound rate budget (token-bucket rate limiter)."""

from __future__ import annotations

import asyncio
import time

import pytest

from bridge.rate_budget import (
    DEFAULT_RATE_BUDGET,
    OutboundRateBudget,
    RateBudgetConfig,
    RateBudgetExhaustedError,
)

# ── Config ──────────────────────────────────────────────────────


class TestRateBudgetConfig:
    def test_default_values(self):
        cfg = RateBudgetConfig()
        assert cfg.max_tokens == 60
        assert cfg.refill_rate == 1.0
        assert cfg.max_wait == 30.0

    def test_custom_values(self):
        cfg = RateBudgetConfig(max_tokens=10, refill_rate=2.0, max_wait=5.0)
        assert cfg.max_tokens == 10
        assert cfg.refill_rate == 2.0
        assert cfg.max_wait == 5.0

    def test_is_frozen(self):
        cfg = RateBudgetConfig()
        with pytest.raises(AttributeError):
            cfg.max_tokens = 100  # type: ignore[misc]

    def test_default_constant(self):
        assert DEFAULT_RATE_BUDGET.max_tokens == 60
        assert DEFAULT_RATE_BUDGET.refill_rate == 1.0


# ── Budget Core ─────────────────────────────────────────────────


class TestOutboundRateBudget:
    def test_starts_full(self):
        budget = OutboundRateBudget(RateBudgetConfig(max_tokens=10))
        assert budget.available == pytest.approx(10.0, abs=0.5)

    async def test_acquire_consumes_token(self):
        budget = OutboundRateBudget(RateBudgetConfig(max_tokens=10, refill_rate=0.0))
        initial = budget.available
        await budget.acquire()
        assert budget.available < initial

    async def test_acquire_multiple(self):
        budget = OutboundRateBudget(RateBudgetConfig(max_tokens=5, refill_rate=0.0))
        for _ in range(5):
            await budget.acquire()
        assert budget.available == pytest.approx(0.0, abs=0.1)

    async def test_acquire_blocks_when_empty(self):
        """When empty, acquire() should sleep until refilled."""
        budget = OutboundRateBudget(
            RateBudgetConfig(max_tokens=1, refill_rate=100.0, max_wait=5.0)
        )
        # Drain the bucket
        await budget.acquire()

        # Next acquire should need to wait (but refill is fast → brief wait)
        start = time.monotonic()
        await budget.acquire()
        elapsed = time.monotonic() - start
        # With refill_rate=100/s, wait should be ~0.01s
        assert elapsed < 1.0

    async def test_acquire_raises_when_max_wait_exceeded(self):
        budget = OutboundRateBudget(
            RateBudgetConfig(max_tokens=1, refill_rate=0.01, max_wait=0.01)
        )
        # Drain
        await budget.acquire()

        # Need 1/0.01 = 100s to refill, but max_wait=0.01s
        with pytest.raises(RateBudgetExhaustedError) as exc_info:
            await budget.acquire()
        assert exc_info.value.max_wait == 0.01

    async def test_acquire_raises_with_zero_refill_rate(self):
        budget = OutboundRateBudget(RateBudgetConfig(max_tokens=1, refill_rate=0.0, max_wait=1.0))
        await budget.acquire()

        with pytest.raises(RateBudgetExhaustedError):
            await budget.acquire()

    async def test_refill_over_time(self):
        budget = OutboundRateBudget(RateBudgetConfig(max_tokens=10, refill_rate=1000.0))
        # Drain 5 tokens
        for _ in range(5):
            await budget.acquire()

        # Small sleep → tokens refill at 1000/s
        await asyncio.sleep(0.01)

        # Should have refilled some tokens
        assert budget.available > 0

    def test_refill_caps_at_max(self):
        budget = OutboundRateBudget(RateBudgetConfig(max_tokens=5, refill_rate=1000.0))
        # Even with massive refill rate, should not exceed max_tokens
        import time as _time

        budget._last_refill = _time.monotonic() - 100  # pretend 100s passed
        budget._refill()
        assert budget._tokens <= 5.0

    async def test_custom_cost(self):
        budget = OutboundRateBudget(RateBudgetConfig(max_tokens=10, refill_rate=0.0))
        await budget.acquire(cost=5)
        assert budget.available == pytest.approx(5.0, abs=0.1)
        await budget.acquire(cost=5)
        assert budget.available == pytest.approx(0.0, abs=0.1)

    def test_default_config(self):
        budget = OutboundRateBudget()
        assert budget._max_tokens == 60
        assert budget._refill_rate == 1.0

    def test_none_config_uses_default(self):
        budget = OutboundRateBudget(None)
        assert budget._max_tokens == 60


# ── Client Integration ──────────────────────────────────────────


class TestClientRateBudget:
    """Test that CodegenClient integrates rate budget correctly."""

    def test_default_creates_budget(self):
        from bridge.client import CodegenClient

        client = CodegenClient(api_key="test-key", org_id=42)
        assert client.rate_budget is not None
        assert client.rate_budget._max_tokens == 60

    def test_false_disables_budget(self):
        from bridge.client import CodegenClient

        client = CodegenClient(api_key="test-key", org_id=42, rate_budget=False)
        assert client.rate_budget is None

    def test_true_creates_default_budget(self):
        from bridge.client import CodegenClient

        client = CodegenClient(api_key="test-key", org_id=42, rate_budget=True)
        assert client.rate_budget is not None
        assert client.rate_budget._max_tokens == 60

    def test_custom_config(self):
        from bridge.client import CodegenClient

        cfg = RateBudgetConfig(max_tokens=10, refill_rate=2.0)
        client = CodegenClient(api_key="test-key", org_id=42, rate_budget=cfg)
        assert client.rate_budget is not None
        assert client.rate_budget._max_tokens == 10
        assert client.rate_budget._refill_rate == 2.0


class TestClientRequestWithBudget:
    """Test that _request() calls acquire() on the rate budget."""

    async def test_request_acquires_budget(self):
        """Each _request() call should acquire from rate budget."""
        import respx
        from httpx import Response

        from bridge.client import NO_RETRY, CodegenClient

        respx.mock.start()
        try:
            respx.get("https://api.codegen.com/v1/test").mock(
                return_value=Response(200, json={"ok": True})
            )

            cfg = RateBudgetConfig(max_tokens=10, refill_rate=0.0)
            async with CodegenClient(
                api_key="test", org_id=42, retry=NO_RETRY, rate_budget=cfg
            ) as client:
                budget = client.rate_budget
                assert budget is not None
                initial = budget.available

                await client._request("GET", "/test")

                # Should have consumed 1 token
                assert budget.available < initial
        finally:
            respx.mock.stop()

    async def test_disabled_budget_skips_acquire(self):
        """When rate_budget=False, requests proceed without throttling."""
        import respx
        from httpx import Response

        from bridge.client import NO_RETRY, CodegenClient

        respx.mock.start()
        try:
            respx.get("https://api.codegen.com/v1/test").mock(
                return_value=Response(200, json={"ok": True})
            )

            async with CodegenClient(
                api_key="test", org_id=42, retry=NO_RETRY, rate_budget=False
            ) as client:
                assert client.rate_budget is None
                # Should not raise — no budget to exhaust
                await client._request("GET", "/test")
        finally:
            respx.mock.stop()

    async def test_retry_attempts_also_consume_budget(self):
        """Each retry attempt should consume a budget token."""
        import respx
        from httpx import Response

        from bridge.client import CodegenClient, RetryConfig

        respx.mock.start()
        try:
            route = respx.get("https://api.codegen.com/v1/test")
            route.side_effect = [
                Response(500, json={"error": "server error"}),
                Response(500, json={"error": "server error"}),
                Response(200, json={"ok": True}),
            ]

            retry = RetryConfig(
                max_retries=2,
                backoff_base=0.01,
                backoff_max=0.02,
                jitter=0.0,
            )
            cfg = RateBudgetConfig(max_tokens=10, refill_rate=0.0)

            async with CodegenClient(
                api_key="test", org_id=42, retry=retry, rate_budget=cfg
            ) as client:
                budget = client.rate_budget
                assert budget is not None

                await client._request("GET", "/test")

                # 3 attempts (1 initial + 2 retries) = 3 tokens consumed
                # Budget started at 10, so ~7 left
                assert budget.available == pytest.approx(7.0, abs=0.5)
        finally:
            respx.mock.stop()


# ── Exception ───────────────────────────────────────────────────


class TestRateBudgetExhaustedError:
    def test_message_format(self):
        exc = RateBudgetExhaustedError(wait_needed=15.0, max_wait=5.0)
        assert "15.0s" in str(exc)
        assert "5.0s" in str(exc)

    def test_attributes(self):
        exc = RateBudgetExhaustedError(wait_needed=10.0, max_wait=2.0)
        assert exc.wait_needed == 10.0
        assert exc.max_wait == 2.0
