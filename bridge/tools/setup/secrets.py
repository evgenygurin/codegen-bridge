"""Repository secrets guidance tool.

The Codegen API does not expose public endpoints for managing
repository secrets.  This module provides a structured guidance tool
that returns the exact steps, constraints, common use cases, and UI
URLs so the MCP client can direct the user appropriately.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.annotations import READ_ONLY
from bridge.dependencies import CurrentContext
from bridge.icons import ICON_SECRETS

# ── Constants ────────────────────────────────────────────────────

CODEGEN_APP_BASE = "https://codegen.com"
DOCS_URL = "https://docs.codegen.com/sandboxes/secrets"

COMMON_USE_CASES: list[dict[str, str]] = [
    {
        "category": "Build Configuration",
        "description": "Environment-specific build variables and feature flags",
        "example_key": "NODE_ENV",
    },
    {
        "category": "Third-Party Integrations",
        "description": (
            "Non-production tokens for services like Stripe test mode, staging analytics"
        ),
        "example_key": "STRIPE_TEST_KEY",
    },
    {
        "category": "Database Connections",
        "description": "Connection strings for staging/test databases",
        "example_key": "DATABASE_URL",
    },
    {
        "category": "Development Server Credentials",
        "description": "API keys for staging services and development APIs",
        "example_key": "DEV_API_KEY",
    },
]


def register_secrets_tools(mcp: FastMCP) -> None:
    """Register repository secrets guidance tools."""

    @mcp.tool(tags={"setup"}, icons=ICON_SECRETS, timeout=10, annotations=READ_ONLY)
    async def codegen_get_secrets_guide(
        org_name: str,
        repo_name: str,
        ctx: Context = CurrentContext(),
    ) -> str:
        """Get guidance for managing repository secrets.

        Secrets are environment variables securely injected into the
        Codegen sandbox during agent execution.  They are managed
        exclusively through the Codegen web UI — no public API endpoint
        exists for creating or listing secrets.

        This tool returns structured setup guidance, security constraints,
        common use cases, and the UI URL where secrets are managed.

        Args:
            org_name: Organization name (e.g. ``"my-org"``).
            repo_name: Repository name (e.g. ``"my-repo"``).
        """
        settings_url = f"{CODEGEN_APP_BASE}/{org_name}/{repo_name}/settings/secrets"

        await ctx.info(f"Providing secrets guidance for {org_name}/{repo_name}")
        return json.dumps(
            {
                "status": "guidance",
                "api_supported": False,
                "message": (
                    "Repository secrets cannot be managed via the API. "
                    "Add them through the Codegen web UI."
                ),
                "ui_url": settings_url,
                "documentation_url": DOCS_URL,
                "instructions": [
                    f"Navigate to {settings_url} to manage secrets.",
                    "Go to the Secrets tab in your repository settings.",
                    "Add key-value pairs for your environment variables.",
                    (
                        "Secrets are immediately available to agents in "
                        "the sandbox after adding them."
                    ),
                ],
                "security_constraints": {
                    "staging_only": True,
                    "warning": (
                        "Only use staging credentials and non-production secrets. "
                        "Never store production API keys, database passwords, "
                        "or sensitive credentials."
                    ),
                    "storage": "Secrets are encrypted and stored securely per repository.",
                    "access": (
                        "Secrets are injected as environment variables during "
                        "agent code execution in the sandbox."
                    ),
                },
                "common_use_cases": COMMON_USE_CASES,
            }
        )
