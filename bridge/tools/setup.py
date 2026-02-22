"""Organization, repository, user setup, and OAuth tools."""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context

from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.elicitation import confirm_action
from bridge.helpers.pagination import (
    DEFAULT_PAGE_SIZE,
    build_paginated_response,
    cursor_to_offset,
)
from bridge.icons import (
    ICON_CHECK_SUITE,
    ICON_MCP,
    ICON_OAUTH,
    ICON_ORG,
    ICON_ORG_SETTINGS,
    ICON_REPO,
    ICON_SETUP_CMD,
    ICON_USER,
    ICON_USERS,
)
from bridge.models import User


def _user_to_dict(user: User) -> dict[str, Any]:
    """Serialize a User model to a dict for JSON responses."""
    return {
        "id": user.id,
        "github_user_id": user.github_user_id,
        "github_username": user.github_username,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "full_name": user.full_name,
        "role": user.role,
        "is_admin": user.is_admin,
    }


def register_setup_tools(mcp: FastMCP) -> None:
    """Register all setup tools on the given FastMCP server."""

    # ── Users ──────────────────────────────────────────────

    @mcp.tool(tags={"setup"}, icons=ICON_USER)
    async def codegen_get_current_user(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Get current user information from the API token.

        Returns the profile of the authenticated user, including
        GitHub username, email, role, and avatar URL.
        """
        await ctx.info("Fetching current user")
        user = await client.get_current_user()
        await ctx.info(f"Current user: {user.github_username}")
        return json.dumps({"user": _user_to_dict(user)})

    @mcp.tool(tags={"setup"}, icons=ICON_USERS)
    async def codegen_list_users(
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """List users in the configured Codegen organization.

        Supports cursor-based pagination for large user lists.

        Args:
            limit: Maximum users per page (default 20).
            cursor: Opaque cursor from a previous response's ``next_cursor``
                field.  Omit or pass ``null`` for the first page.
        """
        offset = cursor_to_offset(cursor)
        await ctx.info(f"Listing users: limit={limit}, offset={offset}")
        page = await client.list_users(skip=offset, limit=limit)
        await ctx.info(f"Listed {len(page.items)} of {page.total} users")
        return json.dumps(
            build_paginated_response(
                items=[_user_to_dict(u) for u in page.items],
                total=page.total,
                offset=offset,
                page_size=limit,
                items_key="users",
            )
        )

    @mcp.tool(tags={"setup"}, icons=ICON_USER)
    async def codegen_get_user(
        user_id: int,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Get details for a specific user in the organization.

        Args:
            user_id: Unique user ID.
        """
        await ctx.info(f"Fetching user {user_id}")
        user = await client.get_user(user_id)
        await ctx.info(f"Found user: {user.github_username}")
        return json.dumps({"user": _user_to_dict(user)})

    # ── Organizations ──────────────────────────────────────

    @mcp.tool(tags={"setup"}, icons=ICON_ORG)
    async def codegen_list_orgs(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """List Codegen organizations the authenticated user belongs to."""
        await ctx.info("Listing organizations")
        page = await client.list_orgs()
        await ctx.info(f"Found {len(page.items)} organizations")
        return json.dumps(
            {
                "organizations": [{"id": org.id, "name": org.name} for org in page.items],
            }
        )

    @mcp.tool(tags={"setup"}, icons=ICON_ORG_SETTINGS)
    async def codegen_get_organization_settings(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),
    ) -> str:
        """Get organization feature-flag settings.

        Returns the current feature flags for the configured organization,
        such as whether PR creation and rules detection are enabled.
        """
        await ctx.info("Fetching organization settings")
        settings = await client.get_organization_settings()
        await ctx.info(
            f"Organization settings: pr_creation={settings.enable_pr_creation}, "
            f"rules_detection={settings.enable_rules_detection}"
        )
        return json.dumps(
            {
                "enable_pr_creation": settings.enable_pr_creation,
                "enable_rules_detection": settings.enable_rules_detection,
            }
        )

    @mcp.tool(tags={"setup"}, icons=ICON_REPO)
    async def codegen_list_repos(
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """List repositories in the configured Codegen organization.

        Supports cursor-based pagination for large repository lists.

        Args:
            limit: Maximum repos per page (default 20).
            cursor: Opaque cursor from a previous response's ``next_cursor``
                field.  Omit or pass ``null`` for the first page.
        """
        offset = cursor_to_offset(cursor)
        await ctx.info(f"Listing repos: limit={limit}, offset={offset}")
        page = await client.list_repos(skip=offset, limit=limit)
        await ctx.info(f"Listed {len(page.items)} of {page.total} repos")
        return json.dumps(
            build_paginated_response(
                items=[
                    {
                        "id": r.id,
                        "name": r.name,
                        "full_name": r.full_name,
                        "language": r.language,
                        "setup_status": r.setup_status,
                    }
                    for r in page.items
                ],
                total=page.total,
                offset=offset,
                page_size=limit,
                items_key="repos",
            )
        )

    @mcp.tool(tags={"setup"}, icons=ICON_SETUP_CMD)
    async def codegen_generate_setup_commands(
        repo_id: int,
        prompt: str | None = None,
        trigger_source: str = "setup-commands",
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Generate setup commands for a repository.

        Creates an agent that analyzes the repository structure and generates
        appropriate setup commands. The generation runs asynchronously —
        use the returned agent_run_id to check results.

        Args:
            repo_id: Repository ID to generate setup commands for.
            prompt: Optional custom prompt to guide generation.
            trigger_source: Source trigger identifier (default "setup-commands").
        """
        await ctx.info(f"Generating setup commands: repo_id={repo_id}")
        result = await client.generate_setup_commands(
            repo_id, prompt=prompt, trigger_source=trigger_source
        )
        await ctx.info(
            f"Setup commands generation started: agent_run_id={result.agent_run_id}, "
            f"status={result.status}"
        )
        return json.dumps(
            {
                "agent_run_id": result.agent_run_id,
                "status": result.status,
                "url": result.url,
            }
        )

    @mcp.tool(tags={"setup"}, icons=ICON_MCP)
    async def codegen_get_mcp_providers(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """List available MCP-enabled OAuth providers.

        Returns all providers registered in Codegen with ``is_mcp=True``.
        Use these provider names when checking OAuth token status or
        configuring MCP server integrations.
        """
        await ctx.info("Fetching MCP providers")
        providers = await client.get_mcp_providers()
        await ctx.info(f"Found {len(providers)} MCP providers")
        return json.dumps(
            {
                "providers": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "issuer": p.issuer,
                        "authorization_endpoint": p.authorization_endpoint,
                        "token_endpoint": p.token_endpoint,
                        "default_scopes": p.default_scopes,
                    }
                    for p in providers
                ],
                "total": len(providers),
            }
        )

    @mcp.tool(tags={"setup"}, icons=ICON_OAUTH)
    async def codegen_get_oauth_status(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Get OAuth token status for the current user and organization.

        Returns a list of connected OAuth providers that have active tokens.
        Use this to check which MCP providers are already authorized before
        prompting the user to connect new ones.
        """
        await ctx.info("Fetching OAuth token status")
        statuses = await client.get_oauth_status()
        await ctx.info(f"Found {len(statuses)} connected providers")
        return json.dumps(
            {
                "connected_providers": [
                    {"provider": s.provider, "active": s.active} for s in statuses
                ],
                "total": len(statuses),
            }
        )

    # ── Check Suite Settings ─────────────────────────────

    @mcp.tool(tags={"setup"}, icons=ICON_CHECK_SUITE)
    async def codegen_get_check_suite_settings(
        repo_id: int,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),
    ) -> str:
        """Get CI check-suite settings for a repository.

        Returns retry counts, ignored checks, custom prompts, high-priority
        apps, and available check suite names.

        Args:
            repo_id: Repository ID to get check suite settings for.
        """
        await ctx.info(f"Fetching check suite settings: repo_id={repo_id}")
        settings = await client.get_check_suite_settings(repo_id)
        await ctx.info(
            f"Check suite settings retrieved: "
            f"{len(settings.ignored_checks)} ignored checks, "
            f"retry_count={settings.check_retry_count}"
        )
        return json.dumps(
            {
                "check_retry_count": settings.check_retry_count,
                "ignored_checks": settings.ignored_checks,
                "check_retry_counts": settings.check_retry_counts,
                "custom_prompts": settings.custom_prompts,
                "high_priority_apps": settings.high_priority_apps,
                "available_check_suite_names": settings.available_check_suite_names,
            }
        )

    @mcp.tool(tags={"setup"}, icons=ICON_CHECK_SUITE)
    async def codegen_update_check_suite_settings(
        repo_id: int,
        check_retry_count: int | None = None,
        ignored_checks: list[str] | None = None,
        check_retry_counts: dict[str, int] | None = None,
        custom_prompts: dict[str, str] | None = None,
        high_priority_apps: list[str] | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),
    ) -> str:
        """Update CI check-suite settings for a repository.

        Only the fields you provide will be updated; omitted fields
        are left unchanged.

        Args:
            repo_id: Repository ID to update settings for.
            check_retry_count: Global retry count for failed checks (0-10).
            ignored_checks: List of check names to ignore.
            check_retry_counts: Per-check retry counts (check_name → count).
            custom_prompts: Per-check custom prompts (check_name → prompt).
            high_priority_apps: Apps whose checks are treated as high priority.
        """
        body: dict = {}
        if check_retry_count is not None:
            body["check_retry_count"] = check_retry_count
        if ignored_checks is not None:
            body["ignored_checks"] = ignored_checks
        if check_retry_counts is not None:
            body["check_retry_counts"] = check_retry_counts
        if custom_prompts is not None:
            body["custom_prompts"] = custom_prompts
        if high_priority_apps is not None:
            body["high_priority_apps"] = high_priority_apps

        if not body:
            raise ToolError("At least one setting field must be provided")

        await ctx.info(f"Updating check suite settings: repo_id={repo_id}, fields={list(body)}")
        result = await client.update_check_suite_settings(repo_id, body)
        await ctx.info("Check suite settings updated")
        return json.dumps({"status": "updated", "result": result})

    @mcp.tool(tags={"setup", "dangerous"}, icons=ICON_OAUTH)
    async def codegen_revoke_oauth(
        provider: str,
        confirmed: bool = False,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Revoke/disconnect an OAuth token for a specific provider.

        Marks ALL tokens as inactive for the current user and organization.
        This action cannot be undone — the user will need to re-authorize.

        Args:
            provider: Provider name to revoke (e.g. from ``codegen_get_mcp_providers``).
            confirmed: Skip interactive confirmation when True (for programmatic use).
        """
        if not provider:
            raise ToolError("provider is required")

        if not confirmed:
            user_confirmed = await confirm_action(
                ctx,
                f"Revoke OAuth token for provider '{provider}'? "
                "All active tokens will be deactivated. This cannot be undone.",
            )
            if not user_confirmed:
                return json.dumps(
                    {
                        "action": "cancelled",
                        "reason": "User declined to revoke OAuth token",
                    }
                )

        await ctx.warning(f"Revoking OAuth token for provider: {provider}")
        await client.revoke_oauth(provider)
        await ctx.info(f"OAuth token revoked for provider: {provider}")
        return json.dumps(
            {
                "action": "revoked",
                "provider": provider,
            }
        )
