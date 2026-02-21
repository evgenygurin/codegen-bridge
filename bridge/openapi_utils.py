"""Utilities for OpenAPI spec patching and provider setup."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import httpx
from fastmcp.server.providers.openapi import (
    MCPType,
    OpenAPIProvider,
    RouteMap,
)
from fastmcp.utilities.openapi import HTTPRoute

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
    "edit_pull_request_simple_v1_organizations__org_id__prs__pr_id__patch": (
        "codegen_edit_pr"
    ),
    "edit_pull_request_v1_organizations__org_id__repos__repo_id__prs__pr_id__patch": (
        "codegen_edit_repo_pr"
    ),
    # ── Models & config ────────────────────────────────────────────────
    "get_available_models_v1_organizations__org_id__models_get": (
        "codegen_get_models"
    ),
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
    "get_webhook_config_v1_organizations__org_id__webhooks_agent_run_get": (
        "codegen_get_webhook"
    ),
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


def load_and_patch_spec(org_id: int) -> dict:
    """Load OpenAPI spec from disk and replace {org_id} with the real value.

    This removes org_id from tool parameters so the LLM doesn't need to pass it.
    """
    spec = json.loads(SPEC_PATH.read_text())
    spec = copy.deepcopy(spec)

    patched_paths: dict = {}
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
    return spec


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


def _customize_component(
    route: HTTPRoute,
    component: Any,
) -> None:
    """Add tags and prefix descriptions for auto-generated tools."""
    if hasattr(component, "tags") and isinstance(component.tags, set):
        component.tags.add("codegen-auto")
        if "webhook" in route.path:
            component.tags.add("management")
        elif "agent" in route.path or "prs" in route.path:
            component.tags.add("execution")
        elif "oauth" in route.path or "slack" in route.path:
            component.tags.add("integration")
        elif "sandbox" in route.path or "setup-commands" in route.path:
            component.tags.add("setup")
        elif "users" in route.path or "mcp-providers" in route.path:
            component.tags.add("setup")
        else:
            component.tags.add("setup")


def create_openapi_provider(
    http_client: httpx.AsyncClient,
    org_id: int,
) -> OpenAPIProvider:
    """Create an OpenAPI provider for auto-generated tools."""
    spec = load_and_patch_spec(org_id)
    return OpenAPIProvider(
        openapi_spec=spec,
        client=http_client,
        route_maps=build_route_maps(),
        mcp_names=TOOL_NAMES,
        mcp_component_fn=_customize_component,
    )
