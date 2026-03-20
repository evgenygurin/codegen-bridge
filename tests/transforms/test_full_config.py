"""Tests for full transform configuration: Namespace, Visibility, VersionFilter.

Verifies that each transform type works end-to-end via the in-memory MCP
client, and that combined configurations compose correctly.
"""

from __future__ import annotations

from fastmcp import Client, FastMCP

from bridge.transforms import (
    NamespaceConfig,
    TransformsConfig,
    VersionFilterConfig,
    VisibilityConfig,
    VisibilityRuleConfig,
    configure_transforms,
)

# ── Helpers ────────────────────────────────────────────────


def _server_with_tagged_tools() -> FastMCP:
    """Server with tools bearing different tags for visibility tests."""
    mcp = FastMCP("test-visibility")

    @mcp.tool(tags={"setup"})
    def setup_orgs() -> str:
        """List orgs."""
        return "orgs"

    @mcp.tool(tags={"setup"})
    def setup_repos() -> str:
        """List repos."""
        return "repos"

    @mcp.tool(tags={"agent"})
    def agent_create_run(prompt: str) -> str:
        """Create run."""
        return f"run:{prompt}"

    @mcp.tool(tags={"agent"})
    def agent_get_run(run_id: int) -> str:
        """Get run."""
        return f"run:{run_id}"

    @mcp.tool(tags={"dangerous", "agent"})
    def agent_stop_run(run_id: int) -> str:
        """Stop run."""
        return f"stopped:{run_id}"

    return mcp


def _server_with_versioned_tools() -> FastMCP:
    """Server with versioned tools for version filter tests."""
    mcp = FastMCP("test-version")

    @mcp.tool(version="1.0")
    def legacy_tool() -> str:
        return "legacy"

    @mcp.tool(version="1.5")
    def stable_tool() -> str:
        return "stable"

    @mcp.tool(version="2.0")
    def current_tool() -> str:
        return "current"

    @mcp.tool(version="3.0")
    def future_tool() -> str:
        return "future"

    @mcp.tool()
    def unversioned_tool() -> str:
        return "unversioned"

    return mcp


# ── Namespace ─────────────────────────────────────────────


class TestNamespaceFullConfig:
    """Namespace transform adds a prefix to all tool names."""

    async def test_prefix_applied_to_all_tools(self):
        mcp = _server_with_tagged_tools()
        configure_transforms(
            mcp,
            TransformsConfig(namespace=NamespaceConfig(prefix="cg")),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        # All tools must have the prefix
        assert all(n.startswith("cg_") for n in names), f"Unprefixed tools: {names}"
        assert "cg_setup_orgs" in names
        assert "cg_agent_create_run" in names

    async def test_prefixed_tool_callable(self):
        mcp = _server_with_tagged_tools()
        configure_transforms(
            mcp,
            TransformsConfig(namespace=NamespaceConfig(prefix="cg")),
        )

        async with Client(mcp) as client:
            result = await client.call_tool("cg_setup_orgs", {})

        assert result.data == "orgs"

    async def test_original_name_gone(self):
        mcp = _server_with_tagged_tools()
        configure_transforms(
            mcp,
            TransformsConfig(namespace=NamespaceConfig(prefix="cg")),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "setup_orgs" not in names
        assert "agent_create_run" not in names

    async def test_disabled_namespace_is_noop(self):
        mcp = _server_with_tagged_tools()
        configure_transforms(
            mcp,
            TransformsConfig(namespace=NamespaceConfig(prefix="cg", enabled=False)),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "setup_orgs" in names
        assert "cg_setup_orgs" not in names


# ── Visibility ────────────────────────────────────────────


class TestVisibilityFullConfig:
    """Visibility transform hides tools by tag or name."""

    async def test_hide_by_tag(self):
        mcp = _server_with_tagged_tools()
        configure_transforms(
            mcp,
            TransformsConfig(
                visibility=VisibilityConfig(
                    rules=[
                        VisibilityRuleConfig(enabled=False, tags={"dangerous"}),
                    ]
                )
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "agent_stop_run" not in names
        # Non-dangerous tools remain
        assert "setup_orgs" in names
        assert "agent_create_run" in names

    async def test_show_only_matching_tag(self):
        mcp = _server_with_tagged_tools()
        configure_transforms(
            mcp,
            TransformsConfig(
                visibility=VisibilityConfig(
                    rules=[
                        VisibilityRuleConfig(enabled=False, match_all=True),
                        VisibilityRuleConfig(enabled=True, tags={"setup"}),
                    ]
                )
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert names == {"setup_orgs", "setup_repos"}

    async def test_hide_by_name(self):
        mcp = _server_with_tagged_tools()
        configure_transforms(
            mcp,
            TransformsConfig(
                visibility=VisibilityConfig(
                    rules=[
                        VisibilityRuleConfig(
                            enabled=False,
                            names={"setup_orgs", "agent_stop_run"},
                        ),
                    ]
                )
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "setup_orgs" not in names
        assert "agent_stop_run" not in names
        assert "setup_repos" in names
        assert "agent_create_run" in names

    async def test_disabled_visibility_is_noop(self):
        mcp = _server_with_tagged_tools()
        configure_transforms(
            mcp,
            TransformsConfig(
                visibility=VisibilityConfig(
                    enabled=False,
                    rules=[
                        VisibilityRuleConfig(enabled=False, match_all=True),
                    ],
                )
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()

        assert len(tools) == 5  # all tools visible


# ── Version Filter ────────────────────────────────────────


class TestVersionFilterFullConfig:
    """VersionFilter gates tools by semantic version range."""

    async def test_range_filter(self):
        mcp = _server_with_versioned_tools()
        configure_transforms(
            mcp,
            TransformsConfig(
                version_filter=VersionFilterConfig(
                    version_gte="1.5",
                    version_lt="3.0",
                )
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "stable_tool" in names
        assert "current_tool" in names
        assert "legacy_tool" not in names
        assert "future_tool" not in names

    async def test_lower_bound_only(self):
        mcp = _server_with_versioned_tools()
        configure_transforms(
            mcp,
            TransformsConfig(
                version_filter=VersionFilterConfig(version_gte="2.0"),
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "current_tool" in names
        assert "future_tool" in names
        assert "legacy_tool" not in names
        assert "stable_tool" not in names

    async def test_upper_bound_only(self):
        mcp = _server_with_versioned_tools()
        configure_transforms(
            mcp,
            TransformsConfig(
                version_filter=VersionFilterConfig(version_lt="2.0"),
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "legacy_tool" in names
        assert "stable_tool" in names
        assert "current_tool" not in names
        assert "future_tool" not in names

    async def test_disabled_filter_is_noop(self):
        mcp = _server_with_versioned_tools()
        configure_transforms(
            mcp,
            TransformsConfig(
                version_filter=VersionFilterConfig(enabled=False, version_gte="99.0"),
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()

        # All 5 tools visible when filter disabled
        assert len(tools) == 5


# ── Combined ──────────────────────────────────────────────


class TestCombinedFullConfig:
    """Multiple transforms composed together."""

    async def test_namespace_plus_visibility(self):
        mcp = _server_with_tagged_tools()
        configure_transforms(
            mcp,
            TransformsConfig(
                namespace=NamespaceConfig(prefix="cg"),
                visibility=VisibilityConfig(
                    rules=[
                        VisibilityRuleConfig(enabled=False, tags={"dangerous"}),
                    ]
                ),
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        # Namespace applied
        assert "cg_setup_orgs" in names
        # Dangerous hidden
        assert "cg_agent_stop_run" not in names
        assert "agent_stop_run" not in names

    async def test_namespace_plus_version_filter(self):
        mcp = _server_with_versioned_tools()
        configure_transforms(
            mcp,
            TransformsConfig(
                namespace=NamespaceConfig(prefix="api"),
                version_filter=VersionFilterConfig(version_gte="2.0", version_lt="3.0"),
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "api_current_tool" in names
        assert "api_legacy_tool" not in names
        assert "api_future_tool" not in names

    async def test_all_three_transforms(self):
        """Namespace + Visibility + VersionFilter composed."""
        mcp = FastMCP("test-all")

        @mcp.tool(tags={"setup"}, version="1.0")
        def setup_v1() -> str:
            return "setup-v1"

        @mcp.tool(tags={"setup"}, version="2.0")
        def setup_v2() -> str:
            return "setup-v2"

        @mcp.tool(tags={"agent"}, version="1.0")
        def agent_v1() -> str:
            return "agent-v1"

        @mcp.tool(tags={"agent"}, version="2.0")
        def agent_v2() -> str:
            return "agent-v2"

        configure_transforms(
            mcp,
            TransformsConfig(
                namespace=NamespaceConfig(prefix="cg"),
                visibility=VisibilityConfig(
                    rules=[
                        VisibilityRuleConfig(enabled=False, tags={"agent"}),
                    ]
                ),
                version_filter=VersionFilterConfig(version_gte="2.0"),
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        # Only setup v2 passes all filters:
        # - namespace: cg_ prefix
        # - visibility: agent hidden
        # - version: >= 2.0 only
        assert "cg_setup_v2" in names
        assert "cg_setup_v1" not in names  # version < 2.0
        assert "cg_agent_v2" not in names  # hidden by tag
        assert "cg_agent_v1" not in names  # hidden by tag + version
