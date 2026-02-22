"""Integration tests for transforms with a live FastMCP server and client.

These tests verify that transforms actually modify what clients see,
using the in-memory MCP client for fast, isolated tests.
"""

from __future__ import annotations

from fastmcp import Client, FastMCP

from bridge.transforms import (
    NamespaceConfig,
    ToolTransformConfig,
    ToolTransformEntry,
    TransformsConfig,
    VersionFilterConfig,
    VisibilityConfig,
    VisibilityRuleConfig,
    configure_transforms,
)

# ── Helpers ────────────────────────────────────────────────


def _make_server(*, name: str = "test") -> FastMCP:
    """Create a test server with tagged tools, resources, and prompts."""
    mcp = FastMCP(name)

    @mcp.tool(tags={"setup"})
    def list_orgs() -> str:
        """List organizations."""
        return "orgs"

    @mcp.tool(tags={"setup"})
    def list_repos() -> str:
        """List repositories."""
        return "repos"

    @mcp.tool(tags={"execution"})
    def create_run(prompt: str) -> str:
        """Create an agent run."""
        return f"run: {prompt}"

    @mcp.tool(tags={"execution"})
    def get_run(run_id: int) -> str:
        """Get a run."""
        return f"run {run_id}"

    @mcp.tool(tags={"monitoring"})
    def get_logs(run_id: int) -> str:
        """Get logs."""
        return f"logs {run_id}"

    @mcp.resource("test://config")
    def config_resource() -> str:
        return "config"

    @mcp.prompt()
    def task_prompt(description: str) -> str:
        return f"Task: {description}"

    return mcp


# ── Namespace ──────────────────────────────────────────────


class TestNamespaceIntegration:
    async def test_tools_prefixed(self):
        mcp = _make_server()
        configure_transforms(mcp, TransformsConfig.namespaced("codegen"))

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "codegen_list_orgs" in names
        assert "codegen_create_run" in names
        assert "list_orgs" not in names

    async def test_prompts_prefixed(self):
        mcp = _make_server()
        configure_transforms(mcp, TransformsConfig.namespaced("codegen"))

        async with Client(mcp) as client:
            prompts = await client.list_prompts()
            names = {p.name for p in prompts}

        assert "codegen_task_prompt" in names
        assert "task_prompt" not in names

    async def test_resources_prefixed(self):
        mcp = _make_server()
        configure_transforms(mcp, TransformsConfig.namespaced("codegen"))

        async with Client(mcp) as client:
            resources = await client.list_resources()
            uris = {str(r.uri) for r in resources}

        assert any("codegen" in uri for uri in uris)

    async def test_tool_callable_after_namespace(self):
        mcp = _make_server()
        configure_transforms(mcp, TransformsConfig.namespaced("ns"))

        async with Client(mcp) as client:
            result = await client.call_tool("ns_list_orgs", {})

        assert result.data == "orgs"

    async def test_passthrough_no_prefix(self):
        mcp = _make_server()
        configure_transforms(mcp)

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "list_orgs" in names
        assert "create_run" in names


# ── Tool Transform ─────────────────────────────────────────


class TestToolTransformIntegration:
    async def test_rename_tool(self):
        mcp = _make_server()
        configure_transforms(
            mcp,
            TransformsConfig(
                tool_transform=ToolTransformConfig(
                    tools={
                        "list_orgs": ToolTransformEntry(name="orgs"),
                        "create_run": ToolTransformEntry(name="run"),
                    }
                )
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "orgs" in names
        assert "run" in names
        assert "list_orgs" not in names
        assert "create_run" not in names

    async def test_renamed_tool_callable(self):
        mcp = _make_server()
        configure_transforms(
            mcp,
            TransformsConfig(
                tool_transform=ToolTransformConfig(
                    tools={"list_repos": ToolTransformEntry(name="repos")}
                )
            ),
        )

        async with Client(mcp) as client:
            result = await client.call_tool("repos", {})

        assert result.data == "repos"

    async def test_redescribe_tool(self):
        mcp = _make_server()
        configure_transforms(
            mcp,
            TransformsConfig(
                tool_transform=ToolTransformConfig(
                    tools={
                        "list_orgs": ToolTransformEntry(description="Fetch all organizations."),
                    }
                )
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            tool = next(t for t in tools if t.name == "list_orgs")

        assert tool.description == "Fetch all organizations."

    async def test_hide_tool_via_enabled_false(self):
        mcp = _make_server()
        configure_transforms(
            mcp,
            TransformsConfig(
                tool_transform=ToolTransformConfig(
                    tools={"get_logs": ToolTransformEntry(enabled=False)}
                )
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "get_logs" not in names
        # Others remain
        assert "list_orgs" in names

    async def test_namespace_plus_rename(self):
        """Namespace runs first, then ToolTransform sees namespaced names."""
        mcp = _make_server()
        configure_transforms(
            mcp,
            TransformsConfig(
                namespace=NamespaceConfig(prefix="api"),
                tool_transform=ToolTransformConfig(
                    tools={
                        "api_list_orgs": ToolTransformEntry(name="orgs"),
                    }
                ),
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "orgs" in names
        assert "api_list_orgs" not in names
        # Other tools still have namespace prefix
        assert "api_create_run" in names


# ── Visibility ─────────────────────────────────────────────


class TestVisibilityIntegration:
    async def test_show_only_setup_tools(self):
        mcp = _make_server()
        configure_transforms(mcp, TransformsConfig.setup_only())

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "list_orgs" in names
        assert "list_repos" in names
        assert "create_run" not in names
        assert "get_run" not in names
        assert "get_logs" not in names

    async def test_show_only_execution_tools(self):
        mcp = _make_server()
        configure_transforms(mcp, TransformsConfig.execution_only())

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "create_run" in names
        assert "get_run" in names
        assert "get_logs" in names
        assert "list_orgs" not in names
        assert "list_repos" not in names

    async def test_hide_by_name(self):
        mcp = _make_server()
        configure_transforms(
            mcp,
            TransformsConfig(
                visibility=VisibilityConfig(
                    rules=[
                        VisibilityRuleConfig(
                            enabled=False,
                            names={"get_logs"},
                        )
                    ]
                )
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "get_logs" not in names
        assert "list_orgs" in names
        assert "create_run" in names

    async def test_show_all_by_default(self):
        """Empty visibility config shows everything."""
        mcp = _make_server()
        configure_transforms(
            mcp,
            TransformsConfig(visibility=VisibilityConfig()),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()

        assert len(tools) == 5

    async def test_visibility_component_scoping(self):
        """Visibility rules with ``components`` scope to specific types.

        When ``components={"tool"}`` is set, the rule only marks tools.
        Here we hide all tools, then re-enable setup tools — non-tool
        components remain untouched by these rules.
        """
        mcp = _make_server()
        configure_transforms(
            mcp,
            TransformsConfig(
                visibility=VisibilityConfig(
                    rules=[
                        VisibilityRuleConfig(
                            enabled=False,
                            match_all=True,
                            components={"tool"},
                        ),
                        VisibilityRuleConfig(
                            enabled=True,
                            tags={"setup"},
                            components={"tool"},
                        ),
                    ]
                )
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        # Only setup tools should be visible
        assert "list_orgs" in names
        assert "list_repos" in names
        assert "create_run" not in names
        assert "get_logs" not in names


# ── Version Filter ─────────────────────────────────────────


class TestVersionFilterIntegration:
    async def test_version_filter_with_versioned_tools(self):
        """VersionFilter keeps tools within the specified range."""
        mcp = FastMCP("test")

        @mcp.tool(version="1.0")
        def tool_v1() -> str:
            return "v1"

        @mcp.tool(version="2.0")
        def tool_v2() -> str:
            return "v2"

        @mcp.tool(version="3.0")
        def tool_v3() -> str:
            return "v3"

        configure_transforms(
            mcp,
            TransformsConfig(
                version_filter=VersionFilterConfig(
                    version_gte="2.0",
                    version_lt="3.0",
                )
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "tool_v2" in names
        assert "tool_v1" not in names
        assert "tool_v3" not in names

    async def test_version_filter_lower_bound(self):
        mcp = FastMCP("test")

        @mcp.tool(version="1.0")
        def old_tool() -> str:
            return "old"

        @mcp.tool(version="2.0")
        def new_tool() -> str:
            return "new"

        configure_transforms(
            mcp,
            TransformsConfig(version_filter=VersionFilterConfig(version_gte="2.0")),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "new_tool" in names
        assert "old_tool" not in names

    async def test_version_filter_upper_bound(self):
        mcp = FastMCP("test")

        @mcp.tool(version="1.0")
        def stable_tool() -> str:
            return "stable"

        @mcp.tool(version="3.0")
        def beta_tool() -> str:
            return "beta"

        configure_transforms(
            mcp,
            TransformsConfig(version_filter=VersionFilterConfig(version_lt="2.0")),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "stable_tool" in names
        assert "beta_tool" not in names


# ── Combined Transforms ───────────────────────────────────


class TestCombinedTransforms:
    async def test_namespace_plus_visibility(self):
        """Namespace + visibility profile work together."""
        mcp = _make_server()
        configure_transforms(
            mcp,
            TransformsConfig(
                namespace=NamespaceConfig(prefix="cg"),
                visibility=VisibilityConfig(
                    rules=[
                        VisibilityRuleConfig(enabled=False, match_all=True),
                        VisibilityRuleConfig(enabled=True, tags={"setup"}),
                    ]
                ),
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "cg_list_orgs" in names
        assert "cg_list_repos" in names
        assert "cg_create_run" not in names

    async def test_full_pipeline(self):
        """Namespace + rename + visibility all composed."""
        mcp = _make_server()
        configure_transforms(
            mcp,
            TransformsConfig(
                namespace=NamespaceConfig(prefix="api"),
                tool_transform=ToolTransformConfig(
                    tools={
                        "api_list_orgs": ToolTransformEntry(name="orgs"),
                    }
                ),
                visibility=VisibilityConfig(
                    rules=[
                        VisibilityRuleConfig(
                            enabled=False,
                            names={"api_get_logs"},
                        ),
                    ]
                ),
            ),
        )

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "orgs" in names
        assert "api_list_orgs" not in names
        assert "api_create_run" in names
        assert "api_get_logs" not in names


# ── Edge Cases ────────────────────────────────────────────


class TestEdgeCases:
    async def test_passthrough_preserves_all(self):
        """Passthrough config doesn't alter any components."""
        mcp = _make_server()
        configure_transforms(mcp, TransformsConfig.passthrough())

        async with Client(mcp) as client:
            tools = await client.list_tools()
            resources = await client.list_resources()
            prompts = await client.list_prompts()

        assert len(tools) == 5
        assert len(resources) == 1
        assert len(prompts) == 1

    async def test_server_with_no_transforms(self):
        """Server with configure_transforms(mcp) behaves normally."""
        mcp = _make_server()
        configure_transforms(mcp)

        async with Client(mcp) as client:
            tools = await client.list_tools()
            result = await client.call_tool("list_orgs", {})

        assert len(tools) == 5
        assert result.data == "orgs"

    async def test_double_namespace(self):
        """Two namespace transforms stack."""
        mcp = _make_server()
        configure_transforms(mcp, TransformsConfig.namespaced("inner"))
        configure_transforms(mcp, TransformsConfig.namespaced("outer"))

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "outer_inner_list_orgs" in names
