"""Web preview configuration guidance tool.

The Codegen API does not expose public endpoints for managing web
preview settings.  This module provides a structured guidance tool
that returns the exact configuration requirements, common commands,
and UI URLs so the MCP client can direct the user appropriately.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.annotations import READ_ONLY
from bridge.dependencies import CurrentContext
from bridge.icons import ICON_WEB_PREVIEW

# ── Constants ────────────────────────────────────────────────────

CODEGEN_APP_BASE = "https://codegen.com"
DOCS_URL = "https://docs.codegen.com/sandboxes/web-preview"
REQUIRED_PORT = 3000
PREVIEW_ENV_VAR = "CG_PREVIEW_URL"

COMMON_COMMANDS: list[dict[str, str]] = [
    {"framework": "Node.js / npm", "command": "npm run dev"},
    {"framework": "Node.js / yarn", "command": "yarn dev"},
    {"framework": "Python / Django", "command": "python manage.py runserver 127.0.0.1:3000"},
    {"framework": "Python / Flask", "command": "flask run --host=127.0.0.1 --port=3000"},
    {"framework": "Ruby / Rails", "command": "bundle exec rails server -b 127.0.0.1 -p 3000"},
    {"framework": "Go / Air", "command": "air -p 3000"},
    {"framework": "Rust / Cargo", "command": "cargo watch -x run"},
    {"framework": "Next.js", "command": "npx next dev -p 3000"},
]


def register_web_preview_tools(mcp: FastMCP) -> None:
    """Register web preview guidance tools."""

    @mcp.tool(tags={"setup"}, icons=ICON_WEB_PREVIEW, timeout=10, annotations=READ_ONLY)
    async def codegen_get_web_preview_guide(
        org_name: str,
        repo_name: str,
        framework: str | None = None,
        ctx: Context = CurrentContext(),
    ) -> str:
        """Get guidance for configuring web preview for a repository.

        Web preview lets you start a development server in the Codegen
        sandbox and view the running application in the Codegen UI.
        The server **must** listen on port 3000.

        The Codegen API does not currently expose endpoints for managing
        web preview configuration.  This tool returns structured setup
        guidance, the required port, common framework commands, and the
        UI URL where configuration is performed.

        Args:
            org_name: Organization name (e.g. ``"my-org"``).
            repo_name: Repository name (e.g. ``"my-repo"``).
            framework: Optional framework hint to filter commands
                (e.g. ``"django"``, ``"next.js"``).
        """
        settings_url = f"{CODEGEN_APP_BASE}/{org_name}/{repo_name}/settings/web-preview"

        # Filter commands by framework if provided
        if framework:
            lower = framework.lower()
            filtered = [c for c in COMMON_COMMANDS if lower in c["framework"].lower()]
            commands = filtered if filtered else COMMON_COMMANDS
        else:
            commands = COMMON_COMMANDS

        await ctx.info(f"Providing web preview guidance for {org_name}/{repo_name}")
        return json.dumps(
            {
                "status": "guidance",
                "api_supported": False,
                "message": (
                    "Web preview settings cannot be managed via the API. "
                    "Configure them through the Codegen web UI."
                ),
                "ui_url": settings_url,
                "documentation_url": DOCS_URL,
                "instructions": [
                    f"Navigate to {settings_url} to configure web preview.",
                    (
                        "Enter the command to start your development server "
                        f"(it MUST listen on port {REQUIRED_PORT})."
                    ),
                    (
                        f"The {PREVIEW_ENV_VAR} environment variable is "
                        "automatically set with the accessible preview URL."
                    ),
                    (
                        "Web preview runs inside the sandbox — it has access to "
                        "the same files, secrets, and environment as agent tasks."
                    ),
                ],
                "requirements": {
                    "port": REQUIRED_PORT,
                    "host": "127.0.0.1",
                    "env_var": PREVIEW_ENV_VAR,
                    "note": (
                        f"The web server MUST listen on port {REQUIRED_PORT}. "
                        "Codegen is specifically configured to expose this port."
                    ),
                },
                "common_commands": commands,
            }
        )
