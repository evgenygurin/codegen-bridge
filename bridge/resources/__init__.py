"""MCP resource definitions for the Codegen Bridge server."""

from bridge.resources.config import register_resources as _register_config
from bridge.resources.platform import register_platform_resources as _register_platform


def register_resources(mcp):
    """Register all MCP resources (config, execution, platform docs)."""
    _register_config(mcp)
    _register_platform(mcp)


__all__ = ["register_resources"]
