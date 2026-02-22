"""Utilities for OpenAPI spec patching and provider setup.

This module handles:
- Loading and patching the OpenAPI spec (replacing {org_id} with real values)
- Building route maps to select which endpoints become MCP tools
- Customizing auto-generated tool metadata (tags, descriptions, icons)
- Creating the configured OpenAPIProvider instance

The OpenAPIProvider is one of several providers registered with the server;
see ``bridge.providers`` for the full provider registry.
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

import httpx
from fastmcp.server.providers.openapi import (
    MCPType,
    OpenAPIProvider,
    RouteMap,
)
from fastmcp.utilities.openapi import HTTPRoute

from bridge.middleware.authorization import DEFAULT_DANGEROUS_TOOLS

logger = logging.getLogger("bridge.openapi")

SPEC_PATH = Path(__file__).parent / "openapi_spec.json"

# operationId -> human-readable MCP tool name
#
# Keys are exact operationIds from the OpenAPI spec.
# Endpoints handled by manual tools (in bridge.tools.*) are NOT listed here:
#   - create_agent_run, get_agent_run, list_agent_runs, resume_agent_run,
#     ban_all_checks (codegen_stop_run), get_agent_run_logs
#   - get_organizations, get_repositories, get_cli_rules
TOOL_NAMES: dict[str, str] = {
    # ── Agent run management (ban excluded — manual codegen_stop_run) ──
    "unban_all_checks_for_agent_run_v1_organizations__org_id__agent_run_unban_post": (
        "codegen_unban_run"
    ),
    "remove_codegen_from_pr_v1_organizations__org_id__agent_run_remove_from_pr_post": (
        "codegen_remove_from_pr"
    ),
    # ── Users ──────────────────────────────────────────────────────────
    "get_users_v1_organizations__org_id__users_get": "codegen_list_users",
    "get_user_v1_organizations__org_id__users__user_id__get": "codegen_get_user",
    "get_current_user_info_v1_users_me_get": "codegen_get_current_user",
    # ── PR management ──────────────────────────────────────────────────
    "edit_pull_request_simple_v1_organizations__org_id__prs__pr_id__patch": ("codegen_edit_pr"),
    "edit_pull_request_v1_organizations__org_id__repos__repo_id__prs__pr_id__patch": (
        "codegen_edit_repo_pr"
    ),
    # ── Models & config ────────────────────────────────────────────────
    "get_available_models_v1_organizations__org_id__models_get": ("codegen_get_models"),
    "get_organization_integrations_endpoint_v1_organizations__org_id__integrations_get": (
        "codegen_get_integrations"
    ),
    "get_check_suite_settings_v1_organizations__org_id__repos_check_suite_settings_get": (
        "codegen_get_check_suite"
    ),
    "update_check_suite_settings_v1_organizations__org_id__repos_check_suite_settings_put": (
        "codegen_set_check_suite"
    ),
    # ── Webhooks ───────────────────────────────────────────────────────
    "get_webhook_config_v1_organizations__org_id__webhooks_agent_run_get": ("codegen_get_webhook"),
    "set_webhook_config_v1_organizations__org_id__webhooks_agent_run_post": (
        "codegen_set_webhook"
    ),
    "delete_webhook_config_v1_organizations__org_id__webhooks_agent_run_delete": (
        "codegen_delete_webhook"
    ),
    "test_webhook_v1_organizations__org_id__webhooks_agent_run_test_post": (
        "codegen_test_webhook"
    ),
    # ── Setup & sandbox ────────────────────────────────────────────────
    "generate_setup_commands_v1_organizations__org_id__setup_commands_generate_post": (
        "codegen_generate_setup_commands"
    ),
    "analyze_sandbox_logs_v1_organizations__org_id__sandbox__sandbox_id__analyze_logs_post": (
        "codegen_analyze_sandbox_logs"
    ),
    # ── Slack ──────────────────────────────────────────────────────────
    "generate_slack_connect_token_endpoint_v1_slack_connect_generate_token_post": (
        "codegen_generate_slack_token"
    ),
    # ── OAuth ──────────────────────────────────────────────────────────
    "revoke_oauth_token_v1_oauth_tokens_revoke_post": "codegen_revoke_oauth_token",
    "get_oauth_token_status_v1_oauth_tokens_status_get": "codegen_get_oauth_status",
    # ── MCP providers ──────────────────────────────────────────────────
    "get_mcp_providers_v1_mcp_providers_get": "codegen_get_mcp_providers",
}


def load_and_patch_spec(org_id: int) -> dict[str, Any]:
    """Load OpenAPI spec from disk and replace {org_id} with the real value.

    This removes org_id from tool parameters so the LLM doesn't need to pass it.
    """
    spec = json.loads(SPEC_PATH.read_text())
    spec = copy.deepcopy(spec)

    patched_paths: dict[str, Any] = {}
    for path, path_item in spec.get("paths", {}).items():
        new_path = path.replace("{org_id}", str(org_id))

        for _method_key, method_data in path_item.items():
            if not isinstance(method_data, dict):
                continue
            if "parameters" in method_data:
                method_data["parameters"] = [
                    p
                    for p in method_data["parameters"]
                    if not (isinstance(p, dict) and p.get("name") == "org_id")
                ]

        patched_paths[new_path] = path_item

    spec["paths"] = patched_paths
    result: dict[str, Any] = spec
    return result


def build_route_maps() -> list[RouteMap]:
    """Build route maps for all endpoints NOT covered by manual tools.

    Manual tools (excluded here) handle:
    - POST /agent/run (create), GET /agent/run/{id} (get), GET /agent/runs (list)
    - POST /agent/run/resume, POST /agent/run/ban (stop)
    - GET /alpha/.../agent/run/{id}/logs
    - GET /organizations (list orgs)
    - GET /repos (list repos)
    - GET /cli/rules (agent rules)
    """
    return [
        # ── Agent management extras (ban excluded — manual codegen_stop_run) ──
        RouteMap(
            pattern=r".*/agent/run/unban$",
            methods=["POST"],
            mcp_type=MCPType.TOOL,
        ),
        RouteMap(
            pattern=r".*/agent/run/remove-from-pr$",
            methods=["POST"],
            mcp_type=MCPType.TOOL,
        ),
        # ── Users (org-scoped) ────────────────────────────────────────
        RouteMap(
            pattern=r".*/organizations/\d+/users/\d+$",
            methods=["GET"],
            mcp_type=MCPType.TOOL,
        ),
        RouteMap(
            pattern=r".*/organizations/\d+/users$",
            methods=["GET"],
            mcp_type=MCPType.TOOL,
        ),
        # ── Users (global) ────────────────────────────────────────────
        RouteMap(
            pattern=r".*/users/me$",
            methods=["GET"],
            mcp_type=MCPType.TOOL,
        ),
        # ── PR management ─────────────────────────────────────────────
        RouteMap(
            pattern=r".*/prs/.*",
            methods=["PATCH"],
            mcp_type=MCPType.TOOL,
        ),
        # ── Models & config ───────────────────────────────────────────
        RouteMap(pattern=r".*/models$", methods=["GET"], mcp_type=MCPType.TOOL),
        RouteMap(
            pattern=r".*/integrations$",
            methods=["GET"],
            mcp_type=MCPType.TOOL,
        ),
        RouteMap(pattern=r".*/check-suite-settings$", mcp_type=MCPType.TOOL),
        # ── Webhooks ──────────────────────────────────────────────────
        RouteMap(pattern=r".*/webhooks/.*", mcp_type=MCPType.TOOL),
        # ── Setup & sandbox ───────────────────────────────────────────
        RouteMap(
            pattern=r".*/setup-commands/generate$",
            methods=["POST"],
            mcp_type=MCPType.TOOL,
        ),
        RouteMap(
            pattern=r".*/sandbox/.*/analyze-logs$",
            methods=["POST"],
            mcp_type=MCPType.TOOL,
        ),
        # ── Slack ─────────────────────────────────────────────────────
        RouteMap(
            pattern=r".*/slack-connect/.*",
            methods=["POST"],
            mcp_type=MCPType.TOOL,
        ),
        # ── OAuth ─────────────────────────────────────────────────────
        RouteMap(pattern=r".*/oauth/tokens/.*", mcp_type=MCPType.TOOL),
        # ── MCP providers ─────────────────────────────────────────────
        RouteMap(
            pattern=r".*/mcp-providers$",
            methods=["GET"],
            mcp_type=MCPType.TOOL,
        ),
        # ── Exclude manual-only endpoints (create, get, list, resume,
        #    ban, logs, organizations, repos, cli/rules) ───────────────
        RouteMap(mcp_type=MCPType.EXCLUDE),
    ]


# Reverse-map MCP tool names to detect dangerous OpenAPI tools.
_DANGEROUS_OPENAPI_NAMES: set[str] = {
    name for name in TOOL_NAMES.values() if name in DEFAULT_DANGEROUS_TOOLS
}

# ── Domain classification for auto-generated tools ───────

# Maps path fragments to (category_tag, description_prefix) pairs.
# The first match wins, so order matters (more specific patterns first).
_DOMAIN_CLASSIFIERS: list[tuple[str, str, str]] = [
    ("webhook", "management", "Webhook"),
    ("agent", "execution", "Agent run"),
    ("prs", "execution", "Pull request"),
    ("oauth", "integration", "OAuth"),
    ("slack", "integration", "Slack"),
    ("sandbox", "setup", "Sandbox"),
    ("setup-commands", "setup", "Setup"),
    ("users", "setup", "User"),
    ("mcp-providers", "setup", "MCP provider"),
    ("models", "setup", "Model"),
    ("integrations", "setup", "Integration"),
    ("check-suite", "setup", "Check suite"),
]


def _classify_route(path: str) -> tuple[str, str]:
    """Classify a route path into (category_tag, description_prefix)."""
    for fragment, tag, prefix in _DOMAIN_CLASSIFIERS:
        if fragment in path:
            return tag, prefix
    return "setup", "API"


def _customize_component(
    route: HTTPRoute,
    component: Any,
) -> None:
    """Add tags, prefix descriptions, and enrich auto-generated tools.

    Improvements over v1:
    - Uses data-driven domain classification instead of nested if/elif
    - Enriches tool descriptions with HTTP method and domain context
    - Adds 'codegen-auto' tag for filtering auto-generated tools
    """
    category, prefix = _classify_route(route.path)

    if hasattr(component, "tags") and isinstance(component.tags, set):
        component.tags.add("codegen-auto")
        component.tags.add(category)

    # Enrich description with domain context if it's bare/empty
    if hasattr(component, "description"):
        desc = component.description or ""
        method = route.method.upper() if hasattr(route, "method") else ""
        if not desc or len(desc) < 10:
            component.description = f"{prefix} management via Codegen API ({method} {route.path})."

        # Tag dangerous OpenAPI tools so the authorization middleware
        # can identify them by both name and tag.
        comp_name = getattr(component, "name", "")
        if comp_name in _DANGEROUS_OPENAPI_NAMES:
            component.tags.add("dangerous")


def create_openapi_provider(
    http_client: httpx.AsyncClient,
    org_id: int,
    *,
    validate_output: bool = True,
) -> OpenAPIProvider:
    """Create an OpenAPI provider for auto-generated tools.

    Args:
        http_client: Pre-configured httpx client with auth headers.
        org_id: Organization ID (already baked into spec paths).
        validate_output: If True, validate API responses against the
            OpenAPI response schema. Helps catch API drift early.

    Returns:
        Configured ``OpenAPIProvider`` ready to be added to the server.

    Raises:
        FileNotFoundError: If the OpenAPI spec file is missing.
        json.JSONDecodeError: If the spec file is invalid JSON.
    """
    spec = load_and_patch_spec(org_id)
    route_maps = build_route_maps()

    logger.info(
        "Creating OpenAPI provider: org_id=%s, routes=%d, tool_names=%d, validate=%s",
        org_id,
        len(route_maps),
        len(TOOL_NAMES),
        validate_output,
    )

    return OpenAPIProvider(
        openapi_spec=spec,
        client=http_client,
        route_maps=route_maps,
        mcp_names=TOOL_NAMES,
        mcp_component_fn=_customize_component,
        validate_output=validate_output,
    )
