"""Tests for Pydantic schema elicitation and multi-select helpers.

Tests cover:
- confirm_with_schema with Pydantic BaseModel
- select_multiple: accept/decline/cancel/unsupported/empty/filtering
- Graceful degradation for all helpers (NotImplementedError, AttributeError)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastmcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData
from pydantic import BaseModel

from bridge.elicitation import (
    MultiSelectSchema,
    confirm_with_schema,
    select_multiple,
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


# ── confirm_with_schema + Pydantic BaseModel ────────────────


class DeployConfig(BaseModel):
    """Pydantic schema for elicitation tests."""

    environment: str = "staging"
    force: bool = False


class TestConfirmWithPydanticSchema:
    async def test_returns_pydantic_model_when_accepted(self, mock_ctx):
        mock_data = DeployConfig(environment="production", force=True)
        mock_ctx.elicit.return_value = AcceptedElicitation(action="accept", data=mock_data)

        result = await confirm_with_schema(mock_ctx, "Deploy config?", DeployConfig)

        assert result is not None
        assert isinstance(result, DeployConfig)
        assert result.environment == "production"
        assert result.force is True
        mock_ctx.elicit.assert_awaited_once_with("Deploy config?", DeployConfig)

    async def test_returns_none_when_declined(self, mock_ctx):
        mock_ctx.elicit.return_value = DeclinedElicitation(action="decline")
        result = await confirm_with_schema(mock_ctx, "Deploy config?", DeployConfig)
        assert result is None

    async def test_returns_none_when_cancelled(self, mock_ctx):
        mock_ctx.elicit.return_value = CancelledElicitation(action="cancel")
        result = await confirm_with_schema(mock_ctx, "Deploy config?", DeployConfig)
        assert result is None

    async def test_returns_default_when_unsupported(self, mock_ctx):
        mock_ctx.elicit.side_effect = _mcp_error()
        default = DeployConfig(environment="fallback", force=False)
        result = await confirm_with_schema(
            mock_ctx, "Deploy config?", DeployConfig, default_on_unsupported=default
        )
        assert result is default

    async def test_returns_none_default_when_unsupported(self, mock_ctx):
        mock_ctx.elicit.side_effect = _mcp_error()
        result = await confirm_with_schema(mock_ctx, "Deploy config?", DeployConfig)
        assert result is None

    async def test_graceful_on_not_implemented(self, mock_ctx):
        mock_ctx.elicit.side_effect = NotImplementedError("elicit not available")
        result = await confirm_with_schema(mock_ctx, "Deploy config?", DeployConfig)
        assert result is None

    async def test_graceful_on_attribute_error(self, mock_ctx):
        mock_ctx.elicit.side_effect = AttributeError("no elicit method")
        result = await confirm_with_schema(mock_ctx, "Deploy config?", DeployConfig)
        assert result is None

    async def test_graceful_on_runtime_error(self, mock_ctx):
        mock_ctx.elicit.side_effect = RuntimeError("broken")
        result = await confirm_with_schema(mock_ctx, "Deploy config?", DeployConfig)
        assert result is None

    async def test_graceful_on_type_error(self, mock_ctx):
        mock_ctx.elicit.side_effect = TypeError("bad schema")
        result = await confirm_with_schema(mock_ctx, "Deploy config?", DeployConfig)
        assert result is None


# ── select_multiple ─────────────────────────────────────────


class TestSelectMultiple:
    async def test_returns_selected_items_when_accepted(self, mock_ctx):
        mock_data = MultiSelectSchema(selected="repo-a, repo-c")
        mock_ctx.elicit.return_value = AcceptedElicitation(action="accept", data=mock_data)

        result = await select_multiple(
            mock_ctx, "Which repos?", ["repo-a", "repo-b", "repo-c"]
        )

        assert result == ["repo-a", "repo-c"]
        mock_ctx.info.assert_awaited()

    async def test_filters_invalid_choices(self, mock_ctx):
        mock_data = MultiSelectSchema(selected="valid, invalid, also-valid")
        mock_ctx.elicit.return_value = AcceptedElicitation(action="accept", data=mock_data)

        result = await select_multiple(
            mock_ctx, "Pick:", ["valid", "also-valid", "other"]
        )

        assert result == ["valid", "also-valid"]

    async def test_handles_whitespace_in_selections(self, mock_ctx):
        mock_data = MultiSelectSchema(selected="  a , b ,  c  ")
        mock_ctx.elicit.return_value = AcceptedElicitation(action="accept", data=mock_data)

        result = await select_multiple(mock_ctx, "Pick:", ["a", "b", "c"])

        assert result == ["a", "b", "c"]

    async def test_returns_empty_for_no_valid_selections(self, mock_ctx):
        mock_data = MultiSelectSchema(selected="x, y, z")
        mock_ctx.elicit.return_value = AcceptedElicitation(action="accept", data=mock_data)

        result = await select_multiple(mock_ctx, "Pick:", ["a", "b"])

        assert result == []

    async def test_returns_empty_for_blank_input(self, mock_ctx):
        mock_data = MultiSelectSchema(selected="")
        mock_ctx.elicit.return_value = AcceptedElicitation(action="accept", data=mock_data)

        result = await select_multiple(mock_ctx, "Pick:", ["a", "b"])

        assert result == []

    async def test_returns_default_when_declined(self, mock_ctx):
        mock_ctx.elicit.return_value = DeclinedElicitation(action="decline")
        result = await select_multiple(mock_ctx, "Pick:", ["a", "b"])
        assert result == []

    async def test_returns_custom_default_when_declined(self, mock_ctx):
        mock_ctx.elicit.return_value = DeclinedElicitation(action="decline")
        result = await select_multiple(mock_ctx, "Pick:", ["a", "b"], default=["a"])
        assert result == ["a"]

    async def test_returns_default_when_cancelled(self, mock_ctx):
        mock_ctx.elicit.return_value = CancelledElicitation(action="cancel")
        result = await select_multiple(mock_ctx, "Pick:", ["a", "b"])
        assert result == []

    async def test_returns_default_for_empty_choices(self, mock_ctx):
        result = await select_multiple(mock_ctx, "Pick:", [])
        assert result == []
        mock_ctx.elicit.assert_not_awaited()

    async def test_returns_custom_default_for_empty_choices(self, mock_ctx):
        result = await select_multiple(mock_ctx, "Pick:", [], default=["fallback"])
        assert result == ["fallback"]
        mock_ctx.elicit.assert_not_awaited()

    async def test_graceful_on_mcp_error(self, mock_ctx):
        mock_ctx.elicit.side_effect = _mcp_error()
        result = await select_multiple(mock_ctx, "Pick:", ["a", "b"])
        assert result == []

    async def test_graceful_on_not_implemented(self, mock_ctx):
        mock_ctx.elicit.side_effect = NotImplementedError("elicit not available")
        result = await select_multiple(mock_ctx, "Pick:", ["a", "b"])
        assert result == []

    async def test_graceful_on_attribute_error(self, mock_ctx):
        mock_ctx.elicit.side_effect = AttributeError("no elicit method")
        result = await select_multiple(mock_ctx, "Pick:", ["a", "b"])
        assert result == []

    async def test_graceful_on_runtime_error(self, mock_ctx):
        mock_ctx.elicit.side_effect = RuntimeError("broken")
        result = await select_multiple(mock_ctx, "Pick:", ["a", "b"], default=["x"])
        assert result == ["x"]

    async def test_graceful_on_type_error(self, mock_ctx):
        mock_ctx.elicit.side_effect = TypeError("bad schema")
        result = await select_multiple(mock_ctx, "Pick:", ["a", "b"])
        assert result == []

    async def test_prompt_includes_choices(self, mock_ctx):
        mock_data = MultiSelectSchema(selected="a")
        mock_ctx.elicit.return_value = AcceptedElicitation(action="accept", data=mock_data)

        await select_multiple(mock_ctx, "Which?", ["a", "b", "c"])

        call_args = mock_ctx.elicit.call_args
        prompt = call_args[0][0]
        assert "a, b, c" in prompt
        assert "Which?" in prompt
