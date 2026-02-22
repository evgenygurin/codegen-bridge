"""Platform documentation resources — integrations guide and CLI/SDK docs.

Exposes two read-only MCP resources:

* ``codegen://platform/integrations-guide`` — comprehensive reference for all
  supported third-party integrations (GitHub, Linear, Slack, Jira, Figma,
  Notion, Sentry) including setup instructions and capabilities.
* ``codegen://platform/cli-sdk`` — Codegen CLI key commands, SDK usage
  patterns, and quick-start instructions.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP

from bridge.icons import ICON_CLI, ICON_GUIDE

# ── Static content ────────────────────────────────────────

_INTEGRATIONS_GUIDE: dict[str, object] = {
    "title": "Codegen Platform Integrations Guide",
    "description": (
        "Comprehensive reference for all supported third-party integrations. "
        "Each integration extends the Codegen AI agent's ability to interact "
        "with your development workflow."
    ),
    "integrations": [
        {
            "name": "GitHub",
            "type": "github_app",
            "description": (
                "Core integration for repository access, pull request management, "
                "code review, and CI/CD status monitoring."
            ),
            "capabilities": [
                "Repository read/write access",
                "Pull request creation and editing",
                "Branch management",
                "Code review comments",
                "CI check-suite monitoring and retry",
                "Webhook event processing",
            ],
            "setup": (
                "Install the Codegen GitHub App on your organization. "
                "Grant repository access to the repos you want Codegen to manage."
            ),
            "auth_method": "GitHub App installation",
        },
        {
            "name": "Linear",
            "type": "oauth",
            "description": (
                "Project management integration for issue tracking, sprint planning, "
                "and bi-directional sync between code changes and Linear issues."
            ),
            "capabilities": [
                "Issue creation and updates",
                "Sprint/cycle management",
                "Label and priority synchronization",
                "Bi-directional status sync with PRs",
                "Team and project discovery",
            ],
            "setup": (
                "Connect via OAuth from the Codegen dashboard under "
                "Settings → Integrations → Linear."
            ),
            "auth_method": "OAuth 2.0",
        },
        {
            "name": "Slack",
            "type": "oauth",
            "description": (
                "Team communication integration for real-time notifications, "
                "agent status updates, and interactive command workflows."
            ),
            "capabilities": [
                "Agent run notifications",
                "PR status updates in channels",
                "Interactive slash commands",
                "Thread-based conversations with agents",
                "Slack Connect for external collaboration",
            ],
            "setup": (
                "Connect via OAuth from the Codegen dashboard under "
                "Settings → Integrations → Slack. Use the "
                "codegen_slack_connect_token tool for Slack Connect setup."
            ),
            "auth_method": "OAuth 2.0",
        },
        {
            "name": "Jira",
            "type": "oauth",
            "description": (
                "Issue tracker integration for Atlassian workflows, enabling "
                "ticket synchronization and automated status transitions."
            ),
            "capabilities": [
                "Issue creation and updates",
                "Status transition automation",
                "Sprint board integration",
                "Custom field mapping",
                "Bi-directional sync with PRs",
            ],
            "setup": (
                "Connect via OAuth from the Codegen dashboard under "
                "Settings → Integrations → Jira. Requires Jira Cloud."
            ),
            "auth_method": "OAuth 2.0 (Atlassian)",
        },
        {
            "name": "Figma",
            "type": "oauth",
            "description": (
                "Design tool integration for extracting design tokens, component "
                "specs, and visual references to guide code generation."
            ),
            "capabilities": [
                "Design file access",
                "Component property extraction",
                "Design token export",
                "Visual reference for UI implementation",
                "Comment synchronization",
            ],
            "setup": (
                "Connect via OAuth from the Codegen dashboard under "
                "Settings → Integrations → Figma."
            ),
            "auth_method": "OAuth 2.0",
        },
        {
            "name": "Notion",
            "type": "oauth",
            "description": (
                "Knowledge base integration for accessing documentation, specs, "
                "and project context stored in Notion workspaces."
            ),
            "capabilities": [
                "Page and database read access",
                "Documentation context for agents",
                "Specification extraction",
                "Meeting notes and decision references",
                "Project wiki integration",
            ],
            "setup": (
                "Connect via OAuth from the Codegen dashboard under "
                "Settings → Integrations → Notion. Select which pages/databases "
                "to share."
            ),
            "auth_method": "OAuth 2.0",
        },
        {
            "name": "Sentry",
            "type": "api_key",
            "description": (
                "Error monitoring integration for accessing crash reports, "
                "stack traces, and performance data to guide bug fixes."
            ),
            "capabilities": [
                "Error and exception retrieval",
                "Stack trace analysis",
                "Performance issue detection",
                "Release tracking",
                "Automated bug-fix context",
            ],
            "setup": (
                "Connect via API key from the Codegen dashboard under "
                "Settings → Integrations → Sentry. Create an internal "
                "integration token in your Sentry organization."
            ),
            "auth_method": "API key (internal integration)",
        },
    ],
    "notes": (
        "Use the codegen_get_integrations tool to check which integrations "
        "are currently active for your organization. Integration availability "
        "depends on your Codegen plan."
    ),
}

_CLI_SDK_DOCS: dict[str, object] = {
    "title": "Codegen CLI & SDK Reference",
    "description": (
        "Quick reference for the Codegen command-line interface and Python SDK. "
        "The CLI is the primary way to interact with Codegen from your terminal, "
        "while the SDK enables programmatic access."
    ),
    "cli": {
        "installation": "pip install codegen",
        "commands": [
            {
                "command": "codegen",
                "description": "Launch the Codegen AI agent in your terminal.",
                "usage": "codegen [OPTIONS] [PROMPT]",
                "examples": [
                    'codegen "Fix the failing tests in src/auth"',
                    'codegen --repo my-org/my-repo "Add input validation"',
                ],
            },
            {
                "command": "cg status",
                "description": (
                    "Check the status of agent runs for the current organization."
                ),
                "usage": "cg status [RUN_ID]",
                "examples": [
                    "cg status",
                    "cg status 12345",
                ],
            },
            {
                "command": "cg logs",
                "description": "Stream or view logs from an agent run.",
                "usage": "cg logs <RUN_ID> [--follow] [--tail N]",
                "examples": [
                    "cg logs 12345",
                    "cg logs 12345 --follow",
                    "cg logs 12345 --tail 50",
                ],
            },
            {
                "command": "cg config",
                "description": (
                    "View or update Codegen CLI configuration (API key, org ID, "
                    "default model)."
                ),
                "usage": "cg config [set KEY VALUE]",
                "examples": [
                    "cg config",
                    "cg config set org_id 42",
                    "cg config set model gpt-4o",
                ],
            },
        ],
    },
    "sdk": {
        "installation": "pip install codegen",
        "quick_start": (
            "from codegen import Codegen\n\n"
            "cg = Codegen(api_key='your-key', org_id=42)\n\n"
            "# Create an agent run\n"
            "run = cg.create_run(\n"
            '    prompt="Fix the auth bug in login.py",\n'
            '    repo_name="my-org/my-repo",\n'
            ")\n\n"
            "# Check status\n"
            "status = cg.get_run(run.id)\n"
            "print(status.status)  # 'running', 'completed', 'blocked'\n\n"
            "# List recent runs\n"
            "runs = cg.list_runs(limit=10)\n"
            "for r in runs:\n"
            '    print(f"{r.id}: {r.status}")\n'
        ),
        "key_classes": [
            {
                "name": "Codegen",
                "description": (
                    "Main SDK client. Wraps the Codegen REST API with typed "
                    "methods for agent runs, pull requests, and integrations."
                ),
            },
            {
                "name": "AgentRun",
                "description": (
                    "Represents a single agent execution. Contains status, "
                    "result, summary, associated PRs, and metadata."
                ),
            },
            {
                "name": "PullRequest",
                "description": (
                    "GitHub PR created or managed by an agent run. Includes "
                    "URL, number, title, state, and branch info."
                ),
            },
        ],
    },
    "environment_variables": [
        {
            "name": "CODEGEN_API_KEY",
            "description": "Your Codegen API key (required).",
            "required": True,
        },
        {
            "name": "CODEGEN_ORG_ID",
            "description": "Your organization ID (required).",
            "required": True,
        },
        {
            "name": "CODEGEN_BASE_URL",
            "description": (
                "Override the API base URL. Defaults to https://api.codegen.com."
            ),
            "required": False,
        },
    ],
    "links": {
        "documentation": "https://docs.codegen.com",
        "api_reference": "https://api.codegen.com/api/openapi.json",
        "dashboard": "https://codegen.com/dashboard",
    },
}


def register_platform_resources(mcp: FastMCP) -> None:
    """Register platform documentation resources on the given FastMCP server."""

    @mcp.resource("codegen://platform/integrations-guide", icons=ICON_GUIDE)
    def get_integrations_guide() -> str:
        """Supported integrations reference — GitHub, Linear, Slack, Jira, Figma, Notion, Sentry.

        Returns setup instructions, capabilities, and authentication methods
        for every integration the Codegen platform supports.
        """
        return json.dumps(_INTEGRATIONS_GUIDE, indent=2)

    @mcp.resource("codegen://platform/cli-sdk", icons=ICON_CLI)
    def get_cli_sdk_docs() -> str:
        """Codegen CLI commands and Python SDK quick-start reference.

        Returns key CLI commands (codegen, cg status, cg logs, cg config),
        SDK usage patterns, environment variables, and useful links.
        """
        return json.dumps(_CLI_SDK_DOCS, indent=2)
