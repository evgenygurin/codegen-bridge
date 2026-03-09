"""MCP prompt definitions for the Codegen Bridge server."""

from fastmcp import FastMCP

from bridge.prompts.dynamic import register_dynamic_prompts as _register_dynamic
from bridge.prompts.templates import register_prompts as _register_templates


def register_prompts(mcp: FastMCP) -> None:
    """Register all MCP prompts (templates + dynamic)."""
    _register_templates(mcp)
    _register_dynamic(mcp)


__all__ = ["register_prompts"]
