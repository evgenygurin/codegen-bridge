"""Repository rules tools.

Provides tools for reading current agent rules (API-backed) and
guidance for configuring repository-specific rules (UI-only — no
public API endpoint exists for writes).
"""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.server.context import Context

from bridge.annotations import READ_ONLY
from bridge.client import CodegenClient
from bridge.dependencies import CurrentContext, Depends, get_client
from bridge.icons import ICON_REPO_RULES

# ── Constants ────────────────────────────────────────────────────

CODEGEN_APP_BASE = "https://codegen.com"
DOCS_URL = "https://docs.codegen.com/settings/repo-rules"

SUPPORTED_RULE_FILE_PATTERNS: list[str] = [
    "AGENTS.md",
    "CLAUDE.md",
    ".cursorrules",
    ".clinerules",
    ".windsurfrules",
    ".cursor/rules/**/*.mdc",
    "**/*.mdc",
]

MAX_RULES_BUDGET_CHARS = 25_000


def register_repository_rules_tools(mcp: FastMCP) -> None:
    """Register repository-rules tools (get, configure guide)."""

    @mcp.tool(tags={"setup"}, icons=ICON_REPO_RULES, timeout=30, annotations=READ_ONLY)
    async def codegen_get_repository_rules(
        ctx: Context = CurrentContext(),
        client: CodegenClient = Depends(get_client),  # type: ignore[arg-type]
    ) -> str:
        """Get current agent rules for the organization.

        Returns the organization-level rules and user-level custom prompt
        that are injected into agent context at task start. These rules
        come from the Codegen platform settings plus any automatically
        detected rule files in the repository (AGENTS.md, CLAUDE.md, etc.).
        """
        await ctx.info("Fetching repository / organization rules")
        raw = await client.get_rules()
        org_rules = raw.get("organization_rules") or None
        user_prompt = raw.get("user_custom_prompt") or None
        await ctx.info(
            f"Rules retrieved: org_rules={'present' if org_rules else 'empty'}, "
            f"user_prompt={'present' if user_prompt else 'empty'}"
        )
        return json.dumps(
            {
                "organization_rules": org_rules,
                "user_custom_prompt": user_prompt,
                "auto_detected_patterns": SUPPORTED_RULE_FILE_PATTERNS,
                "max_budget_chars": MAX_RULES_BUDGET_CHARS,
                "documentation_url": DOCS_URL,
            }
        )

    @mcp.tool(tags={"setup"}, icons=ICON_REPO_RULES, timeout=10, annotations=READ_ONLY)
    async def codegen_configure_repository_rules(
        org_name: str,
        repo_name: str,
        ctx: Context = CurrentContext(),
    ) -> str:
        """Get guidance for configuring repository rules.

        The Codegen API does not currently support creating or updating
        repository rules programmatically. This tool returns the exact
        steps required to configure rules through the Codegen web UI,
        along with supported rule file patterns and constraints.

        Args:
            org_name: Organization name (e.g. ``"my-org"``).
            repo_name: Repository name (e.g. ``"my-repo"``).
        """
        settings_url = f"{CODEGEN_APP_BASE}/{org_name}/{repo_name}/settings"
        repos_url = f"{CODEGEN_APP_BASE}/repos"

        await ctx.info(f"Providing repository rules guidance for {org_name}/{repo_name}")
        return json.dumps(
            {
                "status": "guidance",
                "api_supported": False,
                "message": (
                    "Repository rules cannot be managed via the API. "
                    "Use the Codegen web UI or commit rule files to your repository."
                ),
                "ui_url": settings_url,
                "repos_url": repos_url,
                "documentation_url": DOCS_URL,
                "instructions": [
                    f"Navigate to {settings_url} to configure rules in the web UI.",
                    "Alternatively, commit rule files directly to your repository.",
                    (
                        "Codegen auto-detects rule files matching these patterns: "
                        + ", ".join(SUPPORTED_RULE_FILE_PATTERNS)
                    ),
                    (
                        f"All rule files combined are truncated to "
                        f"{MAX_RULES_BUDGET_CHARS:,} characters."
                    ),
                    f"You can customize glob patterns at {repos_url} "
                    "(select your repo → configure rule file patterns).",
                ],
                "supported_rule_files": SUPPORTED_RULE_FILE_PATTERNS,
                "constraints": {
                    "max_budget_chars": MAX_RULES_BUDGET_CHARS,
                    "rule_priority": "User > Repository > Organization",
                    "note": (
                        "Rules are text prompts used as guidance — "
                        "not strict constraints. Agents consider all rules "
                        "alongside the specific task."
                    ),
                },
            }
        )
