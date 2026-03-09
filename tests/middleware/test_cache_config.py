"""Tests for caching configuration with real-time tool exclusions."""

from __future__ import annotations

from bridge.middleware.config import CachingConfig


class TestCachingConfigRealtimeTools:
    def test_default_realtime_tools(self):
        """Default config includes the five real-time tools."""
        cfg = CachingConfig()
        assert "codegen_get_run" in cfg.realtime_tools
        assert "codegen_list_runs" in cfg.realtime_tools
        assert "codegen_get_run_logs" in cfg.realtime_tools
        assert "codegen_get_execution_context" in cfg.realtime_tools
        assert "codegen_get_session_preferences" in cfg.realtime_tools
        assert len(cfg.realtime_tools) == 5

    def test_custom_realtime_tools(self):
        """Custom realtime_tools override the default list."""
        cfg = CachingConfig(realtime_tools=["my_custom_tool"])
        assert cfg.realtime_tools == ["my_custom_tool"]

    def test_empty_realtime_tools(self):
        """Empty list means all tools are cached."""
        cfg = CachingConfig(realtime_tools=[])
        assert cfg.realtime_tools == []

    def test_realtime_tools_does_not_share_state(self):
        """Each CachingConfig instance gets its own list (no mutable default sharing)."""
        a = CachingConfig()
        b = CachingConfig()
        a.realtime_tools.append("extra_tool")
        assert "extra_tool" not in b.realtime_tools
