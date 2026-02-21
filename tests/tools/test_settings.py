"""Tests for settings management tools."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client

from bridge.settings import _DEFAULT_SETTINGS_PATH
from bridge.tools.settings import _parse_value

# Default settings content to restore between tests
_DEFAULT_SETTINGS = {
    "default_model": None,
    "auto_monitor": True,
    "poll_interval": 30,
}


@pytest.fixture(autouse=True)
def _restore_settings():
    """Restore settings.json to defaults before and after each test."""
    _write_defaults()
    yield
    _write_defaults()


def _write_defaults():
    """Write default settings to the settings file."""
    _DEFAULT_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DEFAULT_SETTINGS_PATH.write_text(
        json.dumps(_DEFAULT_SETTINGS, indent=2) + "\n",
        encoding="utf-8",
    )


# ── _parse_value helper ─────────────────────────────────────


class TestParseValue:
    """Tests for the string-to-type parser."""

    def test_null(self):
        assert _parse_value("null") is None

    def test_none(self):
        assert _parse_value("none") is None

    def test_null_uppercase(self):
        assert _parse_value("NULL") is None

    def test_true(self):
        assert _parse_value("true") is True

    def test_false(self):
        assert _parse_value("false") is False

    def test_true_uppercase(self):
        assert _parse_value("True") is True

    def test_false_uppercase(self):
        assert _parse_value("False") is False

    def test_integer(self):
        assert _parse_value("60") == 60

    def test_negative_integer(self):
        assert _parse_value("-1") == -1

    def test_string(self):
        assert _parse_value("claude-sonnet") == "claude-sonnet"

    def test_string_with_spaces(self):
        assert _parse_value("  claude-sonnet  ") == "claude-sonnet"

    def test_empty_looking_string(self):
        assert _parse_value("some-model") == "some-model"


# ── Tool registration ──────────────────────────────────────


class TestSettingsToolRegistration:
    async def test_get_settings_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_get_settings" in names

    async def test_update_settings_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_update_settings" in names

    async def test_get_settings_has_description(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_get_settings")
        assert "settings" in tool.description.lower()

    async def test_update_settings_has_description(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_update_settings")
        assert "setting" in tool.description.lower()

    async def test_settings_tools_tagged(self, client: Client):
        tools = await client.list_tools()
        for tool in tools:
            if tool.name in ("codegen_get_settings", "codegen_update_settings"):
                tags = tool.meta.get("fastmcp", {}).get("tags", [])
                assert "settings" in tags


# ── Tool execution ─────────────────────────────────────────


class TestGetSettingsTool:
    async def test_returns_default_settings(self, client: Client):
        result = await client.call_tool("codegen_get_settings", {})
        data = json.loads(result.data)
        assert "default_model" in data
        assert "auto_monitor" in data
        assert "poll_interval" in data
        assert data["auto_monitor"] is True
        assert data["poll_interval"] == 30


class TestUpdateSettingsTool:
    async def test_update_poll_interval(self, client: Client):
        result = await client.call_tool(
            "codegen_update_settings",
            {"key": "poll_interval", "value": "60"},
        )
        data = json.loads(result.data)
        assert data["updated"]["poll_interval"] == 60

    async def test_update_auto_monitor(self, client: Client):
        result = await client.call_tool(
            "codegen_update_settings",
            {"key": "auto_monitor", "value": "false"},
        )
        data = json.loads(result.data)
        assert data["updated"]["auto_monitor"] is False

    async def test_update_default_model(self, client: Client):
        result = await client.call_tool(
            "codegen_update_settings",
            {"key": "default_model", "value": "claude-sonnet"},
        )
        data = json.loads(result.data)
        assert data["updated"]["default_model"] == "claude-sonnet"

    async def test_update_model_to_null(self, client: Client):
        result = await client.call_tool(
            "codegen_update_settings",
            {"key": "default_model", "value": "null"},
        )
        data = json.loads(result.data)
        assert data["updated"]["default_model"] is None

    async def test_update_unknown_key_returns_error(self, client: Client):
        result = await client.call_tool(
            "codegen_update_settings",
            {"key": "nonexistent_key", "value": "value"},
        )
        data = json.loads(result.data)
        assert "error" in data

    async def test_update_returns_all_settings(self, client: Client):
        result = await client.call_tool(
            "codegen_update_settings",
            {"key": "poll_interval", "value": "45"},
        )
        data = json.loads(result.data)
        assert "all_settings" in data
        assert "default_model" in data["all_settings"]
        assert "auto_monitor" in data["all_settings"]
        assert "poll_interval" in data["all_settings"]
