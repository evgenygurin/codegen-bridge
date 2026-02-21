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

_ORG = "__org_id__"  # abbreviation for the long operationId prefix

# operationId → human-readable MCP tool name
TOOL_NAMES: dict[str, str] = {
    # Agent run management (ban excluded — manual tool)
    f"unban_all_checks_for_agent_run_v1_organizations{_ORG}_agent_run_unban_post": (
        "codegen_unban_run"
    ),
    f"remove_codegen_from_pr_v1_organizations{_ORG}_agent_run_remove_from_pr_post": (
        "codegen_remove_from_pr"
    ),
    # PR management
    f"edit_pull_request_simple_v1_organizations{_ORG}_prs__pr_id__patch": (
        "codegen_edit_pr"
    ),
    f"edit_pull_request_v1_organizations{_ORG}_repos__repo_id__prs__pr_id__patch": (
        "codegen_edit_repo_pr"
    ),
    # Models & config
    f"get_available_models_v1_organizations{_ORG}_models_get": (
        "codegen_get_models"
    ),
    f"get_organization_integrations_endpoint_v1_organizations{_ORG}_integrations_get": (
        "codegen_get_integrations"
    ),
    f"get_check_suite_settings_v1_organizations{_ORG}_repos_check_suite_settings_get": (
        "codegen_get_check_suite"
    ),
    f"update_check_suite_settings_v1_organizations{_ORG}_repos_check_suite_settings_put": (
        "codegen_set_check_suite"
    ),
    # Webhooks
    f"get_webhook_config_v1_organizations{_ORG}_webhooks_agent_run_get": (
        "codegen_get_webhook"
    ),
    f"set_webhook_config_v1_organizations{_ORG}_webhooks_agent_run_post": (
        "codegen_set_webhook"
    ),
    f"delete_webhook_config_v1_organizations{_ORG}_webhooks_agent_run_delete": (
        "codegen_delete_webhook"
    ),
    f"test_webhook_v1_organizations{_ORG}_webhooks_agent_run_test_post": (
        "codegen_test_webhook"
    ),
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
    """Build route maps that include only endpoints NOT covered by manual tools."""
    return [
        # Agent management extras (ban excluded — manual codegen_stop_run)
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
        # PR management
        RouteMap(
            pattern=r".*/prs/.*",
            methods=["PATCH"],
            mcp_type=MCPType.TOOL,
        ),
        # Models & config
        RouteMap(pattern=r".*/models$", methods=["GET"], mcp_type=MCPType.TOOL),
        RouteMap(
            pattern=r".*/integrations$",
            methods=["GET"],
            mcp_type=MCPType.TOOL,
        ),
        RouteMap(pattern=r".*/check-suite-settings$", mcp_type=MCPType.TOOL),
        # Webhooks
        RouteMap(pattern=r".*/webhooks/.*", mcp_type=MCPType.TOOL),
        # Exclude everything else (manual tools, oauth, slack, sandbox)
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
