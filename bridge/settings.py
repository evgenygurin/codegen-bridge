"""Plugin settings management.

Loads, validates, and persists plugin settings from
``.claude-plugin/settings.json``.  Settings are exposed as a Pydantic model
and can be read/updated at runtime through MCP tools.

Default settings file location::

    <project_root>/.claude-plugin/settings.json

Default values:
    - ``default_model``: ``null`` (use organization default)
    - ``auto_monitor``: ``true`` (automatically poll runs after creation)
    - ``poll_interval``: ``30`` (seconds between status polls)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("bridge.settings")

# Default path relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SETTINGS_PATH = _PROJECT_ROOT / ".claude-plugin" / "settings.json"


class PluginSettings(BaseModel):
    """Plugin settings with defaults.

    All fields are optional with sensible defaults so the settings file
    can be empty or partially populated.
    """

    default_model: str | None = Field(
        default=None,
        description="Default LLM model for agent runs. null = use organization default.",
    )
    auto_monitor: bool = Field(
        default=True,
        description="Automatically poll agent runs after creation.",
    )
    poll_interval: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Seconds between status polls (5-300).",
    )


def load_settings(path: str | Path | None = None) -> PluginSettings:
    """Load plugin settings from disk.

    Args:
        path: Override path to settings.json.
            Defaults to ``<project>/.claude-plugin/settings.json``.

    Returns:
        Validated ``PluginSettings`` instance.  If the file doesn't exist
        or is unreadable, returns defaults.
    """
    settings_path = Path(path) if path else _DEFAULT_SETTINGS_PATH

    if not settings_path.is_file():
        logger.info("Settings file not found: %s — using defaults", settings_path)
        return PluginSettings()

    try:
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
        settings = PluginSettings.model_validate(raw)
        logger.info("Loaded settings from %s", settings_path)
        return settings
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read settings file %s: %s — using defaults", settings_path, exc)
        return PluginSettings()
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid settings in %s: %s — using defaults", settings_path, exc)
        return PluginSettings()


def save_settings(
    settings: PluginSettings,
    path: str | Path | None = None,
) -> Path:
    """Persist plugin settings to disk.

    Args:
        settings: The settings to save.
        path: Override path to settings.json.
            Defaults to ``<project>/.claude-plugin/settings.json``.

    Returns:
        The path the settings were written to.

    Raises:
        OSError: If the file cannot be written.
    """
    settings_path = Path(path) if path else _DEFAULT_SETTINGS_PATH
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    data = settings.model_dump(mode="json")
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    logger.info("Saved settings to %s", settings_path)
    return settings_path


def update_settings(
    updates: dict[str, Any],
    path: str | Path | None = None,
) -> PluginSettings:
    """Load settings, apply updates, validate, and save.

    Args:
        updates: Dictionary of field names to new values.
        path: Override path to settings.json.

    Returns:
        The updated and validated ``PluginSettings``.

    Raises:
        ValueError: If a field name is unknown or a value is invalid.
    """
    current = load_settings(path)
    current_data = current.model_dump()

    unknown = set(updates) - set(current_data)
    if unknown:
        raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")

    current_data.update(updates)
    updated = PluginSettings.model_validate(current_data)
    save_settings(updated, path)
    return updated
