"""Async HTTP client for Codegen REST API v1.

Production-grade client with:
- Structured timeouts (connect / read / write / pool)
- Automatic retries with exponential backoff + jitter
- Outbound rate budget (token-bucket throttling)
- Normalized error hierarchy (``CodegenAPIError`` and subclasses)
- Request ID tracking for debugging

All custom exceptions inherit from ``httpx.HTTPStatusError`` so existing
``except httpx.HTTPStatusError`` blocks continue to work.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from bridge.models import (
    AgentRun,
    AgentRunWithLogs,
    BanActionResponse,
    CheckSuiteSettings,
    EditPRResponse,
    MCPProvider,
    ModelsResponse,
    OAuthTokenStatus,
    Organization,
    OrganizationIntegrations,
    OrganizationSettings,
    Page,
    PRState,
    Repository,
    SandboxLog,
    SetupCommand,
    SlackToken,
    StopRunResponse,
    User,
    WebhookConfig,
)
from bridge.rate_budget import OutboundRateBudget, RateBudgetConfig

logger = logging.getLogger("bridge.client")

BASE_URL = "https://api.codegen.com/v1"

# ── Timeout Defaults ──────────────────────────────────────────────

DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READ_TIMEOUT = 30.0
DEFAULT_WRITE_TIMEOUT = 30.0
DEFAULT_POOL_TIMEOUT = 10.0

# ── Retry Configuration ──────────────────────────────────────────


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for automatic request retries.

    Attributes:
        max_retries: Maximum number of retry attempts (0 = no retries).
        backoff_base: Base delay in seconds for exponential backoff.
        backoff_max: Maximum delay cap in seconds.
        jitter: Maximum random jitter added to each delay (seconds).
        retryable_status_codes: HTTP status codes eligible for retry.
        retry_on_timeout: Whether to retry on timeout exceptions.
        retry_on_connect_error: Whether to retry on connection errors.
    """

    max_retries: int = 3
    backoff_base: float = 0.5
    backoff_max: float = 30.0
    jitter: float = 0.25
    retryable_status_codes: frozenset[int] = field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504})
    )
    retry_on_timeout: bool = True
    retry_on_connect_error: bool = True


# Sensible default: 3 retries with exponential backoff
DEFAULT_RETRY = RetryConfig()

# No retries — useful for tests or latency-sensitive paths
NO_RETRY = RetryConfig(max_retries=0)


# ── Error Hierarchy ──────────────────────────────────────────────


class CodegenAPIError(httpx.HTTPStatusError):
    """Base exception for Codegen API errors.

    Inherits from ``httpx.HTTPStatusError`` for backward compatibility —
    existing ``except httpx.HTTPStatusError`` blocks still catch these.

    Attributes:
        status_code: HTTP status code from the response.
        detail: Human-readable error message extracted from the response body.
        request_id: Correlation ID for the failed request (if available).
    """

    def __init__(
        self,
        message: str,
        *,
        request: httpx.Request,
        response: httpx.Response,
        detail: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message, request=request, response=response)
        self.status_code: int = response.status_code
        self.detail: str | None = detail
        self.request_id: str | None = request_id

    def __str__(self) -> str:
        parts = [f"[{self.status_code}]"]
        if self.detail:
            parts.append(self.detail)
        if self.request_id:
            parts.append(f"(request_id={self.request_id})")
        return " ".join(parts)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(status_code={self.status_code}, "
            f"detail={self.detail!r}, request_id={self.request_id!r})"
        )


class AuthenticationError(CodegenAPIError):
    """Raised on 401 Unauthorized or 403 Forbidden."""


class NotFoundError(CodegenAPIError):
    """Raised on 404 Not Found."""


class ValidationError(CodegenAPIError):
    """Raised on 422 Unprocessable Entity."""


class RateLimitError(CodegenAPIError):
    """Raised on 429 Too Many Requests.

    Attributes:
        retry_after: Seconds to wait before retrying (from ``Retry-After`` header).
    """

    def __init__(
        self,
        message: str,
        *,
        request: httpx.Request,
        response: httpx.Response,
        detail: str | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(
            message,
            request=request,
            response=response,
            detail=detail,
            request_id=request_id,
        )
        self.retry_after: float | None = retry_after


class ServerError(CodegenAPIError):
    """Raised on 5xx Server Error."""


# ── Helpers ──────────────────────────────────────────────────────


def _extract_detail(response: httpx.Response) -> str | None:
    """Best-effort extraction of error detail from a JSON response body."""
    try:
        body = response.json()
    except Exception:
        return None

    if isinstance(body, dict):
        # Common API patterns: {"detail": "..."}, {"error": "..."}, {"message": "..."}
        for key in ("detail", "error", "message"):
            val = body.get(key)
            if isinstance(val, str):
                return val
            # FastAPI validation: {"detail": [{"msg": "...", ...}]}
            if isinstance(val, list) and val:
                first = val[0]
                if isinstance(first, dict) and "msg" in first:
                    return str(first["msg"])
                return str(first)
    return None


def _classify_error(
    *,
    request: httpx.Request,
    response: httpx.Response,
    detail: str | None,
    request_id: str | None,
) -> CodegenAPIError:
    """Map an HTTP status code to the appropriate exception subclass."""
    status = response.status_code
    msg = f"Codegen API error: {response.status_code} {response.reason_phrase}"
    if detail:
        msg = f"{msg} — {detail}"

    kwargs: dict[str, Any] = {
        "request": request,
        "response": response,
        "detail": detail,
        "request_id": request_id,
    }

    if status in {401, 403}:
        return AuthenticationError(msg, **kwargs)
    if status == 404:
        return NotFoundError(msg, **kwargs)
    if status == 422:
        return ValidationError(msg, **kwargs)
    if status == 429:
        retry_after = _parse_retry_after(response)
        return RateLimitError(msg, retry_after=retry_after, **kwargs)
    if 500 <= status < 600:
        return ServerError(msg, **kwargs)
    return CodegenAPIError(msg, **kwargs)


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Parse ``Retry-After`` header value (seconds)."""
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def _compute_delay(attempt: int, config: RetryConfig) -> float:
    """Compute retry delay with exponential backoff and jitter."""
    base_delay: float = config.backoff_base * (2**attempt)
    capped: float = min(base_delay, config.backoff_max)
    jitter: float = random.uniform(0, config.jitter)
    return capped + jitter


def _is_retryable_exception(exc: Exception, config: RetryConfig) -> bool:
    """Check whether an exception is eligible for retry."""
    if isinstance(exc, httpx.TimeoutException):
        return config.retry_on_timeout
    if isinstance(exc, (httpx.ConnectError, httpx.NetworkError)):
        return config.retry_on_connect_error
    return False


# ── Client ───────────────────────────────────────────────────────


class CodegenClient:
    """Async client for Codegen API.

    Args:
        api_key: Bearer token for authentication.
        org_id: Organization ID for API calls.
        base_url: Override API base URL (for testing).
        retry: Retry configuration. Pass ``NO_RETRY`` to disable retries.
        rate_budget: Outbound rate limiting.  ``None``/``True`` → default
            (60 burst, 1/s sustained).  ``False`` → disabled.
            ``RateBudgetConfig(...)`` → custom config.
        timeout: Override default httpx timeout.
    """

    def __init__(
        self,
        api_key: str,
        org_id: int,
        *,
        base_url: str = BASE_URL,
        retry: RetryConfig | None = None,
        rate_budget: RateBudgetConfig | None | bool = None,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if not org_id:
            raise ValueError("org_id is required")

        self.org_id = org_id
        self._retry = retry if retry is not None else DEFAULT_RETRY

        # Rate budget: None/True → default config, False → disabled
        if rate_budget is False:
            self._rate_budget: OutboundRateBudget | None = None
        elif rate_budget is None or rate_budget is True:
            self._rate_budget = OutboundRateBudget()
        else:
            self._rate_budget = OutboundRateBudget(rate_budget)

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout
            or httpx.Timeout(
                connect=DEFAULT_CONNECT_TIMEOUT,
                read=DEFAULT_READ_TIMEOUT,
                write=DEFAULT_WRITE_TIMEOUT,
                pool=DEFAULT_POOL_TIMEOUT,
            ),
        )

    @property
    def rate_budget(self) -> OutboundRateBudget | None:
        """The outbound rate budget, if configured."""
        return self._rate_budget

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> CodegenClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ── Agent Runs ──────────────────────────────────────────

    async def create_run(
        self,
        prompt: str,
        *,
        repo_id: int | None = None,
        model: str | None = None,
        agent_type: str = "claude_code",
        images: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentRun:
        """Create a new agent run."""
        body: dict[str, Any] = {"prompt": prompt}
        if repo_id is not None:
            body["repo_id"] = repo_id
        if model is not None:
            body["model"] = model
        if agent_type:
            body["agent_type"] = agent_type
        if images is not None:
            body["images"] = images
        if metadata is not None:
            body["metadata"] = metadata

        resp = await self._post(f"/organizations/{self.org_id}/agent/run", json=body)
        return AgentRun.model_validate(resp)

    async def get_run(self, run_id: int) -> AgentRun:
        """Get agent run by ID."""
        resp = await self._get(f"/organizations/{self.org_id}/agent/run/{run_id}")
        return AgentRun.model_validate(resp)

    async def list_runs(
        self,
        *,
        skip: int = 0,
        limit: int = 10,
        source_type: str | None = None,
        user_id: int | None = None,
    ) -> Page[AgentRun]:
        """List agent runs with pagination."""
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if source_type:
            params["source_type"] = source_type
        if user_id is not None:
            params["user_id"] = user_id

        resp = await self._get(f"/organizations/{self.org_id}/agent/runs", params=params)
        return Page[AgentRun].model_validate(resp)

    async def resume_run(
        self,
        run_id: int,
        prompt: str,
        *,
        model: str | None = None,
        images: list[str] | None = None,
    ) -> AgentRun:
        """Resume a paused agent run."""
        body: dict[str, Any] = {"agent_run_id": run_id, "prompt": prompt}
        if model is not None:
            body["model"] = model
        if images is not None:
            body["images"] = images

        resp = await self._post(f"/organizations/{self.org_id}/agent/run/resume", json=body)
        return AgentRun.model_validate(resp)

    async def get_logs(
        self,
        run_id: int,
        *,
        skip: int = 0,
        limit: int = 50,
        reverse: bool = True,
    ) -> AgentRunWithLogs:
        """Get agent run logs.

        Endpoint: ``GET /v1/alpha/organizations/{org_id}/agent/run/{agent_run_id}/logs``
        """
        params: dict[str, Any] = {
            "skip": skip,
            "limit": limit,
            "reverse": reverse,
        }
        resp = await self._get(
            f"/alpha/organizations/{self.org_id}/agent/run/{run_id}/logs",
            params=params,
        )
        return AgentRunWithLogs.model_validate(resp)

    async def ban_run(
        self,
        run_id: int,
        *,
        before_card_order_id: str | None = None,
        after_card_order_id: str | None = None,
    ) -> BanActionResponse:
        """Ban all checks for a PR and stop all related agents.

        Flags the PR to prevent future CI/CD check suite events from being
        processed and stops all current agents for that PR.
        """
        body: dict[str, Any] = {"agent_run_id": run_id}
        if before_card_order_id is not None:
            body["before_card_order_id"] = before_card_order_id
        if after_card_order_id is not None:
            body["after_card_order_id"] = after_card_order_id

        resp = await self._post(f"/organizations/{self.org_id}/agent/run/ban", json=body)
        return BanActionResponse.model_validate(resp)

    async def unban_run(
        self,
        run_id: int,
        *,
        before_card_order_id: str | None = None,
        after_card_order_id: str | None = None,
    ) -> BanActionResponse:
        """Unban all checks for a PR.

        Removes the ban flag from the PR to allow future CI/CD check suite
        events to be processed.
        """
        body: dict[str, Any] = {"agent_run_id": run_id}
        if before_card_order_id is not None:
            body["before_card_order_id"] = before_card_order_id
        if after_card_order_id is not None:
            body["after_card_order_id"] = after_card_order_id

        resp = await self._post(f"/organizations/{self.org_id}/agent/run/unban", json=body)
        return BanActionResponse.model_validate(resp)

    async def remove_from_pr(
        self,
        run_id: int,
        *,
        before_card_order_id: str | None = None,
        after_card_order_id: str | None = None,
    ) -> BanActionResponse:
        """Remove Codegen from a PR.

        Performs the same action as banning all checks — flags the PR to
        prevent future CI/CD check suite events and stops all current agents.
        """
        body: dict[str, Any] = {"agent_run_id": run_id}
        if before_card_order_id is not None:
            body["before_card_order_id"] = before_card_order_id
        if after_card_order_id is not None:
            body["after_card_order_id"] = after_card_order_id

        resp = await self._post(
            f"/organizations/{self.org_id}/agent/run/remove-from-pr", json=body
        )
        return BanActionResponse.model_validate(resp)

    # Legacy alias — preserved for backward compatibility
    async def stop_run(self, run_id: int) -> StopRunResponse:
        """Stop/ban an agent run (legacy alias)."""
        body: dict[str, Any] = {"agent_run_id": run_id}
        resp = await self._post(f"/organizations/{self.org_id}/agent/run/ban", json=body)
        return StopRunResponse.model_validate(resp)

    # ── Users ──────────────────────────────────────────────

    async def get_current_user(self) -> User:
        """Get current user from API token."""
        resp = await self._get("/users/me")
        return User.model_validate(resp)

    async def list_users(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Page[User]:
        """List users in the organization."""
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        resp = await self._get(f"/organizations/{self.org_id}/users", params=params)
        return Page[User].model_validate(resp)

    async def get_user(self, user_id: int) -> User:
        """Get user by ID."""
        resp = await self._get(f"/organizations/{self.org_id}/users/{user_id}")
        return User.model_validate(resp)

    # ── Organizations & Repos ───────────────────────────────

    async def list_orgs(self) -> Page[Organization]:
        """List organizations."""
        resp = await self._get("/organizations")
        return Page[Organization].model_validate(resp)

    async def get_organization_settings(self) -> OrganizationSettings:
        """Get organization feature-flag settings.

        Endpoint: ``GET /v1/organizations/{org_id}/settings``
        """
        try:
            resp = await self._get(f"/organizations/{self.org_id}/settings")
            return OrganizationSettings.model_validate(resp)
        except NotFoundError:
            # Compatibility fallback for API variants where settings are only
            # embedded in /organizations list payloads.
            orgs = await self.list_orgs()
            match = next((org for org in orgs.items if org.id == self.org_id), None)
            if match is not None and match.settings is not None:
                return match.settings
            return OrganizationSettings()

    async def list_repos(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Page[Repository]:
        """List repositories in the organization."""
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        resp = await self._get(f"/organizations/{self.org_id}/repos", params=params)
        return Page[Repository].model_validate(resp)

    # ── Pull Requests ───────────────────────────────────────

    async def edit_pr(
        self,
        repo_id: int,
        pr_id: int,
        state: PRState,
    ) -> EditPRResponse:
        """Edit PR properties (RESTful — requires repo_id)."""
        body = {"state": state}
        resp = await self._patch(
            f"/organizations/{self.org_id}/repos/{repo_id}/prs/{pr_id}",
            json=body,
        )
        return EditPRResponse.model_validate(resp)

    async def edit_pr_simple(
        self,
        pr_id: int,
        state: PRState,
    ) -> EditPRResponse:
        """Edit PR properties (simple — only requires pr_id)."""
        body = {"state": state}
        resp = await self._patch(
            f"/organizations/{self.org_id}/prs/{pr_id}",
            json=body,
        )
        return EditPRResponse.model_validate(resp)

    # ── Integrations ─────────────────────────────────────────

    async def get_integrations(self) -> OrganizationIntegrations:
        """Get all integrations for the organization."""
        resp = await self._get(f"/organizations/{self.org_id}/integrations")
        return OrganizationIntegrations.model_validate(resp)

    # ── Webhooks ─────────────────────────────────────────────

    async def get_webhook_config(self) -> WebhookConfig:
        """Get agent-run webhook configuration."""
        resp = await self._get(f"/organizations/{self.org_id}/webhooks/agent-run")
        return WebhookConfig.model_validate(resp)

    async def set_webhook_config(
        self,
        url: str,
        *,
        secret: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        """Set agent-run webhook configuration."""
        body: dict[str, Any] = {"url": url, "enabled": enabled}
        if secret is not None:
            body["secret"] = secret
        return await self._post(f"/organizations/{self.org_id}/webhooks/agent-run", json=body)

    async def delete_webhook_config(self) -> dict[str, Any]:
        """Delete agent-run webhook configuration."""
        return await self._delete(f"/organizations/{self.org_id}/webhooks/agent-run")

    async def test_webhook(self, url: str) -> dict[str, Any]:
        """Send a test event to a webhook URL."""
        body: dict[str, Any] = {"url": url}
        return await self._post(f"/organizations/{self.org_id}/webhooks/agent-run/test", json=body)

    # ── Setup Commands ───────────────────────────────────────

    async def generate_setup_commands(
        self,
        repo_id: int,
        *,
        prompt: str | None = None,
        trigger_source: str | None = None,
    ) -> SetupCommand:
        """Generate setup commands for a repository."""
        body: dict[str, Any] = {"repo_id": repo_id}
        if prompt is not None:
            body["prompt"] = prompt
        if trigger_source is not None:
            body["trigger_source"] = trigger_source
        resp = await self._post(f"/organizations/{self.org_id}/setup-commands/generate", json=body)
        return SetupCommand.model_validate(resp)

    # ── Sandbox ──────────────────────────────────────────────

    async def analyze_sandbox_logs(self, run_id: int) -> SandboxLog:
        """Analyze sandbox logs for an agent run."""
        resp = await self._post(f"/organizations/{self.org_id}/sandbox/{run_id}/analyze-logs")
        return SandboxLog.model_validate(resp)

    # ── Slack ────────────────────────────────────────────────

    async def generate_slack_connect_token(self) -> SlackToken:
        """Generate a short-lived Slack connect token."""
        body: dict[str, Any] = {"org_id": self.org_id}
        resp = await self._post("/slack-connect/generate-token", json=body)
        return SlackToken.model_validate(resp)

    # ── MCP Providers & OAuth ──────────────────────────────

    async def get_mcp_providers(self) -> list[MCPProvider]:
        """Get all MCP-enabled OAuth providers."""
        resp = await self._get_raw("/mcp-providers")
        return [MCPProvider.model_validate(item) for item in resp]

    async def get_oauth_status(self) -> list[OAuthTokenStatus]:
        """Get OAuth token status for the current user and organization."""
        resp = await self._get_raw(
            "/oauth/tokens/status",
            params={"org_id": self.org_id},
        )
        # Normalize: API may return list[str] or list[dict]
        result: list[OAuthTokenStatus] = []
        for item in resp:
            if isinstance(item, str):
                result.append(OAuthTokenStatus(provider=item))
            else:
                result.append(OAuthTokenStatus.model_validate(item))
        return result

    async def revoke_oauth(self, provider: str) -> None:
        """Revoke/disconnect an OAuth token for a specific provider."""
        await self._request(
            "POST",
            "/oauth/tokens/revoke",
            params={"provider": provider, "org_id": self.org_id},
        )

    # ── Check Suite Settings ────────────────────────────────

    async def get_check_suite_settings(self, repo_id: int) -> CheckSuiteSettings:
        """Get check suite settings for a repository.

        Endpoint: ``GET /v1/organizations/{org_id}/repos/check-suite-settings?repo_id=``
        """
        resp = await self._get(
            f"/organizations/{self.org_id}/repos/check-suite-settings",
            params={"repo_id": repo_id},
        )
        return CheckSuiteSettings.model_validate(resp)

    async def update_check_suite_settings(
        self,
        repo_id: int,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Update check suite settings for a repository.

        Endpoint: ``PUT /v1/organizations/{org_id}/repos/check-suite-settings?repo_id=``

        Args:
            repo_id: Repository ID.
            settings: Dict of settings fields to update (e.g. check_retry_count,
                ignored_checks, check_retry_counts, custom_prompts,
                high_priority_apps).
        """
        return await self._put(
            f"/organizations/{self.org_id}/repos/check-suite-settings",
            json=settings,
            params={"repo_id": repo_id},
        )

    # ── Rules ────────────────────────────────────────────────

    async def get_rules(self) -> dict[str, Any]:
        """Get organization and user agent rules."""
        return await self._get(f"/organizations/{self.org_id}/cli/rules")

    # ── Models ─────────────────────────────────────────────────

    async def list_models(self) -> ModelsResponse:
        """Get available AI models grouped by provider."""
        resp = await self._get(f"/organizations/{self.org_id}/models")
        return ModelsResponse.model_validate(resp)

    # ── Core Request Engine ─────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Unified HTTP request with retries, timeouts, and error normalization.

        Implements exponential backoff with jitter. For 429 responses,
        respects the ``Retry-After`` header when present.

        Returns:
            The successful ``httpx.Response``.

        Raises:
            CodegenAPIError: (or subclass) on non-retryable HTTP errors.
            httpx.TimeoutException: If all retry attempts time out.
            httpx.ConnectError: If all retry attempts fail to connect.
        """
        retry = self._retry
        request_id = uuid.uuid4().hex[:12]
        last_exc: Exception | None = None

        for attempt in range(retry.max_retries + 1):
            # Acquire rate budget token before each attempt (including retries)
            if self._rate_budget is not None:
                await self._rate_budget.acquire()

            try:
                resp = await self._client.request(
                    method,
                    path,
                    json=json,
                    params=params,
                    headers={"X-Request-ID": request_id},
                )

                # Success — return immediately
                if resp.is_success:
                    return resp

                # Non-retryable status — raise immediately
                status = resp.status_code
                if status not in retry.retryable_status_codes:
                    raise self._build_error(resp, request_id)

                # Retryable status — log and prepare for retry
                last_exc = self._build_error(resp, request_id)

                if attempt < retry.max_retries:
                    # For 429, prefer Retry-After header
                    if status == 429:
                        retry_after = _parse_retry_after(resp)
                        if retry_after is not None:
                            delay = retry_after
                        else:
                            delay = _compute_delay(attempt, retry)
                    else:
                        delay = _compute_delay(attempt, retry)

                    logger.warning(
                        "Retryable %s %s → %d (attempt %d/%d, retry in %.1fs) [request_id=%s]",
                        method,
                        path,
                        status,
                        attempt + 1,
                        retry.max_retries + 1,
                        delay,
                        request_id,
                    )
                    await asyncio.sleep(delay)
                    continue

            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
                last_exc = exc

                if not _is_retryable_exception(exc, retry) or attempt >= retry.max_retries:
                    raise

                delay = _compute_delay(attempt, retry)
                logger.warning(
                    "Retryable %s %s → %s (attempt %d/%d, retry in %.1fs) [request_id=%s]",
                    method,
                    path,
                    type(exc).__name__,
                    attempt + 1,
                    retry.max_retries + 1,
                    delay,
                    request_id,
                )
                await asyncio.sleep(delay)
                continue

        # All retries exhausted — raise the last error
        if last_exc is not None:
            raise last_exc
        # Should never reach here, but satisfy type checker
        raise RuntimeError("Unexpected state in retry loop")  # pragma: no cover

    def _build_error(
        self,
        response: httpx.Response,
        request_id: str,
    ) -> CodegenAPIError:
        """Build a classified ``CodegenAPIError`` from an HTTP response."""
        detail = _extract_detail(response)
        return _classify_error(
            request=response.request,
            response=response,
            detail=detail,
            request_id=request_id,
        )

    # ── HTTP Helpers ────────────────────────────────────────

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = await self._request("GET", path, params=params)
        result: dict[str, Any] = resp.json()
        return result

    async def _get_raw(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """GET that returns the raw JSON value (may be a list or dict)."""
        resp = await self._request("GET", path, params=params)
        return resp.json()

    async def _post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resp = await self._request("POST", path, json=json, params=params)
        result: dict[str, Any] = resp.json()
        return result

    async def _put(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resp = await self._request("PUT", path, json=json, params=params)
        return resp.json()  # type: ignore[no-any-return]

    async def _patch(self, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = await self._request("PATCH", path, json=json)
        result: dict[str, Any] = resp.json()
        return result

    async def _delete(self, path: str) -> dict[str, Any]:
        resp = await self._request("DELETE", path)
        result: dict[str, Any] = resp.json()
        return result
