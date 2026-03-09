"""MCP resource definitions for the Codegen Bridge server."""

from fastmcp import FastMCP

from bridge.resources.config import register_resources as _register_config
from bridge.resources.platform import register_platform_resources as _register_platform
from bridge.resources.templates import register_resource_templates as _register_templates


def register_resources(mcp: FastMCP) -> None:
    """Register all MCP resources (config, execution, platform docs, templates)."""
    _register_config(mcp)
    _register_platform(mcp)
    _register_templates(mcp)


__all__ = ["register_resources"]
