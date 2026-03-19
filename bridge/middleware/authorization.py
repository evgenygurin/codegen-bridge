"""Authorization middleware for dangerous tool access control.

Provides a configurable guard that prevents execution of dangerous tools
(stop_run, edit_pr, delete_webhook, etc.) unless explicitly allowed.

Works for all transports including STDIO (unlike FastMCP's built-in
``AuthMiddleware`` which skips STDIO).  Authorization is controlled by:

1. **Environment variable** ``CODEGEN_ALLOW_DANGEROUS_TOOLS=true``
2. **Config flag** ``AuthorizationConfig(allow_dangerous=True)``

Tools are identified as dangerous by:
- Matching a configured set of tool names (covers both manual and
  OpenAPI-generated tools)
- Having the ``"dangerous"`` tag (forward-compatible supplement)

The middleware follows the **Strategy** pattern — the authorization
policy is a callable that can be swapped for testing or custom logic.

Position in the stack: placed **after** error handling but **before**
execution-related middleware so denied calls are rejected early.

Usage::

    from bridge.middleware.authorization import (
        AuthorizationConfig,
        DangerousToolGuardMiddleware,
    )

    # Controlled by env var CODEGEN_ALLOW_DANGEROUS_TOOLS
    config = AuthorizationConfig()
    mw = DangerousToolGuardMiddleware(config)

    # Or explicitly allow for testing
    config = AuthorizationConfig(allow_dangerous=True)
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

import mcp.types as mt
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.tool import ToolResult
from pydantic import BaseModel, Field

logger = logging.getLogger("bridge.middleware.authorization")

# ── Default dangerous tool names ────────────────────────
# Canonical list of tools that perform destructive or irreversible actions.
# Includes both manual tools (bridge.tools.*) and OpenAPI-generated tools.

DEFAULT_DANGEROUS_TOOLS: frozenset[str] = frozenset(
    {
        # Manual tools
        "codegen_stop_run",
        # PR editing — both manual tools
        "codegen_edit_pr",
        "codegen_edit_pr_simple",
        # Webhook management — deletion is destructive, set redirects data
        "codegen_delete_webhook_config",
        "codegen_set_webhook_config",
        # OAuth — token revocation is irreversible
        "codegen_revoke_oauth_token",
    }
)

DEFAULT_DANGEROUS_TAG = "dangerous"


# ── Authorization policy (Strategy pattern) ─────────────

AuthorizationPolicy = Callable[[str, set[str]], bool | Awaitable[bool]]
"""Callable that decides whether a tool call is allowed.

Parameters:
    tool_name: The name of the tool being called.
    tool_tags: Tags associated with the tool (may be empty).

Returns:
    ``True`` to allow the call, ``False`` to deny it.
"""


def _default_deny_policy(tool_name: str, tool_tags: set[str]) -> bool:
    """Always deny — used when dangerous tools are not allowed."""
    return False


def _default_allow_policy(tool_name: str, tool_tags: set[str]) -> bool:
    """Always allow — used when dangerous tools are explicitly enabled."""
    return True


# ── Configuration ───────────────────────────────────────


class AuthorizationConfig(BaseModel):
    """Configuration for dangerous tool authorization.

    Attributes:
        enabled: Whether the authorization middleware is active.
            When ``False`` the middleware is a no-op passthrough.
        allow_dangerous: Allow execution of dangerous tools.
            Defaults to reading ``CODEGEN_ALLOW_DANGEROUS_TOOLS`` env var.
        dangerous_tool_names: Set of tool names considered dangerous.
        dangerous_tag: Tag that marks a tool as dangerous.
    """

    enabled: bool = True
    allow_dangerous: bool = Field(
        default_factory=lambda: (
            os.environ.get("CODEGEN_ALLOW_DANGEROUS_TOOLS", "").lower() in ("true", "1", "yes")
        ),
    )
    dangerous_tool_names: frozenset[str] = Field(default=DEFAULT_DANGEROUS_TOOLS)
    dangerous_tag: str = DEFAULT_DANGEROUS_TAG


# ── Middleware ──────────────────────────────────────────


class DangerousToolGuardMiddleware(Middleware):
    """Middleware that blocks dangerous tools unless explicitly allowed.

    Intercepts ``tools/call`` requests and checks whether the target tool
    is classified as dangerous.  If so, and dangerous tools are not
    allowed, raises a ``ToolError`` with an actionable message.

    Also intercepts ``tools/list`` to annotate dangerous tools with a
    ``[RESTRICTED]`` prefix in their description when they are blocked,
    so LLMs know not to call them.

    Parameters
    ----------
    config:
        Authorization configuration.  Uses ``AuthorizationConfig()``
        defaults if not provided.
    policy:
        Optional custom authorization policy.  When ``None``, uses a
        simple allow/deny based on ``config.allow_dangerous``.
    """

    def __init__(
        self,
        config: AuthorizationConfig | None = None,
        policy: AuthorizationPolicy | None = None,
    ) -> None:
        self.config = config or AuthorizationConfig()
        if policy is not None:
            self._policy = policy
        elif self.config.allow_dangerous:
            self._policy = _default_allow_policy
        else:
            self._policy = _default_deny_policy

    def is_dangerous(self, tool_name: str, tool_tags: set[str] | None = None) -> bool:
        """Check whether a tool is classified as dangerous.

        A tool is dangerous if its name is in the configured set OR it
        has the configured dangerous tag.
        """
        tags = tool_tags or set()
        if tool_name in self.config.dangerous_tool_names:
            return True
        return self.config.dangerous_tag in tags

    async def _check_policy(self, tool_name: str, tool_tags: set[str]) -> bool:
        """Run the authorization policy (supports sync and async callables)."""
        import inspect

        result = self._policy(tool_name, tool_tags)
        if inspect.isawaitable(result):
            return await result
        return result

    # ── Tool call interception ──────────────────────────

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        """Block dangerous tool calls when not authorized."""
        if not self.config.enabled:
            return await call_next(context)

        # Apply known argument defaults before policy checks and execution.
        # Needed for OpenAPI-generated tools where optional defaults may not
        # be propagated to the outbound HTTP request builder.
        context = self._with_default_arguments(context)

        tool_name = context.message.name
        tool_tags = await self._get_tool_tags(context, tool_name)

        if self.is_dangerous(tool_name, tool_tags):
            allowed = await self._check_policy(tool_name, tool_tags)
            if not allowed:
                logger.warning(
                    "Blocked dangerous tool call: %s (tags=%s)",
                    tool_name,
                    tool_tags,
                )
                raise ToolError(
                    f"Tool '{tool_name}' is a dangerous operation and is currently "
                    f"restricted. Set environment variable "
                    f"CODEGEN_ALLOW_DANGEROUS_TOOLS=true to enable it."
                )
            logger.info("Allowed dangerous tool call: %s", tool_name)

        return await call_next(context)

    # ── Tool listing annotation ─────────────────────────

    async def on_list_tools(
        self,
        context: MiddlewareContext[Any],
        call_next: CallNext[Any, Any],
    ) -> Any:
        """Annotate dangerous tools in listing when they are blocked.

        Adds a ``[RESTRICTED]`` prefix to the description of dangerous
        tools so LLMs know not to attempt calling them.
        """
        tools = await call_next(context)

        if not self.config.enabled:
            return tools

        annotated = []
        for tool in tools:
            tags = getattr(tool, "tags", set()) or set()
            if self.is_dangerous(tool.name, tags):
                allowed = await self._check_policy(tool.name, tags)
                if not allowed:
                    # Create a copy with annotated description
                    tool = tool.model_copy(
                        update={
                            "description": (
                                f"[RESTRICTED] {tool.description or ''} "
                                f"(Requires CODEGEN_ALLOW_DANGEROUS_TOOLS=true)"
                            ).strip(),
                        }
                    )
            annotated.append(tool)

        return annotated

    # ── Helpers ──────────────────────────────────────────

    @staticmethod
    async def _get_tool_tags(
        context: MiddlewareContext,
        tool_name: str,
    ) -> set[str]:
        """Extract tool tags from FastMCP server registry."""
        try:
            fastmcp_ctx = context.fastmcp_context
            if fastmcp_ctx is not None:
                server = fastmcp_ctx.fastmcp
                tool = await server.get_tool(tool_name)
                if tool is not None:
                    tags = getattr(tool, "tags", set()) or set()
                    return set(tags)
        except (AttributeError, KeyError, TypeError, RuntimeError):
            # Fail open for tag lookup — name-based check is the primary guard
            logger.debug("Could not resolve tags for tool '%s'", tool_name, exc_info=True)
        return set()

    @staticmethod
    def _with_default_arguments(
        context: MiddlewareContext[mt.CallToolRequestParams],
    ) -> MiddlewareContext[mt.CallToolRequestParams]:
        """Inject known default args required by upstream APIs.

        FastMCP/OpenAPI tooling validates optional query params but does not
        always materialize schema defaults into request arguments. For
        ``codegen_revoke_oauth_token`` we must pass ``org_id`` explicitly.
        """
        if context.message.name != "codegen_revoke_oauth_token":
            return context

        args = dict(context.message.arguments or {})
        if args.get("org_id") is not None:
            return context

        fastmcp_ctx = context.fastmcp_context
        if fastmcp_ctx is None:
            return context

        lifespan = fastmcp_ctx.lifespan_context or {}
        org_id = lifespan.get("org_id")
        if not isinstance(org_id, int):
            return context

        args["org_id"] = org_id
        patched_message = context.message.model_copy(update={"arguments": args})
        return context.copy(message=patched_message)
