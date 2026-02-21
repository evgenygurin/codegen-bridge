"""Async HTTP client for Codegen REST API v1."""

from __future__ import annotations

from typing import Any

import httpx

from bridge.models import (
    AgentRun,
    AgentRunWithLogs,
    BanActionResponse,
    CheckSuiteSettings,
    EditPRResponse,
    MCPProvider,
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
    User,
    WebhookConfig,
)

BASE_URL = "https://api.codegen.com/v1"


class CodegenClient:
    """Async client for Codegen API.

    Args:
        api_key: Bearer token for authentication.
        org_id: Organization ID for API calls.
        base_url: Override API base URL (for testing).
    """

    def __init__(
        self,
        api_key: str,
        org_id: int,
        *,
        base_url: str = BASE_URL,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if not org_id:
            raise ValueError("org_id is required")

        self.org_id = org_id
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

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
    async def stop_run(self, run_id: int) -> AgentRun:
        """Stop/ban an agent run (legacy alias — returns AgentRun for backward compat)."""
        body: dict[str, Any] = {"agent_run_id": run_id}
        resp = await self._post(f"/organizations/{self.org_id}/agent/run/ban", json=body)
        return AgentRun.model_validate(resp)

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
        resp = await self._get(f"/organizations/{self.org_id}/settings")
        return OrganizationSettings.model_validate(resp)

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
        return await self._post(
            f"/organizations/{self.org_id}/webhooks/agent-run/test", json=body
        )

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
        resp = await self._post(
            f"/organizations/{self.org_id}/setup-commands/generate", json=body
        )
        return SetupCommand.model_validate(resp)

    # ── Sandbox ──────────────────────────────────────────────

    async def analyze_sandbox_logs(self, run_id: int) -> SandboxLog:
        """Analyze sandbox logs for an agent run."""
        resp = await self._post(
            f"/organizations/{self.org_id}/sandbox/{run_id}/analyze-logs"
        )
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
        resp = await self._client.post(
            "/oauth/tokens/revoke",
            params={"provider": provider, "org_id": self.org_id},
        )
        resp.raise_for_status()

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
    ) -> dict:
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

    # ── HTTP Helpers ────────────────────────────────────────

    async def _get(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    async def _get_raw(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> Any:
        """GET that returns the raw JSON value (may be a list or dict)."""
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resp = await self._client.post(path, json=json, params=params)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    async def _put(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resp = await self._client.put(path, json=json, params=params)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    async def _patch(
        self, path: str, *, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        resp = await self._client.patch(path, json=json)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    async def _delete(self, path: str) -> dict[str, Any]:
        resp = await self._client.delete(path)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result
