"""Async HTTP client for Codegen REST API v1."""

from __future__ import annotations

from typing import Any

import httpx

from bridge.models import (
    AgentRun,
    AgentRunWithLogs,
    BanActionResponse,
    Organization,
    Page,
    Repository,
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
        limit: int = 100,
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
        limit: int = 100,
        reverse: bool = True,
    ) -> AgentRunWithLogs:
        """Get agent run logs.

        Endpoint: ``GET /v1/organizations/{org_id}/agent/run/{agent_run_id}/logs``
        """
        params: dict[str, Any] = {
            "skip": skip,
            "limit": limit,
            "reverse": reverse,
        }
        resp = await self._get(
            f"/organizations/{self.org_id}/agent/run/{run_id}/logs",
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
    async def stop_run(self, run_id: int) -> BanActionResponse:
        """Stop/ban an agent run (legacy alias for ``ban_run``)."""
        return await self.ban_run(run_id)

    # ── Organizations & Repos ───────────────────────────────

    async def list_orgs(self) -> Page[Organization]:
        """List organizations."""
        resp = await self._get("/organizations")
        return Page[Organization].model_validate(resp)

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

    # ── Rules ────────────────────────────────────────────────

    async def get_rules(self) -> dict[str, str]:
        """Get organization and user agent rules."""
        resp = await self._get(f"/organizations/{self.org_id}/cli/rules")
        return resp

    # ── HTTP Helpers ────────────────────────────────────────

    async def _get(self, path: str, *, params: dict | None = None) -> dict:
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, *, json: dict | None = None) -> dict:
        resp = await self._client.post(path, json=json)
        resp.raise_for_status()
        return resp.json()
