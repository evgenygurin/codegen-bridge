"""Organization, repository, user setup, and OAuth tools.

Decomposed into focused submodules by responsibility:
- users: User management (get current user, list, get by ID)
- organizations: Organization and repository management
- oauth: OAuth and MCP provider management
- check_suite: CI check-suite settings
"""

from __future__ import annotations

from fastmcp import FastMCP

from bridge.tools.setup.check_suite import register_check_suite_tools
from bridge.tools.setup.models import register_models_tools
from bridge.tools.setup.oauth import register_oauth_tools
from bridge.tools.setup.organizations import register_organization_tools
from bridge.tools.setup.users import register_user_tools

__all__ = ["register_setup_tools"]


def register_setup_tools(mcp: FastMCP) -> None:
    """Register all setup tools on the given FastMCP server."""
    register_user_tools(mcp)
    register_organization_tools(mcp)
    register_oauth_tools(mcp)
    register_check_suite_tools(mcp)
    register_models_tools(mcp)
