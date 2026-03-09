"""User management tools: get current user, list users, get user by ID.

Provides tools for querying user information within the configured
Codegen organization, including profile details, roles, and
GitHub account linkage.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.annotations import READ_ONLY
from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.helpers.pagination import (
    DEFAULT_PAGE_SIZE,
    build_paginated_response,
    cursor_to_offset,
)
from bridge.icons import ICON_USER, ICON_USERS
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


def register_user_tools(mcp: FastMCP) -> None:
    """Register user management tools (get current user, list, get by ID)."""

    @mcp.tool(tags={"setup"}, icons=ICON_USER, annotations=READ_ONLY)
    async def codegen_get_current_user(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),    ) -> str:
        """Get current user information from the API token.

        Returns the profile of the authenticated user, including
        GitHub username, email, role, and avatar URL.
        """
        await ctx.info("Fetching current user")
        user = await client.get_current_user()
        await ctx.info(f"Current user: {user.github_username}")
        return json.dumps({"user": _user_to_dict(user)})

    @mcp.tool(tags={"setup"}, icons=ICON_USERS, annotations=READ_ONLY)
    async def codegen_list_users(
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),    ) -> str:
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

    @mcp.tool(tags={"setup"}, icons=ICON_USER, annotations=READ_ONLY)
    async def codegen_get_user(
        user_id: int,
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),    ) -> str:
        """Get details for a specific user in the organization.

        Args:
            user_id: Unique user ID.
        """
        await ctx.info(f"Fetching user {user_id}")
        user = await client.get_user(user_id)
        await ctx.info(f"Found user: {user.github_username}")
        return json.dumps({"user": _user_to_dict(user)})
