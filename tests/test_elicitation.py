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

from bridge.elicitation import (
    DangerousActionConfirmation,
    ModelSelectionInput,
    RepoConfirmation,
    StopConfirmation,
    collect_input,
    confirm_action,
    confirm_with_schema,
    select_choice,
)


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


# ── Pydantic schema tests ──────────────────────────────────────


class TestPydanticElicitationSchemas:
    """Verify that the Pydantic schemas are properly defined."""

    def test_stop_confirmation(self):
        s = StopConfirmation(confirm=True)
        assert s.confirm is True

    def test_repo_confirmation(self):
        s = RepoConfirmation(confirm=False)
        assert s.confirm is False

    def test_dangerous_action_confirmation(self):
        s = DangerousActionConfirmation(confirm=True, reason="Testing")
        assert s.confirm is True
        assert s.reason == "Testing"

    def test_dangerous_action_default_reason(self):
        s = DangerousActionConfirmation(confirm=True)
        assert s.reason == ""

    def test_model_selection_input(self):
        s = ModelSelectionInput(model="claude-3-5-sonnet", temperature_override=0.5)
        assert s.model == "claude-3-5-sonnet"
        assert s.temperature_override == 0.5

    def test_model_selection_no_override(self):
        s = ModelSelectionInput(model="gpt-4o")
        assert s.temperature_override is None

    def test_schemas_json_round_trip(self):
        original = DangerousActionConfirmation(confirm=True, reason="test")
        restored = DangerousActionConfirmation.model_validate_json(
            original.model_dump_json()
        )
        assert restored.confirm == original.confirm
        assert restored.reason == original.reason


# ── confirm_with_schema (Pydantic) ────────────────────────────


class TestConfirmWithPydanticSchema:
    """confirm_with_schema works with Pydantic BaseModel schemas."""

    async def test_returns_pydantic_data_when_accepted(self, mock_ctx):
        mock_data = DangerousActionConfirmation(confirm=True, reason="safe")
        mock_ctx.elicit.return_value = AcceptedElicitation(action="accept", data=mock_data)
        result = await confirm_with_schema(
            mock_ctx, "Proceed?", DangerousActionConfirmation
        )
        assert result is not None
        assert result.confirm is True
        assert result.reason == "safe"

    async def test_returns_none_when_declined(self, mock_ctx):
        mock_ctx.elicit.return_value = DeclinedElicitation(action="decline")
        result = await confirm_with_schema(
            mock_ctx, "Proceed?", StopConfirmation
        )
        assert result is None


# ── collect_input ──────────────────────────────────────────────


class TestCollectInput:
    """Tests for the new collect_input helper."""

    async def test_returns_data_when_accepted(self, mock_ctx):
        mock_data = ModelSelectionInput(model="gpt-4o", temperature_override=0.3)
        mock_ctx.elicit.return_value = AcceptedElicitation(action="accept", data=mock_data)
        result = await collect_input(mock_ctx, "Select model:", ModelSelectionInput)
        assert result is not None
        assert result.model == "gpt-4o"
        assert result.temperature_override == 0.3

    async def test_returns_none_when_declined(self, mock_ctx):
        mock_ctx.elicit.return_value = DeclinedElicitation(action="decline")
        result = await collect_input(mock_ctx, "Select model:", ModelSelectionInput)
        assert result is None

    async def test_returns_none_when_cancelled(self, mock_ctx):
        mock_ctx.elicit.return_value = CancelledElicitation(action="cancel")
        result = await collect_input(mock_ctx, "Select model:", ModelSelectionInput)
        assert result is None

    async def test_returns_none_when_unsupported(self, mock_ctx):
        mock_ctx.elicit.side_effect = _mcp_error()
        result = await collect_input(mock_ctx, "Select model:", ModelSelectionInput)
        assert result is None

    async def test_returns_default_when_unsupported(self, mock_ctx):
        mock_ctx.elicit.side_effect = _mcp_error()
        result = await collect_input(
            mock_ctx,
            "Select model:",
            ModelSelectionInput,
            default_on_unsupported={"model": "claude-3-5-sonnet"},
        )
        assert result is not None
        assert result.model == "claude-3-5-sonnet"
        assert result.temperature_override is None

    async def test_returns_default_on_unexpected_error(self, mock_ctx):
        mock_ctx.elicit.side_effect = RuntimeError("broken")
        result = await collect_input(
            mock_ctx,
            "Select model:",
            ModelSelectionInput,
            default_on_unsupported={"model": "fallback"},
        )
        assert result is not None
        assert result.model == "fallback"

    async def test_returns_none_on_unexpected_error_no_default(self, mock_ctx):
        mock_ctx.elicit.side_effect = RuntimeError("broken")
        result = await collect_input(mock_ctx, "Select model:", ModelSelectionInput)
        assert result is None
