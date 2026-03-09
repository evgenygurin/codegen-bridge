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
#
# ONLY tools that have NO manual equivalent belong here.
# All other endpoints are covered by manual tools in bridge.tools.*
# which provide elicitation, safety annotations, and richer error handling.
#
# Manual tools cover: agent runs (create/get/list/resume/stop/ban/unban/
# remove_from_pr/logs), execution, PRs (edit_pr, edit_repo_pr), setup
# (users, orgs, repos, projects, check_suite, setup_commands), integrations
# (webhooks, sandbox, slack), and settings.
TOOL_NAMES: dict[str, str] = {
    # ── Users (global — no org-scoped manual equivalent) ───────────────
    "get_current_user_info_v1_users_me_get": "codegen_get_current_user",
    # ── Models (read-only, no manual equivalent) ───────────────────────
    "get_available_models_v1_organizations__org_id__models_get": "codegen_get_models",
    # ── OAuth (no manual equivalents) ──────────────────────────────────
    "revoke_oauth_token_v1_oauth_tokens_revoke_post": "codegen_revoke_oauth_token",
    "get_oauth_token_status_v1_oauth_tokens_status_get": "codegen_get_oauth_status",
    # ── MCP providers (no manual equivalent) ───────────────────────────
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
                patched_params: list[Any] = []
                for param in method_data["parameters"]:
                    if not isinstance(param, dict):
                        patched_params.append(param)
                        continue

                    if param.get("name") != "org_id":
                        patched_params.append(param)
                        continue

                    # Most endpoints use {org_id} in the path, so org_id
                    # should not be exposed as a tool argument.
                    #
                    # OAuth revoke is different: org_id is a required query
                    # parameter even though the path is global. Keep it in the
                    # spec with a default so callers don't need to pass it.
                    if new_path == "/v1/oauth/tokens/revoke":
                        org_param = copy.deepcopy(param)
                        org_param["required"] = False
                        schema = org_param.get("schema")
                        if isinstance(schema, dict):
                            schema["default"] = org_id
                        patched_params.append(org_param)
                        continue

                    # Drop org_id from all other operations.

                method_data["parameters"] = patched_params

        patched_paths[new_path] = path_item

    spec["paths"] = patched_paths
    result: dict[str, Any] = spec
    return result


def build_route_maps() -> list[RouteMap]:
    """Build route maps for endpoints that have NO manual tool equivalent.

    Only 5 endpoints are exposed via OpenAPI auto-generation.
    Everything else is handled by manual tools in bridge.tools.*
    which provide elicitation, safety annotations, and richer UX.
    """
    return [
        # ── Users (global /users/me — no manual equivalent) ───────────
        RouteMap(
            pattern=r".*/users/me$",
            methods=["GET"],
            mcp_type=MCPType.TOOL,
        ),
        # ── Models (read-only, no manual equivalent) ──────────────────
        RouteMap(pattern=r".*/models$", methods=["GET"], mcp_type=MCPType.TOOL),
        # ── OAuth (no manual equivalents) ─────────────────────────────
        RouteMap(pattern=r".*/oauth/tokens/.*", mcp_type=MCPType.TOOL),
        # ── MCP providers (no manual equivalent) ──────────────────────
        RouteMap(
            pattern=r".*/mcp-providers$",
            methods=["GET"],
            mcp_type=MCPType.TOOL,
        ),
        # ── Exclude everything else (covered by manual tools) ─────────
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
