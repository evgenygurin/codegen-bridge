"""MCP transform pipeline for the Codegen Bridge server.

Provides a configurable transform chain built on FastMCP 3.x built-in
transform classes.  Transforms modify components (tools, resources, prompts)
as they flow from providers to clients.

Available transforms (applied in this order):
1. Namespace  — prefix component names to prevent conflicts
2. ToolTransform — rename, re-describe, or hide individual tools
3. Visibility — show/hide components by name, tag, or type
4. VersionFilter — filter components by semantic version range

Usage::

    from bridge.transforms import configure_transforms, TransformsConfig

    mcp = FastMCP("Codegen Bridge", ...)
    configure_transforms(mcp)  # passthrough (no transforms)

    # or with a profile:
    configure_transforms(mcp, TransformsConfig.setup_only())

    # or custom:
    configure_transforms(mcp, TransformsConfig(
        namespace=NamespaceConfig(prefix="codegen"),
        visibility=VisibilityConfig(rules=[...]),
    ))
"""

from __future__ import annotations

from bridge.transforms.config import (
    NamespaceConfig,
    ToolTransformConfig,
    ToolTransformEntry,
    TransformsConfig,
    VersionFilterConfig,
    VisibilityConfig,
    VisibilityRuleConfig,
)
from bridge.transforms.registry import configure_transforms

__all__ = [
    "NamespaceConfig",
    "ToolTransformConfig",
    "ToolTransformEntry",
    "TransformsConfig",
    "VersionFilterConfig",
    "VisibilityConfig",
    "VisibilityRuleConfig",
    "configure_transforms",
]
