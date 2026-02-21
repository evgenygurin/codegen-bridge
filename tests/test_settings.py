"""Tests for plugin settings management."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from bridge.settings import PluginSettings, load_settings, save_settings, update_settings

# ── PluginSettings model ──────────────────────────────────────


class TestPluginSettings:
    """Tests for the PluginSettings Pydantic model."""

    def test_defaults(self):
        s = PluginSettings()
        assert s.default_model is None
        assert s.auto_monitor is True
        assert s.poll_interval == 30

    def test_custom_values(self):
        s = PluginSettings(
            default_model="claude-sonnet",
            auto_monitor=False,
            poll_interval=60,
        )
        assert s.default_model == "claude-sonnet"
        assert s.auto_monitor is False
        assert s.poll_interval == 60

    def test_poll_interval_minimum(self):
        with pytest.raises(ValidationError):
            PluginSettings(poll_interval=1)

    def test_poll_interval_maximum(self):
        with pytest.raises(ValidationError):
            PluginSettings(poll_interval=999)

    def test_poll_interval_boundary_low(self):
        s = PluginSettings(poll_interval=5)
        assert s.poll_interval == 5

    def test_poll_interval_boundary_high(self):
        s = PluginSettings(poll_interval=300)
        assert s.poll_interval == 300

    def test_model_dump_json(self):
        s = PluginSettings()
        data = s.model_dump(mode="json")
        assert data == {
            "default_model": None,
            "auto_monitor": True,
            "poll_interval": 30,
        }

    def test_model_validate_from_dict(self):
        s = PluginSettings.model_validate({
            "default_model": "gpt-4",
            "auto_monitor": False,
            "poll_interval": 45,
        })
        assert s.default_model == "gpt-4"
        assert s.auto_monitor is False
        assert s.poll_interval == 45

    def test_partial_dict(self):
        """Missing fields should use defaults."""
        s = PluginSettings.model_validate({"poll_interval": 10})
        assert s.default_model is None
        assert s.auto_monitor is True
        assert s.poll_interval == 10

    def test_extra_fields_ignored(self):
        """Unknown fields should not cause errors (strict=False default)."""
        s = PluginSettings.model_validate({"unknown_field": 123})
        assert s.default_model is None


# ── load_settings ─────────────────────────────────────────────


class TestLoadSettings:
    def test_loads_from_file(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({
            "default_model": "claude-sonnet",
            "auto_monitor": False,
            "poll_interval": 60,
        }))
        result = load_settings(settings_file)
        assert result.default_model == "claude-sonnet"
        assert result.auto_monitor is False
        assert result.poll_interval == 60

    def test_returns_defaults_when_file_missing(self, tmp_path):
        result = load_settings(tmp_path / "nonexistent.json")
        assert result == PluginSettings()

    def test_returns_defaults_for_invalid_json(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("not valid json{{{")
        result = load_settings(settings_file)
        assert result == PluginSettings()

    def test_returns_defaults_for_invalid_values(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"poll_interval": -1}))
        result = load_settings(settings_file)
        assert result == PluginSettings()

    def test_loads_partial_settings(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"auto_monitor": False}))
        result = load_settings(settings_file)
        assert result.auto_monitor is False
        assert result.default_model is None
        assert result.poll_interval == 30

    def test_loads_empty_object(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("{}")
        result = load_settings(settings_file)
        assert result == PluginSettings()

    def test_loads_null_model(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"default_model": None}))
        result = load_settings(settings_file)
        assert result.default_model is None


# ── save_settings ─────────────────────────────────────────────


class TestSaveSettings:
    def test_saves_to_file(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings = PluginSettings(
            default_model="claude-sonnet",
            auto_monitor=False,
            poll_interval=45,
        )
        result_path = save_settings(settings, settings_file)
        assert result_path == settings_file

        raw = json.loads(settings_file.read_text())
        assert raw["default_model"] == "claude-sonnet"
        assert raw["auto_monitor"] is False
        assert raw["poll_interval"] == 45

    def test_creates_parent_dirs(self, tmp_path):
        settings_file = tmp_path / "nested" / "dir" / "settings.json"
        settings = PluginSettings()
        save_settings(settings, settings_file)
        assert settings_file.is_file()

    def test_overwrites_existing_file(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"poll_interval": 10}))

        settings = PluginSettings(poll_interval=90)
        save_settings(settings, settings_file)

        raw = json.loads(settings_file.read_text())
        assert raw["poll_interval"] == 90

    def test_roundtrip(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        original = PluginSettings(
            default_model="gpt-4",
            auto_monitor=False,
            poll_interval=120,
        )
        save_settings(original, settings_file)
        loaded = load_settings(settings_file)
        assert loaded == original

    def test_file_ends_with_newline(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        save_settings(PluginSettings(), settings_file)
        content = settings_file.read_text()
        assert content.endswith("\n")

    def test_file_is_pretty_printed(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        save_settings(PluginSettings(), settings_file)
        content = settings_file.read_text()
        # Pretty-printed JSON has newlines in the body
        assert "\n" in content.rstrip()


# ── update_settings ──────────────────────────────────────────


class TestUpdateSettings:
    def test_updates_single_field(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({
            "default_model": None,
            "auto_monitor": True,
            "poll_interval": 30,
        }))

        result = update_settings({"poll_interval": 60}, settings_file)
        assert result.poll_interval == 60
        assert result.auto_monitor is True  # unchanged

        # Verify persisted
        raw = json.loads(settings_file.read_text())
        assert raw["poll_interval"] == 60

    def test_updates_multiple_fields(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({
            "default_model": None,
            "auto_monitor": True,
            "poll_interval": 30,
        }))

        result = update_settings(
            {"default_model": "claude-sonnet", "auto_monitor": False},
            settings_file,
        )
        assert result.default_model == "claude-sonnet"
        assert result.auto_monitor is False
        assert result.poll_interval == 30

    def test_rejects_unknown_fields(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("{}")

        with pytest.raises(ValueError, match="Unknown settings"):
            update_settings({"nonexistent_field": "value"}, settings_file)

    def test_rejects_invalid_values(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("{}")

        with pytest.raises(ValueError):
            update_settings({"poll_interval": 1}, settings_file)

    def test_creates_file_if_missing(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        # File doesn't exist — load_settings returns defaults
        result = update_settings({"poll_interval": 90}, settings_file)
        assert result.poll_interval == 90
        assert settings_file.is_file()

    def test_set_model_to_null(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"default_model": "gpt-4"}))

        result = update_settings({"default_model": None}, settings_file)
        assert result.default_model is None
