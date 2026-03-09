"""MCP resource definitions for the Codegen Bridge server."""

from fastmcp import FastMCP

from bridge.resources.config import register_resources as _register_config
from bridge.resources.dynamic import register_dynamic_resources as _register_dynamic
from bridge.resources.platform import register_platform_resources as _register_platform


def register_resources(mcp: FastMCP) -> None:
    """Register all MCP resources (config, execution, platform docs, dynamic)."""
    _register_config(mcp)
    _register_platform(mcp)
    _register_dynamic(mcp)


__all__ = ["register_resources"]
