"""Tests for transform registry — building and applying transforms."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.transforms import (
    Namespace,
    ToolTransform,
    VersionFilter,
    Visibility,
)

from bridge.transforms.config import (
    NamespaceConfig,
    ToolTransformConfig,
    ToolTransformEntry,
    TransformsConfig,
    VersionFilterConfig,
    VisibilityConfig,
    VisibilityRuleConfig,
)
from bridge.transforms.registry import _build_chain, configure_transforms

# ── _build_chain ──────────────────────────────────────────


class TestBuildChain:
    def test_empty_config_returns_no_transforms(self):
        chain = _build_chain(TransformsConfig())
        assert chain == []

    def test_namespace_only(self):
        cfg = TransformsConfig(namespace=NamespaceConfig(prefix="api"))
        chain = _build_chain(cfg)
        assert len(chain) == 1
        assert isinstance(chain[0], Namespace)

    def test_disabled_namespace_skipped(self):
        cfg = TransformsConfig(namespace=NamespaceConfig(prefix="api", enabled=False))
        chain = _build_chain(cfg)
        assert chain == []

    def test_tool_transform_only(self):
        cfg = TransformsConfig(
            tool_transform=ToolTransformConfig(
                tools={"my_tool": ToolTransformEntry(name="new_tool")}
            )
        )
        chain = _build_chain(cfg)
        assert len(chain) == 1
        assert isinstance(chain[0], ToolTransform)

    def test_empty_tool_transform_skipped(self):
        cfg = TransformsConfig(tool_transform=ToolTransformConfig(tools={}))
        chain = _build_chain(cfg)
        assert chain == []

    def test_disabled_tool_transform_skipped(self):
        cfg = TransformsConfig(
            tool_transform=ToolTransformConfig(
                enabled=False,
                tools={"my_tool": ToolTransformEntry(name="new_tool")},
            )
        )
        chain = _build_chain(cfg)
        assert chain == []

    def test_visibility_single_rule(self):
        cfg = TransformsConfig(
            visibility=VisibilityConfig(rules=[VisibilityRuleConfig(enabled=True, tags={"setup"})])
        )
        chain = _build_chain(cfg)
        assert len(chain) == 1
        assert isinstance(chain[0], Visibility)

    def test_visibility_multiple_rules(self):
        cfg = TransformsConfig(
            visibility=VisibilityConfig(
                rules=[
                    VisibilityRuleConfig(enabled=False, match_all=True),
                    VisibilityRuleConfig(enabled=True, tags={"setup"}),
                ]
            )
        )
        chain = _build_chain(cfg)
        assert len(chain) == 2
        assert all(isinstance(t, Visibility) for t in chain)

    def test_disabled_visibility_skipped(self):
        cfg = TransformsConfig(
            visibility=VisibilityConfig(
                enabled=False,
                rules=[VisibilityRuleConfig(enabled=True, tags={"setup"})],
            )
        )
        chain = _build_chain(cfg)
        assert chain == []

    def test_empty_visibility_rules_skipped(self):
        cfg = TransformsConfig(visibility=VisibilityConfig(rules=[]))
        chain = _build_chain(cfg)
        assert chain == []

    def test_version_filter_only(self):
        cfg = TransformsConfig(
            version_filter=VersionFilterConfig(version_gte="1.0", version_lt="2.0")
        )
        chain = _build_chain(cfg)
        assert len(chain) == 1
        assert isinstance(chain[0], VersionFilter)

    def test_disabled_version_filter_skipped(self):
        cfg = TransformsConfig(
            version_filter=VersionFilterConfig(enabled=False, version_gte="1.0")
        )
        chain = _build_chain(cfg)
        assert chain == []

    def test_ordering_namespace_before_tool_transform(self):
        """Namespace must come before ToolTransform in the chain."""
        cfg = TransformsConfig(
            namespace=NamespaceConfig(prefix="api"),
            tool_transform=ToolTransformConfig(
                tools={"api_my_tool": ToolTransformEntry(name="short")}
            ),
        )
        chain = _build_chain(cfg)
        assert len(chain) == 2
        assert isinstance(chain[0], Namespace)
        assert isinstance(chain[1], ToolTransform)

    def test_ordering_visibility_before_version_filter(self):
        """Visibility must come before VersionFilter in the chain."""
        cfg = TransformsConfig(
            visibility=VisibilityConfig(
                rules=[VisibilityRuleConfig(enabled=True, tags={"setup"})]
            ),
            version_filter=VersionFilterConfig(version_gte="1.0"),
        )
        chain = _build_chain(cfg)
        assert len(chain) == 2
        assert isinstance(chain[0], Visibility)
        assert isinstance(chain[1], VersionFilter)

    def test_full_chain_ordering(self):
        """All four transforms in correct order."""
        cfg = TransformsConfig(
            namespace=NamespaceConfig(prefix="api"),
            tool_transform=ToolTransformConfig(
                tools={"api_my_tool": ToolTransformEntry(name="short")}
            ),
            visibility=VisibilityConfig(
                rules=[VisibilityRuleConfig(enabled=True, tags={"setup"})]
            ),
            version_filter=VersionFilterConfig(version_gte="1.0"),
        )
        chain = _build_chain(cfg)
        assert len(chain) == 4
        assert isinstance(chain[0], Namespace)
        assert isinstance(chain[1], ToolTransform)
        assert isinstance(chain[2], Visibility)
        assert isinstance(chain[3], VersionFilter)


# ── configure_transforms ──────────────────────────────────


class TestConfigureTransforms:
    def test_default_passthrough(self):
        """No transforms with default config."""
        server = FastMCP("test")
        chain = configure_transforms(server)
        assert chain == []

    def test_none_config_is_passthrough(self):
        server = FastMCP("test")
        chain = configure_transforms(server, None)
        assert chain == []

    def test_namespace_applied(self):
        server = FastMCP("test")

        @server.tool(tags={"setup"})
        def greet(name: str) -> str:
            """Say hello."""
            return f"Hello, {name}"

        chain = configure_transforms(
            server,
            TransformsConfig.namespaced("api"),
        )
        assert len(chain) == 1
        assert isinstance(chain[0], Namespace)

    def test_returns_chain(self):
        server = FastMCP("test")
        cfg = TransformsConfig(
            namespace=NamespaceConfig(prefix="v1"),
            visibility=VisibilityConfig(
                rules=[VisibilityRuleConfig(enabled=True, match_all=True)]
            ),
        )
        chain = configure_transforms(server, cfg)
        assert len(chain) == 2

    def test_profile_setup_only(self):
        server = FastMCP("test")
        cfg = TransformsConfig.setup_only()
        chain = configure_transforms(server, cfg)
        # 2 Visibility transforms (hide all + show setup)
        assert len(chain) == 2
        assert all(isinstance(t, Visibility) for t in chain)

    def test_profile_execution_only(self):
        server = FastMCP("test")
        cfg = TransformsConfig.execution_only()
        chain = configure_transforms(server, cfg)
        assert len(chain) == 2
        assert all(isinstance(t, Visibility) for t in chain)
