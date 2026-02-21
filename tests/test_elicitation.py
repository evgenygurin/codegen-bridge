"""Tests for the elicitation helpers module (bridge.elicitation).

Tests cover:
- confirm_action: accept/decline/cancel/unsupported
- confirm_with_schema: dataclass schema accept/decline/cancel/unsupported
- select_choice: accept/decline/cancel/unsupported/empty choices
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest
from fastmcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData

from bridge.elicitation import confirm_action, confirm_with_schema, select_choice


def _mcp_error(msg: str = "Elicitation not supported") -> McpError:
    """Create a properly-constructed McpError for tests."""
    return McpError(ErrorData(code=-1, message=msg))


@pytest.fixture
def mock_ctx():
    """Create a mock Context with elicit and logging methods."""
    ctx = AsyncMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


# ── confirm_action ──────────────────────────────────────────


class TestConfirmAction:
    async def test_returns_true_when_user_accepts_true(self, mock_ctx):
        mock_ctx.elicit.return_value = AcceptedElicitation(action="accept", data=True)
        result = await confirm_action(mock_ctx, "Proceed?")
        assert result is True
        mock_ctx.elicit.assert_awaited_once_with("Proceed?", bool)
        mock_ctx.info.assert_awaited()

    async def test_returns_false_when_user_accepts_false(self, mock_ctx):
        mock_ctx.elicit.return_value = AcceptedElicitation(action="accept", data=False)
        result = await confirm_action(mock_ctx, "Proceed?")
        assert result is False

    async def test_returns_false_when_user_declines(self, mock_ctx):
        mock_ctx.elicit.return_value = DeclinedElicitation(action="decline")
        result = await confirm_action(mock_ctx, "Proceed?")
        assert result is False
        mock_ctx.info.assert_awaited()

    async def test_returns_false_when_user_cancels(self, mock_ctx):
        mock_ctx.elicit.return_value = CancelledElicitation(action="cancel")
        result = await confirm_action(mock_ctx, "Proceed?")
        assert result is False

    async def test_returns_default_true_when_unsupported(self, mock_ctx):
        mock_ctx.elicit.side_effect = _mcp_error()
        result = await confirm_action(mock_ctx, "Proceed?")
        assert result is True

    async def test_returns_custom_default_when_unsupported(self, mock_ctx):
        mock_ctx.elicit.side_effect = _mcp_error()
        result = await confirm_action(mock_ctx, "Proceed?", default=False)
        assert result is False

    async def test_returns_default_on_unexpected_error(self, mock_ctx):
        mock_ctx.elicit.side_effect = RuntimeError("Something broke")
        result = await confirm_action(mock_ctx, "Proceed?")
        assert result is True

    async def test_returns_custom_default_on_unexpected_error(self, mock_ctx):
        mock_ctx.elicit.side_effect = RuntimeError("Something broke")
        result = await confirm_action(mock_ctx, "Proceed?", default=False)
        assert result is False


# ── confirm_with_schema ─────────────────────────────────────


@dataclass
class ConfirmSchema:
    """Dataclass schema for elicitation tests."""

    confirm: bool
    reason: str = ""


class TestConfirmWithSchema:
    async def test_returns_data_when_accepted(self, mock_ctx):
        mock_data = ConfirmSchema(confirm=True, reason="testing")
        mock_ctx.elicit.return_value = AcceptedElicitation(action="accept", data=mock_data)
        result = await confirm_with_schema(mock_ctx, "Confirm?", ConfirmSchema)
        assert result is not None
        assert result.confirm is True
        assert result.reason == "testing"
        mock_ctx.elicit.assert_awaited_once_with("Confirm?", ConfirmSchema)

    async def test_returns_none_when_declined(self, mock_ctx):
        mock_ctx.elicit.return_value = DeclinedElicitation(action="decline")
        result = await confirm_with_schema(mock_ctx, "Confirm?", ConfirmSchema)
        assert result is None

    async def test_returns_none_when_cancelled(self, mock_ctx):
        mock_ctx.elicit.return_value = CancelledElicitation(action="cancel")
        result = await confirm_with_schema(mock_ctx, "Confirm?", ConfirmSchema)
        assert result is None

    async def test_returns_default_when_unsupported(self, mock_ctx):
        mock_ctx.elicit.side_effect = _mcp_error()
        default = ConfirmSchema(confirm=False, reason="default")
        result = await confirm_with_schema(
            mock_ctx, "Confirm?", ConfirmSchema, default_on_unsupported=default
        )
        assert result is default

    async def test_returns_none_default_when_unsupported(self, mock_ctx):
        mock_ctx.elicit.side_effect = _mcp_error()
        result = await confirm_with_schema(mock_ctx, "Confirm?", ConfirmSchema)
        assert result is None

    async def test_returns_default_on_unexpected_error(self, mock_ctx):
        mock_ctx.elicit.side_effect = RuntimeError("broken")
        result = await confirm_with_schema(mock_ctx, "Confirm?", ConfirmSchema)
        assert result is None


# ── select_choice ───────────────────────────────────────────


class TestSelectChoice:
    async def test_returns_selected_when_accepted(self, mock_ctx):
        mock_ctx.elicit.return_value = AcceptedElicitation(action="accept", data="option-a")
        result = await select_choice(mock_ctx, "Pick one:", ["option-a", "option-b"])
        assert result == "option-a"
        mock_ctx.elicit.assert_awaited_once_with("Pick one:", ["option-a", "option-b"])
        mock_ctx.info.assert_awaited()

    async def test_returns_none_when_declined(self, mock_ctx):
        mock_ctx.elicit.return_value = DeclinedElicitation(action="decline")
        result = await select_choice(mock_ctx, "Pick one:", ["a", "b"])
        assert result is None

    async def test_returns_none_when_cancelled(self, mock_ctx):
        mock_ctx.elicit.return_value = CancelledElicitation(action="cancel")
        result = await select_choice(mock_ctx, "Pick one:", ["a", "b"])
        assert result is None

    async def test_returns_default_when_unsupported(self, mock_ctx):
        mock_ctx.elicit.side_effect = _mcp_error()
        result = await select_choice(mock_ctx, "Pick one:", ["a", "b"], default="a")
        assert result == "a"

    async def test_returns_none_default_when_unsupported(self, mock_ctx):
        mock_ctx.elicit.side_effect = _mcp_error()
        result = await select_choice(mock_ctx, "Pick one:", ["a", "b"])
        assert result is None

    async def test_returns_default_for_empty_choices(self, mock_ctx):
        result = await select_choice(mock_ctx, "Pick one:", [])
        assert result is None
        mock_ctx.elicit.assert_not_awaited()

    async def test_returns_custom_default_for_empty_choices(self, mock_ctx):
        result = await select_choice(mock_ctx, "Pick one:", [], default="fallback")
        assert result == "fallback"
        mock_ctx.elicit.assert_not_awaited()

    async def test_returns_default_on_unexpected_error(self, mock_ctx):
        mock_ctx.elicit.side_effect = RuntimeError("broken")
        result = await select_choice(mock_ctx, "Pick one:", ["a", "b"], default="b")
        assert result == "b"
