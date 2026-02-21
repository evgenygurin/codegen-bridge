"""Tests for dangerous tool authorization middleware.

Tests cover:
- AuthorizationConfig defaults and env var integration
- DangerousToolGuardMiddleware tool classification
- Tool call blocking/allowing behavior
- Tool listing annotation
- Custom authorization policies
- Middleware disabled passthrough
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from bridge.middleware.authorization import (
    DEFAULT_DANGEROUS_TAG,
    DEFAULT_DANGEROUS_TOOLS,
    AuthorizationConfig,
    DangerousToolGuardMiddleware,
)

# ── Helpers ─────────────────────────────────────────────


def _make_context(
    tool_name: str, tool_tags: set[str] | None = None
) -> MagicMock:
    """Create a minimal MiddlewareContext mock for on_call_tool."""
    ctx = MagicMock()
    ctx.message.name = tool_name
    ctx.fastmcp_context = None  # no server context in unit tests
    return ctx


def _make_list_context() -> MagicMock:
    """Create a minimal MiddlewareContext mock for on_list_tools."""
    ctx = MagicMock()
    ctx.fastmcp_context = None
    return ctx


@dataclass
class FakeTool:
    """Minimal stand-in for a FastMCP Tool with model_copy support."""

    name: str
    tags: set[str]
    description: str = ""

    def model_copy(self, *, update: dict[str, Any] | None = None) -> FakeTool:
        kw: dict[str, Any] = {
            "name": self.name,
            "tags": self.tags.copy(),
            "description": self.description,
        }
        if update:
            kw.update(update)
        return FakeTool(**kw)


# ── AuthorizationConfig tests ──────────────────────────


class TestAuthorizationConfig:
    """Tests for AuthorizationConfig Pydantic model."""

    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("CODEGEN_ALLOW_DANGEROUS_TOOLS", raising=False)
        cfg = AuthorizationConfig()
        assert cfg.enabled is True
        assert cfg.allow_dangerous is False  # env var not set
        assert cfg.dangerous_tool_names == DEFAULT_DANGEROUS_TOOLS
        assert cfg.dangerous_tag == DEFAULT_DANGEROUS_TAG

    def test_explicit_allow(self):
        cfg = AuthorizationConfig(allow_dangerous=True)
        assert cfg.allow_dangerous is True

    def test_explicit_deny(self):
        cfg = AuthorizationConfig(allow_dangerous=False)
        assert cfg.allow_dangerous is False

    def test_env_var_true(self, monkeypatch):
        monkeypatch.setenv("CODEGEN_ALLOW_DANGEROUS_TOOLS", "true")
        cfg = AuthorizationConfig()
        assert cfg.allow_dangerous is True

    def test_env_var_one(self, monkeypatch):
        monkeypatch.setenv("CODEGEN_ALLOW_DANGEROUS_TOOLS", "1")
        cfg = AuthorizationConfig()
        assert cfg.allow_dangerous is True

    def test_env_var_yes(self, monkeypatch):
        monkeypatch.setenv("CODEGEN_ALLOW_DANGEROUS_TOOLS", "yes")
        cfg = AuthorizationConfig()
        assert cfg.allow_dangerous is True

    def test_env_var_false(self, monkeypatch):
        monkeypatch.setenv("CODEGEN_ALLOW_DANGEROUS_TOOLS", "false")
        cfg = AuthorizationConfig()
        assert cfg.allow_dangerous is False

    def test_env_var_empty(self, monkeypatch):
        monkeypatch.setenv("CODEGEN_ALLOW_DANGEROUS_TOOLS", "")
        cfg = AuthorizationConfig()
        assert cfg.allow_dangerous is False

    def test_custom_tool_names(self):
        custom = frozenset({"my_dangerous_tool"})
        cfg = AuthorizationConfig(dangerous_tool_names=custom)
        assert cfg.dangerous_tool_names == custom

    def test_custom_tag(self):
        cfg = AuthorizationConfig(dangerous_tag="admin")
        assert cfg.dangerous_tag == "admin"

    def test_serialise_round_trip(self):
        cfg = AuthorizationConfig(allow_dangerous=True)
        data = cfg.model_dump()
        restored = AuthorizationConfig.model_validate(data)
        assert restored.allow_dangerous is True
        assert restored.dangerous_tool_names == cfg.dangerous_tool_names


# ── Tool classification tests ──────────────────────────


class TestIsDangerous:
    """Tests for DangerousToolGuardMiddleware.is_dangerous()."""

    def setup_method(self):
        self.mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=False)
        )

    def test_dangerous_by_name_stop_run(self):
        assert self.mw.is_dangerous("codegen_stop_run") is True

    def test_dangerous_by_name_edit_pr(self):
        assert self.mw.is_dangerous("codegen_edit_pr") is True

    def test_dangerous_by_name_edit_repo_pr(self):
        assert self.mw.is_dangerous("codegen_edit_repo_pr") is True

    def test_dangerous_by_name_delete_webhook(self):
        assert self.mw.is_dangerous("codegen_delete_webhook") is True

    def test_safe_tool_by_name(self):
        assert self.mw.is_dangerous("codegen_list_runs") is False

    def test_safe_tool_empty_tags(self):
        assert self.mw.is_dangerous("codegen_list_runs", set()) is False

    def test_dangerous_by_tag(self):
        assert self.mw.is_dangerous("unknown_tool", {"dangerous"}) is True

    def test_not_dangerous_by_irrelevant_tag(self):
        assert self.mw.is_dangerous("unknown_tool", {"execution"}) is False

    def test_custom_config_tool_names(self):
        cfg = AuthorizationConfig(
            dangerous_tool_names=frozenset({"custom_delete"}),
            allow_dangerous=False,
        )
        mw = DangerousToolGuardMiddleware(config=cfg)
        assert mw.is_dangerous("custom_delete") is True
        assert mw.is_dangerous("codegen_stop_run") is False

    def test_custom_config_tag(self):
        cfg = AuthorizationConfig(dangerous_tag="admin", allow_dangerous=False)
        mw = DangerousToolGuardMiddleware(config=cfg)
        assert mw.is_dangerous("some_tool", {"admin"}) is True
        assert mw.is_dangerous("some_tool", {"dangerous"}) is False


# ── on_call_tool tests ─────────────────────────────────


class TestOnCallTool:
    """Tests for tool call blocking/allowing behavior."""

    async def test_blocks_dangerous_tool_when_denied(self):
        """Dangerous tool call should raise ToolError when not allowed."""
        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=False)
        )
        ctx = _make_context("codegen_stop_run")
        call_next = AsyncMock(return_value="result")

        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="dangerous operation"):
            await mw.on_call_tool(ctx, call_next)

        # call_next should NOT be called
        call_next.assert_not_called()

    async def test_allows_dangerous_tool_when_permitted(self):
        """Dangerous tool call should proceed when allowed."""
        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=True)
        )
        ctx = _make_context("codegen_stop_run")
        call_next = AsyncMock(return_value="result")

        result = await mw.on_call_tool(ctx, call_next)
        assert result == "result"
        call_next.assert_called_once()

    async def test_allows_safe_tool_always(self):
        """Safe tool call should always proceed regardless of config."""
        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=False)
        )
        ctx = _make_context("codegen_list_runs")
        call_next = AsyncMock(return_value="safe_result")

        result = await mw.on_call_tool(ctx, call_next)
        assert result == "safe_result"
        call_next.assert_called_once()

    async def test_blocks_edit_pr(self):
        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=False)
        )
        ctx = _make_context("codegen_edit_pr")
        call_next = AsyncMock()

        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="codegen_edit_pr"):
            await mw.on_call_tool(ctx, call_next)

    async def test_blocks_delete_webhook(self):
        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=False)
        )
        ctx = _make_context("codegen_delete_webhook")
        call_next = AsyncMock()

        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="codegen_delete_webhook"):
            await mw.on_call_tool(ctx, call_next)

    async def test_passthrough_when_disabled(self):
        """Middleware should be a no-op when disabled."""
        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(enabled=False, allow_dangerous=False)
        )
        ctx = _make_context("codegen_stop_run")
        call_next = AsyncMock(return_value="passthrough")

        result = await mw.on_call_tool(ctx, call_next)
        assert result == "passthrough"
        call_next.assert_called_once()

    async def test_error_message_includes_env_var_hint(self):
        """Error message should tell the user how to enable dangerous tools."""
        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=False)
        )
        ctx = _make_context("codegen_stop_run")
        call_next = AsyncMock()

        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="CODEGEN_ALLOW_DANGEROUS_TOOLS"):
            await mw.on_call_tool(ctx, call_next)


# ── on_list_tools tests ────────────────────────────────


class TestOnListTools:
    """Tests for tool listing annotation behavior."""

    async def test_annotates_blocked_tools(self):
        """Blocked dangerous tools should have [RESTRICTED] prefix."""
        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=False)
        )
        tools = [
            FakeTool(name="codegen_stop_run", tags={"dangerous"}, description="Stop a run"),
            FakeTool(name="codegen_list_runs", tags={"execution"}, description="List runs"),
        ]
        ctx = _make_list_context()
        call_next = AsyncMock(return_value=tools)

        result = await mw.on_list_tools(ctx, call_next)

        assert len(result) == 2
        # Dangerous tool should be annotated
        assert result[0].description.startswith("[RESTRICTED]")
        assert "CODEGEN_ALLOW_DANGEROUS_TOOLS" in result[0].description
        # Safe tool should be unchanged
        assert result[1].description == "List runs"

    async def test_no_annotation_when_allowed(self):
        """Allowed dangerous tools should NOT have [RESTRICTED] prefix."""
        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=True)
        )
        tools = [
            FakeTool(name="codegen_stop_run", tags={"dangerous"}, description="Stop a run"),
        ]
        ctx = _make_list_context()
        call_next = AsyncMock(return_value=tools)

        result = await mw.on_list_tools(ctx, call_next)

        assert len(result) == 1
        assert result[0].description == "Stop a run"

    async def test_no_annotation_when_disabled(self):
        """Disabled middleware should not modify tool listing."""
        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(enabled=False, allow_dangerous=False)
        )
        tools = [
            FakeTool(name="codegen_stop_run", tags={"dangerous"}, description="Stop a run"),
        ]
        ctx = _make_list_context()
        call_next = AsyncMock(return_value=tools)

        result = await mw.on_list_tools(ctx, call_next)

        assert result[0].description == "Stop a run"

    async def test_annotates_tool_identified_by_name_only(self):
        """Tool with no tags but matching name should still be annotated."""
        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=False)
        )
        tools = [
            FakeTool(name="codegen_edit_pr", tags=set(), description="Edit PR"),
        ]
        ctx = _make_list_context()
        call_next = AsyncMock(return_value=tools)

        result = await mw.on_list_tools(ctx, call_next)

        assert result[0].description.startswith("[RESTRICTED]")


# ── Custom policy tests ────────────────────────────────


class TestCustomPolicy:
    """Tests for custom authorization policy (Strategy pattern)."""

    async def test_sync_policy_allow(self):
        """Sync policy that always allows should let calls through."""

        def allow_all(name: str, tags: set[str]) -> bool:
            return True

        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=False),
            policy=allow_all,
        )
        ctx = _make_context("codegen_stop_run")
        call_next = AsyncMock(return_value="ok")

        result = await mw.on_call_tool(ctx, call_next)
        assert result == "ok"

    async def test_sync_policy_deny(self):
        """Sync policy that always denies should block calls."""

        def deny_all(name: str, tags: set[str]) -> bool:
            return False

        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=True),  # config says allow
            policy=deny_all,  # policy overrides
        )
        ctx = _make_context("codegen_stop_run")
        call_next = AsyncMock()

        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError):
            await mw.on_call_tool(ctx, call_next)

    async def test_async_policy(self):
        """Async policy should be awaited properly."""

        async def async_allow(name: str, tags: set[str]) -> bool:
            return True

        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=False),
            policy=async_allow,
        )
        ctx = _make_context("codegen_stop_run")
        call_next = AsyncMock(return_value="async_ok")

        result = await mw.on_call_tool(ctx, call_next)
        assert result == "async_ok"

    async def test_selective_policy(self):
        """Policy that allows only specific tools."""

        def allow_stop_only(name: str, tags: set[str]) -> bool:
            return name == "codegen_stop_run"

        mw = DangerousToolGuardMiddleware(
            config=AuthorizationConfig(allow_dangerous=False),
            policy=allow_stop_only,
        )

        # codegen_stop_run should be allowed
        ctx1 = _make_context("codegen_stop_run")
        call_next1 = AsyncMock(return_value="stopped")
        result = await mw.on_call_tool(ctx1, call_next1)
        assert result == "stopped"

        # codegen_edit_pr should be blocked
        ctx2 = _make_context("codegen_edit_pr")
        call_next2 = AsyncMock()

        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError):
            await mw.on_call_tool(ctx2, call_next2)


# ── Default dangerous tools list tests ─────────────────


class TestDefaultDangerousTools:
    """Tests for the DEFAULT_DANGEROUS_TOOLS constant."""

    def test_contains_stop_run(self):
        assert "codegen_stop_run" in DEFAULT_DANGEROUS_TOOLS

    def test_contains_edit_pr(self):
        assert "codegen_edit_pr" in DEFAULT_DANGEROUS_TOOLS

    def test_contains_edit_repo_pr(self):
        assert "codegen_edit_repo_pr" in DEFAULT_DANGEROUS_TOOLS

    def test_contains_delete_webhook(self):
        assert "codegen_delete_webhook" in DEFAULT_DANGEROUS_TOOLS

    def test_is_frozenset(self):
        assert isinstance(DEFAULT_DANGEROUS_TOOLS, frozenset)

    def test_exactly_four_tools(self):
        assert len(DEFAULT_DANGEROUS_TOOLS) == 4
