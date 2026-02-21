"""Tests for transform configuration models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bridge.transforms.config import (
    NamespaceConfig,
    ToolTransformConfig,
    ToolTransformEntry,
    TransformsConfig,
    VersionFilterConfig,
    VisibilityConfig,
    VisibilityRuleConfig,
)

# ── NamespaceConfig ────────────────────────────────────────


class TestNamespaceConfig:
    def test_valid_prefix(self):
        cfg = NamespaceConfig(prefix="codegen")
        assert cfg.prefix == "codegen"
        assert cfg.enabled is True

    def test_prefix_with_underscores(self):
        cfg = NamespaceConfig(prefix="my_api_v2")
        assert cfg.prefix == "my_api_v2"

    def test_prefix_with_numbers(self):
        cfg = NamespaceConfig(prefix="api2")
        assert cfg.prefix == "api2"

    def test_empty_prefix_rejected(self):
        with pytest.raises(ValidationError):
            NamespaceConfig(prefix="")

    def test_uppercase_prefix_rejected(self):
        with pytest.raises(ValidationError):
            NamespaceConfig(prefix="Codegen")

    def test_prefix_starting_with_number_rejected(self):
        with pytest.raises(ValidationError):
            NamespaceConfig(prefix="2api")

    def test_prefix_with_spaces_rejected(self):
        with pytest.raises(ValidationError):
            NamespaceConfig(prefix="my api")

    def test_prefix_with_hyphens_rejected(self):
        with pytest.raises(ValidationError):
            NamespaceConfig(prefix="my-api")

    def test_disabled(self):
        cfg = NamespaceConfig(prefix="codegen", enabled=False)
        assert cfg.enabled is False


# ── ToolTransformEntry ─────────────────────────────────────


class TestToolTransformEntry:
    def test_defaults(self):
        entry = ToolTransformEntry()
        assert entry.name is None
        assert entry.description is None
        assert entry.tags is None
        assert entry.enabled is True

    def test_rename(self):
        entry = ToolTransformEntry(name="short_name")
        assert entry.name == "short_name"

    def test_full_entry(self):
        entry = ToolTransformEntry(
            name="new_name",
            description="Better description",
            tags={"setup", "v2"},
            enabled=True,
        )
        assert entry.name == "new_name"
        assert entry.description == "Better description"
        assert entry.tags == {"setup", "v2"}

    def test_disabled_entry(self):
        entry = ToolTransformEntry(enabled=False)
        assert entry.enabled is False


# ── ToolTransformConfig ────────────────────────────────────


class TestToolTransformConfig:
    def test_empty_tools(self):
        cfg = ToolTransformConfig()
        assert cfg.tools == {}
        assert cfg.enabled is True

    def test_with_renames(self):
        cfg = ToolTransformConfig(
            tools={
                "codegen_create_run": ToolTransformEntry(name="create_agent"),
                "codegen_get_run": ToolTransformEntry(name="get_agent"),
            }
        )
        assert len(cfg.tools) == 2
        assert cfg.tools["codegen_create_run"].name == "create_agent"


# ── VisibilityRuleConfig ──────────────────────────────────


class TestVisibilityRuleConfig:
    def test_defaults(self):
        rule = VisibilityRuleConfig()
        assert rule.enabled is True
        assert rule.names is None
        assert rule.tags is None
        assert rule.components is None
        assert rule.match_all is False

    def test_hide_all(self):
        rule = VisibilityRuleConfig(enabled=False, match_all=True)
        assert rule.enabled is False
        assert rule.match_all is True

    def test_show_by_tags(self):
        rule = VisibilityRuleConfig(enabled=True, tags={"setup"})
        assert rule.tags == {"setup"}

    def test_show_by_names(self):
        rule = VisibilityRuleConfig(
            enabled=True,
            names={"codegen_list_orgs", "codegen_list_repos"},
        )
        assert len(rule.names) == 2

    def test_component_type_filter(self):
        rule = VisibilityRuleConfig(
            enabled=True,
            components={"tool", "prompt"},
        )
        assert "tool" in rule.components
        assert "prompt" in rule.components

    def test_invalid_component_type(self):
        with pytest.raises(ValidationError):
            VisibilityRuleConfig(components={"invalid"})


# ── VisibilityConfig ──────────────────────────────────────


class TestVisibilityConfig:
    def test_defaults(self):
        cfg = VisibilityConfig()
        assert cfg.enabled is True
        assert cfg.rules == []

    def test_with_rules(self):
        cfg = VisibilityConfig(
            rules=[
                VisibilityRuleConfig(enabled=False, match_all=True),
                VisibilityRuleConfig(enabled=True, tags={"setup"}),
            ]
        )
        assert len(cfg.rules) == 2
        assert cfg.rules[0].match_all is True
        assert cfg.rules[1].tags == {"setup"}


# ── VersionFilterConfig ──────────────────────────────────


class TestVersionFilterConfig:
    def test_defaults(self):
        cfg = VersionFilterConfig()
        assert cfg.enabled is True
        assert cfg.version_gte is None
        assert cfg.version_lt is None

    def test_range(self):
        cfg = VersionFilterConfig(version_gte="2.0", version_lt="3.0")
        assert cfg.version_gte == "2.0"
        assert cfg.version_lt == "3.0"

    def test_lower_bound_only(self):
        cfg = VersionFilterConfig(version_gte="1.5")
        assert cfg.version_gte == "1.5"
        assert cfg.version_lt is None

    def test_upper_bound_only(self):
        cfg = VersionFilterConfig(version_lt="2.0")
        assert cfg.version_lt == "2.0"
        assert cfg.version_gte is None


# ── TransformsConfig ──────────────────────────────────────


class TestTransformsConfig:
    def test_defaults_passthrough(self):
        cfg = TransformsConfig()
        assert cfg.namespace is None
        assert cfg.tool_transform is None
        assert cfg.visibility is None
        assert cfg.version_filter is None

    def test_with_namespace(self):
        cfg = TransformsConfig(namespace=NamespaceConfig(prefix="api"))
        assert cfg.namespace.prefix == "api"

    def test_combined(self):
        cfg = TransformsConfig(
            namespace=NamespaceConfig(prefix="codegen"),
            tool_transform=ToolTransformConfig(
                tools={"codegen_create_run": ToolTransformEntry(name="create")}
            ),
            visibility=VisibilityConfig(
                rules=[VisibilityRuleConfig(enabled=True, tags={"setup"})]
            ),
            version_filter=VersionFilterConfig(version_gte="1.0"),
        )
        assert cfg.namespace.prefix == "codegen"
        assert len(cfg.tool_transform.tools) == 1
        assert len(cfg.visibility.rules) == 1
        assert cfg.version_filter.version_gte == "1.0"

    def test_json_roundtrip(self):
        cfg = TransformsConfig(
            namespace=NamespaceConfig(prefix="api"),
            visibility=VisibilityConfig(
                rules=[VisibilityRuleConfig(enabled=True, tags={"setup"})]
            ),
        )
        json_str = cfg.model_dump_json()
        restored = TransformsConfig.model_validate_json(json_str)
        assert restored.namespace.prefix == "api"
        assert restored.visibility.rules[0].tags == {"setup"}


# ── Profiles ──────────────────────────────────────────────


class TestProfiles:
    def test_passthrough(self):
        cfg = TransformsConfig.passthrough()
        assert cfg.namespace is None
        assert cfg.tool_transform is None
        assert cfg.visibility is None
        assert cfg.version_filter is None

    def test_namespaced(self):
        cfg = TransformsConfig.namespaced("codegen")
        assert cfg.namespace is not None
        assert cfg.namespace.prefix == "codegen"
        assert cfg.visibility is None

    def test_setup_only(self):
        cfg = TransformsConfig.setup_only()
        assert cfg.visibility is not None
        assert len(cfg.visibility.rules) == 2
        # First rule: hide all
        assert cfg.visibility.rules[0].enabled is False
        assert cfg.visibility.rules[0].match_all is True
        # Second rule: show setup
        assert cfg.visibility.rules[1].enabled is True
        assert "setup" in cfg.visibility.rules[1].tags

    def test_execution_only(self):
        cfg = TransformsConfig.execution_only()
        assert cfg.visibility is not None
        assert len(cfg.visibility.rules) == 2
        assert cfg.visibility.rules[1].tags == {
            "execution",
            "context",
            "monitoring",
        }

    def test_versioned(self):
        cfg = TransformsConfig.versioned(version_gte="2.0", version_lt="3.0")
        assert cfg.version_filter is not None
        assert cfg.version_filter.version_gte == "2.0"
        assert cfg.version_filter.version_lt == "3.0"

    def test_versioned_lower_only(self):
        cfg = TransformsConfig.versioned(version_gte="1.0")
        assert cfg.version_filter.version_gte == "1.0"
        assert cfg.version_filter.version_lt is None
