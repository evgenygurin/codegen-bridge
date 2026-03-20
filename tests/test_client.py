"""Tests for Codegen API client."""

from __future__ import annotations

import httpx
import pytest
import respx
from httpx import Response

from bridge.client import (
    NO_RETRY,
    AuthenticationError,
    CodegenAPIError,
    CodegenClient,
    NotFoundError,
    RateLimitError,
    RetryConfig,
    ServerError,
    ValidationError,
    _classify_error,
    _compute_delay,
    _extract_detail,
    _is_retryable_exception,
    _parse_retry_after,
)


@pytest.fixture(autouse=True)
def _force_test_env(monkeypatch):
    """Ensure test env vars override real ones."""
    monkeypatch.setenv("CODEGEN_API_KEY", "test-key")
    monkeypatch.setenv("CODEGEN_ORG_ID", "42")


# ── Client Init ────────────────────────────────────────────────


class TestClientInit:
    def test_creates_with_credentials(self):
        client = CodegenClient(api_key="test-key", org_id=42)
        assert client.org_id == 42

    def test_raises_without_api_key(self):
        with pytest.raises(ValueError, match="api_key"):
            CodegenClient(api_key="", org_id=42)

    def test_raises_without_org_id(self):
        with pytest.raises(ValueError, match="org_id"):
            CodegenClient(api_key="test-key", org_id=0)

    def test_uses_default_retry_config(self):
        client = CodegenClient(api_key="test-key", org_id=42)
        assert client._retry.max_retries == 3
        assert client._retry.backoff_base == 0.5

    def test_accepts_custom_retry_config(self):
        cfg = RetryConfig(max_retries=5, backoff_base=1.0)
        client = CodegenClient(api_key="test-key", org_id=42, retry=cfg)
        assert client._retry.max_retries == 5
        assert client._retry.backoff_base == 1.0

    def test_accepts_no_retry(self):
        client = CodegenClient(api_key="test-key", org_id=42, retry=NO_RETRY)
        assert client._retry.max_retries == 0

    def test_uses_structured_timeout(self):
        client = CodegenClient(api_key="test-key", org_id=42)
        timeout = client._client.timeout
        assert timeout.connect == 5.0
        assert timeout.read == 30.0
        assert timeout.write == 30.0
        assert timeout.pool == 10.0

    def test_accepts_custom_timeout(self):
        custom_timeout = httpx.Timeout(60.0)
        client = CodegenClient(api_key="test-key", org_id=42, timeout=custom_timeout)
        assert client._client.timeout.read == 60.0


# ── Error Hierarchy ─────────────────────────────────────────────


class TestErrorHierarchy:
    """Verify custom exceptions are backward-compatible with httpx.HTTPStatusError."""

    def _make_error(self, status: int, body: dict | None = None) -> CodegenAPIError:
        """Helper to build a classified error from a status code."""
        req = httpx.Request("GET", "https://api.codegen.com/v1/test")
        resp = httpx.Response(status, request=req, json=body or {})
        return _classify_error(request=req, response=resp, detail=None, request_id="abc123")

    def test_base_inherits_from_httpx_status_error(self):
        err = self._make_error(400)
        assert isinstance(err, httpx.HTTPStatusError)
        assert isinstance(err, CodegenAPIError)

    def test_401_is_authentication_error(self):
        err = self._make_error(401)
        assert isinstance(err, AuthenticationError)
        assert isinstance(err, httpx.HTTPStatusError)
        assert err.status_code == 401

    def test_403_is_authentication_error(self):
        err = self._make_error(403)
        assert isinstance(err, AuthenticationError)
        assert err.status_code == 403

    def test_404_is_not_found_error(self):
        err = self._make_error(404)
        assert isinstance(err, NotFoundError)
        assert err.status_code == 404

    def test_422_is_validation_error(self):
        err = self._make_error(422)
        assert isinstance(err, ValidationError)
        assert err.status_code == 422

    def test_429_is_rate_limit_error(self):
        req = httpx.Request("GET", "https://api.codegen.com/v1/test")
        resp = httpx.Response(429, request=req, json={}, headers={"Retry-After": "5"})
        err = _classify_error(request=req, response=resp, detail=None, request_id="abc")
        assert isinstance(err, RateLimitError)
        assert err.retry_after == 5.0

    def test_500_is_server_error(self):
        err = self._make_error(500)
        assert isinstance(err, ServerError)
        assert err.status_code == 500

    def test_502_is_server_error(self):
        err = self._make_error(502)
        assert isinstance(err, ServerError)

    def test_unknown_4xx_is_base_codegen_error(self):
        err = self._make_error(418)
        assert type(err) is CodegenAPIError
        assert err.status_code == 418

    def test_error_has_request_id(self):
        err = self._make_error(500)
        assert err.request_id == "abc123"

    def test_error_str_includes_status(self):
        err = self._make_error(500)
        assert "500" in str(err)

    def test_error_repr(self):
        err = self._make_error(500)
        assert "ServerError" in repr(err)
        assert "abc123" in repr(err)


# ── Detail Extraction ───────────────────────────────────────────


class TestExtractDetail:
    def test_extracts_detail_field(self):
        resp = httpx.Response(422, json={"detail": "Invalid input"})
        assert _extract_detail(resp) == "Invalid input"

    def test_extracts_error_field(self):
        resp = httpx.Response(500, json={"error": "Internal error"})
        assert _extract_detail(resp) == "Internal error"

    def test_extracts_message_field(self):
        resp = httpx.Response(400, json={"message": "Bad request"})
        assert _extract_detail(resp) == "Bad request"

    def test_extracts_fastapi_validation_detail(self):
        resp = httpx.Response(422, json={"detail": [{"msg": "field required", "type": "missing"}]})
        assert _extract_detail(resp) == "field required"

    def test_extracts_first_item_from_list(self):
        resp = httpx.Response(422, json={"detail": ["first error", "second"]})
        assert _extract_detail(resp) == "first error"

    def test_returns_none_for_non_json(self):
        resp = httpx.Response(500, text="Server error")
        assert _extract_detail(resp) is None

    def test_returns_none_for_empty_dict(self):
        resp = httpx.Response(400, json={})
        assert _extract_detail(resp) is None


# ── Retry After Parsing ─────────────────────────────────────────


class TestParseRetryAfter:
    def test_parses_integer(self):
        resp = httpx.Response(429, headers={"Retry-After": "10"})
        assert _parse_retry_after(resp) == 10.0

    def test_parses_float(self):
        resp = httpx.Response(429, headers={"Retry-After": "1.5"})
        assert _parse_retry_after(resp) == 1.5

    def test_returns_none_for_missing(self):
        resp = httpx.Response(429)
        assert _parse_retry_after(resp) is None

    def test_returns_none_for_invalid(self):
        resp = httpx.Response(429, headers={"Retry-After": "not-a-number"})
        assert _parse_retry_after(resp) is None


# ── Backoff Calculation ──────────────────────────────────────────


class TestComputeDelay:
    def test_exponential_backoff(self):
        cfg = RetryConfig(backoff_base=1.0, jitter=0.0)
        assert _compute_delay(0, cfg) == 1.0
        assert _compute_delay(1, cfg) == 2.0
        assert _compute_delay(2, cfg) == 4.0

    def test_caps_at_backoff_max(self):
        cfg = RetryConfig(backoff_base=1.0, backoff_max=5.0, jitter=0.0)
        assert _compute_delay(10, cfg) == 5.0

    def test_adds_jitter(self):
        cfg = RetryConfig(backoff_base=1.0, jitter=0.5)
        delays = {_compute_delay(0, cfg) for _ in range(100)}
        # With jitter, we should get some variation
        assert len(delays) > 1
        assert all(1.0 <= d <= 1.5 for d in delays)


# ── Retryable Exception Check ───────────────────────────────────


class TestIsRetryableException:
    def test_timeout_retryable_by_default(self):
        exc = httpx.ReadTimeout("timeout")
        assert _is_retryable_exception(exc, RetryConfig()) is True

    def test_connect_error_retryable_by_default(self):
        exc = httpx.ConnectError("refused")
        assert _is_retryable_exception(exc, RetryConfig()) is True

    def test_timeout_not_retryable_when_disabled(self):
        exc = httpx.ReadTimeout("timeout")
        cfg = RetryConfig(retry_on_timeout=False)
        assert _is_retryable_exception(exc, cfg) is False

    def test_connect_error_not_retryable_when_disabled(self):
        exc = httpx.ConnectError("refused")
        cfg = RetryConfig(retry_on_connect_error=False)
        assert _is_retryable_exception(exc, cfg) is False

    def test_generic_exception_not_retryable(self):
        exc = ValueError("bad")
        assert _is_retryable_exception(exc, RetryConfig()) is False


# ── RetryConfig ─────────────────────────────────────────────────


class TestRetryConfig:
    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_retries == 3
        assert cfg.backoff_base == 0.5
        assert cfg.backoff_max == 30.0
        assert cfg.jitter == 0.25
        assert 429 in cfg.retryable_status_codes
        assert 500 in cfg.retryable_status_codes
        assert 502 in cfg.retryable_status_codes
        assert cfg.retry_on_timeout is True
        assert cfg.retry_on_connect_error is True

    def test_is_frozen(self):
        cfg = RetryConfig()
        with pytest.raises(AttributeError):
            cfg.max_retries = 5  # type: ignore[misc]

    def test_no_retry_preset(self):
        assert NO_RETRY.max_retries == 0


# ── _request_json Helper ────────────────────────────────────────


class TestRequestJson:
    """Verify the unified _request_json helper."""

    @respx.mock
    async def test_returns_json_dict(self):
        respx.get("https://api.codegen.com/v1/test-path").mock(
            return_value=Response(200, json={"key": "value", "num": 42})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            result = await client._request_json("GET", "/test-path")

        assert result == {"key": "value", "num": 42}

    @respx.mock
    async def test_forwards_json_body(self):
        route = respx.post("https://api.codegen.com/v1/test-path").mock(
            return_value=Response(200, json={"created": True})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            result = await client._request_json("POST", "/test-path", json_body={"name": "test"})

        assert result == {"created": True}
        assert b"name" in route.calls[0].request.content

    @respx.mock
    async def test_forwards_params(self):
        route = respx.get("https://api.codegen.com/v1/test-path").mock(
            return_value=Response(200, json={"items": []})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            await client._request_json("GET", "/test-path", params={"page": 2})

        assert route.calls[0].request.url.params["page"] == "2"

    @respx.mock
    async def test_raises_on_error_status(self):
        respx.get("https://api.codegen.com/v1/test-path").mock(
            return_value=Response(404, json={"detail": "Not found"})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            with pytest.raises(NotFoundError):
                await client._request_json("GET", "/test-path")


# ── Retry Behavior (Integration) ────────────────────────────────


class TestRetryBehavior:
    """Test actual retry behavior with respx mocks."""

    @respx.mock
    async def test_retries_on_500_then_succeeds(self):
        route = respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1")
        route.side_effect = [
            Response(500, json={"error": "Internal server error"}),
            Response(200, json={"id": 1, "status": "running"}),
        ]

        retry = RetryConfig(max_retries=2, backoff_base=0.01, jitter=0.0)
        async with CodegenClient(api_key="test", org_id=42, retry=retry) as client:
            run = await client.get_run(1)

        assert run.id == 1
        assert route.call_count == 2

    @respx.mock
    async def test_retries_on_502_then_succeeds(self):
        route = respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1")
        route.side_effect = [
            Response(502, json={"error": "Bad gateway"}),
            Response(502, json={"error": "Bad gateway"}),
            Response(200, json={"id": 1, "status": "completed"}),
        ]

        retry = RetryConfig(max_retries=3, backoff_base=0.01, jitter=0.0)
        async with CodegenClient(api_key="test", org_id=42, retry=retry) as client:
            run = await client.get_run(1)

        assert run.status == "completed"
        assert route.call_count == 3

    @respx.mock
    async def test_raises_after_max_retries_exhausted(self):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1").mock(
            return_value=Response(500, json={"error": "Always fails"})
        )

        retry = RetryConfig(max_retries=2, backoff_base=0.01, jitter=0.0)
        async with CodegenClient(api_key="test", org_id=42, retry=retry) as client:
            with pytest.raises(ServerError) as exc_info:
                await client.get_run(1)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Always fails"

    @respx.mock
    async def test_does_not_retry_on_404(self):
        route = respx.get("https://api.codegen.com/v1/organizations/42/agent/run/999")
        route.mock(return_value=Response(404, json={"detail": "Not found"}))

        retry = RetryConfig(max_retries=3, backoff_base=0.01, jitter=0.0)
        async with CodegenClient(api_key="test", org_id=42, retry=retry) as client:
            with pytest.raises(NotFoundError):
                await client.get_run(999)

        # 404 is not retryable — should only be called once
        assert route.call_count == 1

    @respx.mock
    async def test_does_not_retry_on_401(self):
        route = respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1")
        route.mock(return_value=Response(401, json={"detail": "Unauthorized"}))

        retry = RetryConfig(max_retries=3, backoff_base=0.01, jitter=0.0)
        async with CodegenClient(api_key="test", org_id=42, retry=retry) as client:
            with pytest.raises(AuthenticationError):
                await client.get_run(1)

        assert route.call_count == 1

    @respx.mock
    async def test_does_not_retry_on_422(self):
        route = respx.post("https://api.codegen.com/v1/organizations/42/agent/run")
        route.mock(return_value=Response(422, json={"detail": "Invalid input"}))

        retry = RetryConfig(max_retries=3, backoff_base=0.01, jitter=0.0)
        async with CodegenClient(api_key="test", org_id=42, retry=retry) as client:
            with pytest.raises(ValidationError):
                await client.create_run("test")

        assert route.call_count == 1

    @respx.mock
    async def test_retries_on_429_with_retry_after(self):
        route = respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1")
        route.side_effect = [
            Response(429, json={}, headers={"Retry-After": "0.01"}),
            Response(200, json={"id": 1, "status": "running"}),
        ]

        retry = RetryConfig(max_retries=2, backoff_base=0.01, jitter=0.0)
        async with CodegenClient(api_key="test", org_id=42, retry=retry) as client:
            run = await client.get_run(1)

        assert run.id == 1
        assert route.call_count == 2

    @respx.mock
    async def test_no_retry_when_disabled(self):
        route = respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1")
        route.mock(return_value=Response(500, json={"error": "Fail"}))

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            with pytest.raises(ServerError):
                await client.get_run(1)

        assert route.call_count == 1

    @respx.mock
    async def test_retries_on_timeout_exception(self):
        route = respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1")
        route.side_effect = [
            httpx.ReadTimeout("read timeout"),
            Response(200, json={"id": 1, "status": "running"}),
        ]

        retry = RetryConfig(max_retries=2, backoff_base=0.01, jitter=0.0)
        async with CodegenClient(api_key="test", org_id=42, retry=retry) as client:
            run = await client.get_run(1)

        assert run.id == 1
        assert route.call_count == 2

    @respx.mock
    async def test_raises_timeout_after_exhausted_retries(self):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1").mock(
            side_effect=httpx.ReadTimeout("always times out")
        )

        retry = RetryConfig(max_retries=1, backoff_base=0.01, jitter=0.0)
        async with CodegenClient(api_key="test", org_id=42, retry=retry) as client:
            with pytest.raises(httpx.ReadTimeout):
                await client.get_run(1)

    @respx.mock
    async def test_retries_on_connect_error(self):
        route = respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1")
        route.side_effect = [
            httpx.ConnectError("Connection refused"),
            Response(200, json={"id": 1, "status": "running"}),
        ]

        retry = RetryConfig(max_retries=2, backoff_base=0.01, jitter=0.0)
        async with CodegenClient(api_key="test", org_id=42, retry=retry) as client:
            run = await client.get_run(1)

        assert run.id == 1
        assert route.call_count == 2


# ── Error Normalization in API Methods ───────────────────────────


class TestErrorNormalization:
    """Test that API methods raise normalized errors."""

    @respx.mock
    async def test_get_run_raises_not_found(self):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/999").mock(
            return_value=Response(404, json={"detail": "Run not found"})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.get_run(999)

        assert exc_info.value.detail == "Run not found"
        assert exc_info.value.status_code == 404
        assert exc_info.value.request_id is not None

    @respx.mock
    async def test_create_run_raises_validation_error(self):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(422, json={"detail": "prompt is required"})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.create_run("test")

        assert exc_info.value.status_code == 422

    @respx.mock
    async def test_list_runs_raises_auth_error(self):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/runs").mock(
            return_value=Response(401, json={"detail": "Invalid token"})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            with pytest.raises(AuthenticationError):
                await client.list_runs()

    @respx.mock
    async def test_server_error_preserves_response(self):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1").mock(
            return_value=Response(503, json={"error": "Service unavailable"})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            with pytest.raises(ServerError) as exc_info:
                await client.get_run(1)

        # The response object is preserved for inspection
        assert exc_info.value.response.status_code == 503
        assert exc_info.value.detail == "Service unavailable"


# ── Request ID Tracking ──────────────────────────────────────────


class TestRequestIdTracking:
    @respx.mock
    async def test_sends_request_id_header(self):
        route = respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1").mock(
            return_value=Response(200, json={"id": 1, "status": "running"})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            await client.get_run(1)

        assert route.called
        request_id = route.calls[0].request.headers.get("x-request-id")
        assert request_id is not None
        assert len(request_id) == 12  # uuid hex[:12]

    @respx.mock
    async def test_error_includes_request_id(self):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/999").mock(
            return_value=Response(404, json={"detail": "Not found"})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.get_run(999)

        assert exc_info.value.request_id is not None
        assert len(exc_info.value.request_id) == 12


# ── Backward Compatibility ──────────────────────────────────────


class TestBackwardCompatibility:
    """Verify errors can still be caught with httpx.HTTPStatusError."""

    @respx.mock
    async def test_codegen_error_caught_as_httpx_status_error(self):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1").mock(
            return_value=Response(500, json={"error": "Internal"})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_run(1)

    @respx.mock
    async def test_not_found_caught_as_httpx_status_error(self):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/999").mock(
            return_value=Response(404, json={"detail": "Not found"})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_run(999)


# ── Original API Method Tests (preserved) ────────────────────────


class TestCreateRun:
    @respx.mock
    async def test_creates_run_with_prompt(self):
        route = respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(
                200, json={"id": 1, "status": "queued", "web_url": "https://codegen.com/run/1"}
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            run = await client.create_run("Fix the bug")

        assert run.id == 1
        assert run.status == "queued"
        assert route.called

    @respx.mock
    async def test_creates_run_with_all_params(self):
        route = respx.post("https://api.codegen.com/v1/organizations/42/agent/run").mock(
            return_value=Response(200, json={"id": 2, "status": "queued"})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            run = await client.create_run(
                "Refactor auth",
                repo_id=10,
                model="claude-sonnet-4-6",
                agent_type="claude_code",
                metadata={"plan_task": "Task 3"},
            )

        assert run.id == 2
        body = route.calls[0].request.content
        assert b"repo_id" in body


class TestGetRun:
    @respx.mock
    async def test_gets_run_by_id(self):
        respx.get("https://api.codegen.com/v1/organizations/42/agent/run/1").mock(
            return_value=Response(
                200,
                json={
                    "id": 1,
                    "status": "completed",
                    "summary": "Fixed the bug",
                    "github_pull_requests": [
                        {
                            "url": "https://github.com/org/repo/pull/5",
                            "number": 5,
                        }
                    ],
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            run = await client.get_run(1)

        assert run.status == "completed"
        assert run.github_pull_requests[0].number == 5


class TestGetLogs:
    @respx.mock
    async def test_gets_logs(self):
        respx.get("https://api.codegen.com/v1/alpha/organizations/42/agent/run/1/logs").mock(
            return_value=Response(
                200,
                json={
                    "id": 1,
                    "status": "running",
                    "logs": [
                        {
                            "agent_run_id": 1,
                            "thought": "Analyzing code",
                            "tool_name": "read_file",
                        }
                    ],
                    "total_logs": 1,
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.get_logs(1)

        assert len(result.logs) == 1
        assert result.logs[0].thought == "Analyzing code"


class TestStopRun:
    @respx.mock
    async def test_stops_run(self):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run/ban").mock(
            return_value=Response(200, json={"id": 1, "status": "stopped"})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.stop_run(1)

        # stop_run accepts both AgentRun-like and action-style payloads
        assert result.id == 1
        assert result.status == "stopped"

    @respx.mock
    async def test_stops_run_with_action_payload(self):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run/ban").mock(
            return_value=Response(
                200,
                json={"status": "success", "message": "Run stopped", "agent_run_id": 7},
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.stop_run(7)

        assert result.id is None
        assert result.agent_run_id == 7
        assert result.status == "success"


class TestBanRun:
    @respx.mock
    async def test_bans_run(self):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run/ban").mock(
            return_value=Response(200, json={"message": "Banned"})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.ban_run(1)

        assert result.message == "Banned"


class TestUnbanRun:
    @respx.mock
    async def test_unbans_run(self):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run/unban").mock(
            return_value=Response(200, json={})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.unban_run(1)

        assert result.message is None


class TestRemoveFromPr:
    @respx.mock
    async def test_removes_from_pr(self):
        respx.post("https://api.codegen.com/v1/organizations/42/agent/run/remove-from-pr").mock(
            return_value=Response(200, json={"message": "Removed"})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.remove_from_pr(1)

        assert result.message == "Removed"


class TestGetOrganizationSettings:
    @respx.mock
    async def test_returns_settings(self):
        respx.get("https://api.codegen.com/v1/organizations/42/settings").mock(
            return_value=Response(
                200,
                json={
                    "enable_pr_creation": True,
                    "enable_rules_detection": False,
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            settings = await client.get_organization_settings()

        assert settings.enable_pr_creation is True
        assert settings.enable_rules_detection is False

    @respx.mock
    async def test_returns_defaults(self):
        respx.get("https://api.codegen.com/v1/organizations/42/settings").mock(
            return_value=Response(200, json={})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            settings = await client.get_organization_settings()

        assert settings.enable_pr_creation is True
        assert settings.enable_rules_detection is True

    @respx.mock
    async def test_falls_back_to_organizations_list_on_404(self):
        respx.get("https://api.codegen.com/v1/organizations/42/settings").mock(
            return_value=Response(404, json={"detail": "Not Found"})
        )
        respx.get("https://api.codegen.com/v1/organizations").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": 42,
                            "name": "acme",
                            "settings": {
                                "enable_pr_creation": False,
                                "enable_rules_detection": True,
                            },
                        }
                    ],
                    "total": 1,
                    "page": 1,
                    "size": 20,
                    "pages": 1,
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            settings = await client.get_organization_settings()

        assert settings.enable_pr_creation is False
        assert settings.enable_rules_detection is True

    @respx.mock
    async def test_fallback_returns_defaults_when_org_settings_missing(self):
        respx.get("https://api.codegen.com/v1/organizations/42/settings").mock(
            return_value=Response(404, json={"detail": "Not Found"})
        )
        respx.get("https://api.codegen.com/v1/organizations").mock(
            return_value=Response(
                200,
                json={
                    "items": [{"id": 42, "name": "acme"}],
                    "total": 1,
                    "page": 1,
                    "size": 20,
                    "pages": 1,
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            settings = await client.get_organization_settings()

        assert settings.enable_pr_creation is True
        assert settings.enable_rules_detection is True


class TestListRepos:
    @respx.mock
    async def test_lists_repos(self):
        respx.get("https://api.codegen.com/v1/organizations/42/repos").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": 10,
                            "name": "myrepo",
                            "full_name": "org/myrepo",
                            "language": "Python",
                        }
                    ],
                    "total": 1,
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            repos = await client.list_repos()

        assert repos.items[0].full_name == "org/myrepo"


class TestGetMCPProviders:
    @respx.mock
    async def test_returns_providers(self):
        respx.get("https://api.codegen.com/v1/mcp-providers").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "github",
                        "issuer": "https://github.com",
                        "authorization_endpoint": "https://github.com/login/oauth/authorize",
                        "token_endpoint": "https://github.com/login/oauth/access_token",
                        "default_scopes": ["repo", "read:org"],
                        "is_mcp": True,
                        "meta": {"docs": "https://docs.github.com"},
                    },
                    {
                        "id": 2,
                        "name": "linear",
                        "issuer": "https://linear.app",
                        "authorization_endpoint": "https://linear.app/oauth/authorize",
                        "token_endpoint": "https://api.linear.app/oauth/token",
                        "default_scopes": ["read"],
                        "is_mcp": True,
                    },
                ],
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            providers = await client.get_mcp_providers()

        assert len(providers) == 2
        assert providers[0].name == "github"
        assert providers[0].issuer == "https://github.com"
        assert providers[0].default_scopes == ["repo", "read:org"]
        assert providers[0].meta == {"docs": "https://docs.github.com"}
        assert providers[1].name == "linear"
        assert providers[1].is_mcp is True

    @respx.mock
    async def test_returns_empty_list(self):
        respx.get("https://api.codegen.com/v1/mcp-providers").mock(
            return_value=Response(200, json=[])
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            providers = await client.get_mcp_providers()

        assert providers == []


class TestGetOAuthStatus:
    @respx.mock
    async def test_returns_connected_providers_as_strings(self):
        respx.get("https://api.codegen.com/v1/oauth/tokens/status").mock(
            return_value=Response(200, json=["github", "linear"])
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            statuses = await client.get_oauth_status()

        assert len(statuses) == 2
        assert statuses[0].provider == "github"
        assert statuses[0].active is True
        assert statuses[1].provider == "linear"

    @respx.mock
    async def test_returns_connected_providers_as_dicts(self):
        respx.get("https://api.codegen.com/v1/oauth/tokens/status").mock(
            return_value=Response(
                200,
                json=[
                    {"provider": "github", "active": True},
                    {"provider": "slack", "active": False},
                ],
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            statuses = await client.get_oauth_status()

        assert len(statuses) == 2
        assert statuses[0].provider == "github"
        assert statuses[0].active is True
        assert statuses[1].provider == "slack"
        assert statuses[1].active is False

    @respx.mock
    async def test_passes_org_id_query_param(self):
        route = respx.get("https://api.codegen.com/v1/oauth/tokens/status").mock(
            return_value=Response(200, json=[])
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            await client.get_oauth_status()

        assert route.called
        assert route.calls[0].request.url.params["org_id"] == "42"

    @respx.mock
    async def test_returns_empty_list(self):
        respx.get("https://api.codegen.com/v1/oauth/tokens/status").mock(
            return_value=Response(200, json=[])
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            statuses = await client.get_oauth_status()

        assert statuses == []


class TestRevokeOAuth:
    @respx.mock
    async def test_revokes_token(self):
        route = respx.post("https://api.codegen.com/v1/oauth/tokens/revoke").mock(
            return_value=Response(200, json={"status": "revoked"})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            await client.revoke_oauth("github")

        assert route.called
        assert route.calls[0].request.url.params["provider"] == "github"
        assert route.calls[0].request.url.params["org_id"] == "42"

    @respx.mock
    async def test_raises_on_error(self):
        import httpx as _httpx

        respx.post("https://api.codegen.com/v1/oauth/tokens/revoke").mock(
            return_value=Response(422, json={"detail": "Invalid provider"})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            with pytest.raises(_httpx.HTTPStatusError):
                await client.revoke_oauth("nonexistent")

    @respx.mock
    async def test_raises_validation_error_on_422(self):
        respx.post("https://api.codegen.com/v1/oauth/tokens/revoke").mock(
            return_value=Response(422, json={"detail": "Invalid provider"})
        )

        async with CodegenClient(api_key="test", org_id=42, retry=NO_RETRY) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.revoke_oauth("nonexistent")

        assert exc_info.value.detail == "Invalid provider"


class TestGetRules:
    @respx.mock
    async def test_gets_org_rules(self):
        respx.get("https://api.codegen.com/v1/organizations/42/cli/rules").mock(
            return_value=Response(
                200,
                json={
                    "organization_rules": "Use conventional commits\nAdd type hints",
                    "user_custom_prompt": "Prefer pytest over unittest",
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            rules = await client.get_rules()

        assert "conventional commits" in rules["organization_rules"]


class TestGetIntegrations:
    @respx.mock
    async def test_gets_integrations(self):
        respx.get("https://api.codegen.com/v1/organizations/42/integrations").mock(
            return_value=Response(
                200,
                json={
                    "organization_id": 42,
                    "organization_name": "My Org",
                    "integrations": [
                        {
                            "integration_type": "github",
                            "active": True,
                            "installation_id": 100,
                        },
                        {
                            "integration_type": "slack",
                            "active": False,
                            "token_id": 200,
                        },
                    ],
                    "total_active_integrations": 1,
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.get_integrations()

        assert result.organization_id == 42
        assert result.total_active_integrations == 1
        assert len(result.integrations) == 2
        assert result.integrations[0].integration_type == "github"
        assert result.integrations[0].active is True
        assert result.integrations[1].active is False


class TestWebhookConfig:
    @respx.mock
    async def test_gets_webhook_config(self):
        respx.get("https://api.codegen.com/v1/organizations/42/webhooks/agent-run").mock(
            return_value=Response(
                200,
                json={"url": "https://example.com/hook", "enabled": True, "has_secret": True},
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            config = await client.get_webhook_config()

        assert config.url == "https://example.com/hook"
        assert config.enabled is True
        assert config.has_secret is True

    @respx.mock
    async def test_sets_webhook_config(self):
        route = respx.post("https://api.codegen.com/v1/organizations/42/webhooks/agent-run").mock(
            return_value=Response(200, json={"status": "ok"})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.set_webhook_config(
                "https://example.com/hook", secret="s3cret", enabled=True
            )

        assert result["status"] == "ok"
        body = route.calls[0].request.content
        assert b"https://example.com/hook" in body
        assert b"s3cret" in body

    @respx.mock
    async def test_deletes_webhook_config(self):
        respx.delete("https://api.codegen.com/v1/organizations/42/webhooks/agent-run").mock(
            return_value=Response(200, json={"status": "deleted"})
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.delete_webhook_config()

        assert result["status"] == "deleted"

    @respx.mock
    async def test_tests_webhook(self):
        route = respx.post(
            "https://api.codegen.com/v1/organizations/42/webhooks/agent-run/test"
        ).mock(return_value=Response(200, json={"status": "sent"}))

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.test_webhook("https://example.com/hook")

        assert result["status"] == "sent"
        assert route.called


class TestGenerateSetupCommands:
    @respx.mock
    async def test_generates_setup_commands(self):
        route = respx.post(
            "https://api.codegen.com/v1/organizations/42/setup-commands/generate"
        ).mock(
            return_value=Response(
                200,
                json={
                    "agent_run_id": 99,
                    "status": "queued",
                    "url": "https://codegen.com/run/99",
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.generate_setup_commands(10, prompt="Custom setup")

        assert result.agent_run_id == 99
        assert result.status == "queued"
        body = route.calls[0].request.content
        assert b"repo_id" in body

    @respx.mock
    async def test_generates_setup_commands_minimal(self):
        respx.post("https://api.codegen.com/v1/organizations/42/setup-commands/generate").mock(
            return_value=Response(
                200,
                json={
                    "agent_run_id": 100,
                    "status": "queued",
                    "url": "https://codegen.com/run/100",
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.generate_setup_commands(10)

        assert result.agent_run_id == 100


class TestAnalyzeSandboxLogs:
    @respx.mock
    async def test_analyzes_sandbox_logs(self):
        respx.post("https://api.codegen.com/v1/organizations/42/sandbox/55/analyze-logs").mock(
            return_value=Response(
                200,
                json={
                    "agent_run_id": 77,
                    "status": "queued",
                    "message": "Analysis started",
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.analyze_sandbox_logs(55)

        assert result.agent_run_id == 77
        assert result.status == "queued"
        assert result.message == "Analysis started"


class TestGetCheckSuiteSettings:
    @respx.mock
    async def test_gets_check_suite_settings(self):
        respx.get("https://api.codegen.com/v1/organizations/42/repos/check-suite-settings").mock(
            return_value=Response(
                200,
                json={
                    "check_retry_count": 3,
                    "ignored_checks": ["lint"],
                    "check_retry_counts": {"ci": 2},
                    "custom_prompts": {"ci": "Fix CI"},
                    "high_priority_apps": ["GitHub Actions"],
                    "available_check_suite_names": ["ci", "lint", "test"],
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            settings = await client.get_check_suite_settings(10)

        assert settings.check_retry_count == 3
        assert settings.ignored_checks == ["lint"]
        assert settings.check_retry_counts == {"ci": 2}
        assert settings.custom_prompts == {"ci": "Fix CI"}
        assert settings.high_priority_apps == ["GitHub Actions"]
        assert settings.available_check_suite_names == ["ci", "lint", "test"]

    @respx.mock
    async def test_passes_repo_id_query_param(self):
        route = respx.get(
            "https://api.codegen.com/v1/organizations/42/repos/check-suite-settings"
        ).mock(
            return_value=Response(
                200,
                json={
                    "check_retry_count": 0,
                    "ignored_checks": [],
                    "check_retry_counts": {},
                    "custom_prompts": {},
                    "high_priority_apps": [],
                    "available_check_suite_names": [],
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            await client.get_check_suite_settings(10)

        assert route.called
        assert route.calls[0].request.url.params["repo_id"] == "10"


class TestUpdateCheckSuiteSettings:
    @respx.mock
    async def test_updates_settings(self):
        route = respx.put(
            "https://api.codegen.com/v1/organizations/42/repos/check-suite-settings"
        ).mock(return_value=Response(200, json={"status": "ok"}))

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.update_check_suite_settings(
                10, {"check_retry_count": 5, "ignored_checks": ["lint"]}
            )

        assert result["status"] == "ok"
        assert route.called
        assert route.calls[0].request.url.params["repo_id"] == "10"
        body = route.calls[0].request.content
        assert b"check_retry_count" in body
        assert b"ignored_checks" in body

    @respx.mock
    async def test_updates_with_empty_body(self):
        route = respx.put(
            "https://api.codegen.com/v1/organizations/42/repos/check-suite-settings"
        ).mock(return_value=Response(200, json={"status": "ok"}))

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.update_check_suite_settings(10, {})

        assert result["status"] == "ok"
        assert route.called


class TestGenerateSlackConnectToken:
    @respx.mock
    async def test_generates_slack_token(self):
        route = respx.post("https://api.codegen.com/v1/slack-connect/generate-token").mock(
            return_value=Response(
                200,
                json={
                    "token": "abc123",
                    "message": "Send this to the bot",
                    "expires_in_minutes": 10,
                },
            )
        )

        async with CodegenClient(api_key="test", org_id=42) as client:
            result = await client.generate_slack_connect_token()

        assert result.token == "abc123"
        assert result.expires_in_minutes == 10
        body = route.calls[0].request.content
        assert b"org_id" in body
