"""Utilities for OpenAPI spec patching, provider setup, and governance.

This module handles:
- Loading and patching the OpenAPI spec (replacing {org_id} with real values)
- Building route maps to select which endpoints become MCP tools
- Customizing auto-generated tool metadata (tags, descriptions, icons)
- Creating the configured OpenAPIProvider instance
- **Governance**: validating spec integrity and endpoint parity

The OpenAPIProvider is one of several providers registered with the server;
see ``bridge.providers`` for the full provider registry.

Governance Model
~~~~~~~~~~~~~~~~
Every ``operationId`` in the spec must be accounted for in exactly one of:

- ``TOOL_NAMES`` — mapped to an auto-generated tool via ``OpenAPIProvider``
- ``EXCLUDED_OPERATIONS`` — intentionally excluded (handled by manual tools)

The ``validate_spec_integrity`` and ``validate_endpoint_parity`` functions
ensure this invariant holds and are run in CI as well as in tests.
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
LIVE_SPEC_URL = "https://api.codegen.com/api/openapi.json"

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

# operationIds intentionally excluded from auto-generation.
# These endpoints are served by manual tools in bridge.tools.*.
#
# Every operationId in the spec MUST appear in either TOOL_NAMES or
# EXCLUDED_OPERATIONS.  The governance tests enforce this invariant.
EXCLUDED_OPERATIONS: frozenset[str] = frozenset(
    {
        # ── Agent lifecycle (bridge.tools.agent) ──────────────────────
        "create_agent_run_v1_organizations__org_id__agent_run_post",
        "get_agent_run_v1_organizations__org_id__agent_run__agent_run_id__get",
        "list_agent_runs_v1_organizations__org_id__agent_runs_get",
        "resume_agent_run_v1_organizations__org_id__agent_run_resume_post",
        "ban_all_checks_for_agent_run_v1_organizations__org_id__agent_run_ban_post",
        "get_agent_run_logs_v1_alpha_organizations__org_id__agent_run__agent_run_id__logs_get",
        # ── Organization / repo discovery (bridge.tools.setup) ───────
        "get_organizations_v1_organizations_get",
        "get_repositories_v1_organizations__org_id__repos_get",
        # ── Agent rules (bridge.tools.execution) ─────────────────────
        "get_cli_rules_v1_organizations__org_id__cli_rules_get",
    }
)


# ── Governance Helpers ────────────────────────────────────────────────


def load_raw_spec() -> dict[str, Any]:
    """Load the raw OpenAPI spec from disk without patching.

    Used by governance tooling where the spec must be inspected
    in its canonical (unpatched) form.

    Raises:
        FileNotFoundError: If the spec file is missing.
        json.JSONDecodeError: If the spec file is invalid JSON.
    """
    result: dict[str, Any] = json.loads(SPEC_PATH.read_text())
    return result


def extract_operation_ids(spec: dict[str, Any]) -> set[str]:
    """Extract all operationIds from an OpenAPI spec.

    Args:
        spec: Parsed OpenAPI spec dict (raw or patched).

    Returns:
        Set of all operationId strings found in the spec.
    """
    op_ids: set[str] = set()
    for path_item in spec.get("paths", {}).values():
        for method_data in path_item.values():
            if isinstance(method_data, dict) and "operationId" in method_data:
                op_ids.add(method_data["operationId"])
    return op_ids


def validate_spec_integrity(spec: dict[str, Any] | None = None) -> list[str]:
    """Validate structural integrity of the OpenAPI spec.

    Checks:
    - Top-level required keys (``openapi``, ``info``, ``paths``)
    - Version string starts with ``3.``
    - ``info`` contains ``title`` and ``version``
    - At least one path is defined
    - Every path/method pair has an ``operationId``

    Args:
        spec: Parsed spec dict.  If ``None``, loads from ``SPEC_PATH``.

    Returns:
        List of error messages.  Empty list means the spec is valid.
    """
    if spec is None:
        spec = load_raw_spec()

    errors: list[str] = []

    # Top-level structure
    for key in ("openapi", "info", "paths"):
        if key not in spec:
            errors.append(f"Missing required top-level key: {key}")

    # OpenAPI version
    version = spec.get("openapi", "")
    if isinstance(version, str) and not version.startswith("3."):
        errors.append(f"Unexpected OpenAPI version: {version} (expected 3.x)")

    # Info block
    info = spec.get("info", {})
    if isinstance(info, dict):
        for field in ("title", "version"):
            if field not in info:
                errors.append(f"Missing info.{field}")

    # Paths
    paths = spec.get("paths", {})
    if not paths:
        errors.append("Spec has no paths defined")

    # operationId presence
    for path, path_item in paths.items():
        for method, method_data in path_item.items():
            if not isinstance(method_data, dict):
                continue
            if "operationId" not in method_data:
                errors.append(f"Missing operationId: {method.upper()} {path}")

    return errors


def validate_endpoint_parity(spec: dict[str, Any] | None = None) -> dict[str, set[str]]:
    """Validate that every operationId is accounted for.

    Every operationId in the spec must appear in either ``TOOL_NAMES``
    (auto-generated tool) or ``EXCLUDED_OPERATIONS`` (manual tool).

    Args:
        spec: Parsed spec dict.  If ``None``, loads from ``SPEC_PATH``.

    Returns:
        Dict with keys:
        - ``unmapped``: operationIds not in TOOL_NAMES or EXCLUDED_OPERATIONS
        - ``stale_tool_names``: TOOL_NAMES keys not found in spec
        - ``stale_excluded``: EXCLUDED_OPERATIONS entries not found in spec

        All sets empty means full parity.
    """
    if spec is None:
        spec = load_raw_spec()

    spec_ops = extract_operation_ids(spec)
    mapped_ops = set(TOOL_NAMES.keys())
    excluded_ops = set(EXCLUDED_OPERATIONS)
    accounted = mapped_ops | excluded_ops

    return {
        "unmapped": spec_ops - accounted,
        "stale_tool_names": mapped_ops - spec_ops,
        "stale_excluded": excluded_ops - spec_ops,
    }


def diff_specs(
    local: dict[str, Any],
    remote: dict[str, Any],
) -> dict[str, Any]:
    """Compute structural diff between two OpenAPI specs.

    Compares at the endpoint level (path + method + operationId) and the
    schema level (component names).

    Args:
        local: The local (committed) spec.
        remote: The remote (live API) spec.

    Returns:
        Dict with keys:
        - ``added_endpoints``: list of (method, path) in remote but not local
        - ``removed_endpoints``: list of (method, path) in local but not remote
        - ``added_schemas``: schema names in remote but not local
        - ``removed_schemas``: schema names in local but not remote
        - ``version_local``: info.version from local spec
        - ``version_remote``: info.version from remote spec
    """

    def _endpoints(spec: dict[str, Any]) -> set[tuple[str, str]]:
        eps: set[tuple[str, str]] = set()
        for path, item in spec.get("paths", {}).items():
            for method, data in item.items():
                if isinstance(data, dict):
                    eps.add((method.upper(), path))
        return eps

    def _schemas(spec: dict[str, Any]) -> set[str]:
        return set(spec.get("components", {}).get("schemas", {}).keys())

    local_eps = _endpoints(local)
    remote_eps = _endpoints(remote)
    local_schemas = _schemas(local)
    remote_schemas = _schemas(remote)

    return {
        "added_endpoints": sorted(remote_eps - local_eps),
        "removed_endpoints": sorted(local_eps - remote_eps),
        "added_schemas": sorted(remote_schemas - local_schemas),
        "removed_schemas": sorted(local_schemas - remote_schemas),
        "version_local": local.get("info", {}).get("version", "unknown"),
        "version_remote": remote.get("info", {}).get("version", "unknown"),
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
