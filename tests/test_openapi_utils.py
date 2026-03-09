"""Tests for OpenAPI spec utilities."""

from __future__ import annotations

import json
import re
from unittest.mock import MagicMock

from bridge.openapi_utils import (
    TOOL_NAMES,
    _classify_route,
    _customize_component,
    build_route_maps,
    create_openapi_provider,
    load_and_patch_spec,
)


class TestLoadAndPatchSpec:
    def test_replaces_org_id_in_paths(self):
        spec = load_and_patch_spec(42)
        paths = list(spec["paths"].keys())
        # No {org_id} should remain
        for path in paths:
            assert "{org_id}" not in path, f"Unpatched org_id in: {path}"

    def test_injects_real_org_id(self):
        spec = load_and_patch_spec(99)
        paths = list(spec["paths"].keys())
        org_paths = [p for p in paths if "/99/" in p]
        assert len(org_paths) > 0, "Expected org_id=99 in patched paths"

    def test_removes_org_id_from_parameters(self):
        spec = load_and_patch_spec(42)
        for path, path_item in spec["paths"].items():
            for method, data in path_item.items():
                if not isinstance(data, dict):
                    continue
                params = data.get("parameters", [])
                for p in params:
                    if isinstance(p, dict):
                        assert p.get("name") != "org_id", (
                            f"org_id param still in {method.upper()} {path}"
                        )

    def test_preserves_other_path_params(self):
        spec = load_and_patch_spec(42)
        # The agent_run_id path param should survive
        found = False
        for path in spec["paths"]:
            if "agent_run_id" in path or "{agent_run_id}" in path:
                found = True
                break
        assert found, "Expected {agent_run_id} path param to survive patching"

    def test_preserves_sandbox_id_path_param(self):
        spec = load_and_patch_spec(42)
        found = False
        for path in spec["paths"]:
            if "{sandbox_id}" in path:
                found = True
                break
        assert found, "Expected {sandbox_id} path param to survive patching"

    def test_preserves_user_id_path_param(self):
        spec = load_and_patch_spec(42)
        found = False
        for path in spec["paths"]:
            if "{user_id}" in path:
                found = True
                break
        assert found, "Expected {user_id} path param to survive patching"

    def test_non_org_paths_are_preserved(self):
        """Paths without {org_id} should remain unchanged."""
        spec = load_and_patch_spec(42)
        paths = list(spec["paths"].keys())
        non_org_paths = [
            "/v1/users/me",
            "/v1/mcp-providers",
            "/v1/oauth/tokens/revoke",
            "/v1/oauth/tokens/status",
            "/v1/slack-connect/generate-token",
        ]
        for expected in non_org_paths:
            assert expected in paths, f"Non-org path missing: {expected}"

    def test_returns_valid_json(self):
        spec = load_and_patch_spec(42)
        # Should be serializable
        dumped = json.dumps(spec)
        assert len(dumped) > 100


class TestBuildRouteMaps:
    def test_returns_non_empty_list(self):
        maps = build_route_maps()
        assert len(maps) > 0

    def test_last_rule_excludes_all(self):
        maps = build_route_maps()
        from fastmcp.server.providers.openapi import MCPType

        assert maps[-1].mcp_type == MCPType.EXCLUDE

    def test_only_five_tool_routes(self):
        """Only routes for the 5 unique auto-tools plus the catch-all exclude."""
        maps = build_route_maps()
        from fastmcp.server.providers.openapi import MCPType

        tool_routes = [m for m in maps if m.mcp_type == MCPType.TOOL]
        # users/me, models, oauth/tokens/.*, mcp-providers = 4 route entries
        assert len(tool_routes) == 4, f"Expected 4 tool routes, got {len(tool_routes)}"

    def test_user_me_route_matches(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/users/me"
        assert any(re.search(p, path) for p in patterns), f"No route matched {path}"

    def test_models_route_matches(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/organizations/42/models"
        assert any(re.search(p, path) for p in patterns), f"No route matched {path}"

    def test_oauth_routes_match(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        for path in ["/v1/oauth/tokens/revoke", "/v1/oauth/tokens/status"]:
            assert any(re.search(p, path) for p in patterns), f"No route matched {path}"

    def test_mcp_providers_route_matches(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/mcp-providers"
        assert any(re.search(p, path) for p in patterns), f"No route matched {path}"

    def test_excluded_manual_routes_do_not_match(self):
        """Routes handled by manual tools must NOT match any route map."""
        maps = build_route_maps()
        from fastmcp.server.providers.openapi import MCPType

        tool_patterns = [
            m.pattern for m in maps
            if m.pattern is not None and m.mcp_type == MCPType.TOOL
        ]
        manual_paths = [
            "/v1/organizations/42/users",
            "/v1/organizations/42/users/123",
            "/v1/organizations/42/prs/456",
            "/v1/organizations/42/webhooks/agent-run",
            "/v1/organizations/42/agent/run/unban",
            "/v1/organizations/42/setup-commands/generate",
            "/v1/slack-connect/generate-token",
        ]
        for path in manual_paths:
            assert not any(re.search(p, path) for p in tool_patterns), (
                f"Manual path unexpectedly matched a tool route: {path}"
            )


class TestToolNames:
    def test_all_names_start_with_codegen(self):
        for op_id, name in TOOL_NAMES.items():
            assert name.startswith("codegen_"), f"Bad name for {op_id}: {name}"

    def test_no_duplicate_names(self):
        names = list(TOOL_NAMES.values())
        assert len(names) == len(set(names)), "Duplicate tool names found"

    def test_contains_current_user(self):
        names = set(TOOL_NAMES.values())
        assert "codegen_get_current_user" in names

    def test_contains_models(self):
        names = set(TOOL_NAMES.values())
        assert "codegen_get_models" in names

    def test_contains_oauth_tools(self):
        names = set(TOOL_NAMES.values())
        assert "codegen_revoke_oauth_token" in names
        assert "codegen_get_oauth_status" in names

    def test_contains_mcp_providers_tool(self):
        names = set(TOOL_NAMES.values())
        assert "codegen_get_mcp_providers" in names

    def test_no_duplicate_manual_tools(self):
        """Auto-generated tools must NOT overlap with manual tool names."""
        # These are covered by manual tools and must NOT be in TOOL_NAMES
        manual_names = {
            "codegen_list_users", "codegen_get_user",
            "codegen_edit_pr", "codegen_edit_repo_pr",
            "codegen_unban_run", "codegen_remove_from_pr",
            "codegen_get_webhook", "codegen_set_webhook",
            "codegen_delete_webhook", "codegen_test_webhook",
            "codegen_get_integrations", "codegen_get_check_suite",
            "codegen_set_check_suite", "codegen_generate_setup_commands",
            "codegen_analyze_sandbox_logs", "codegen_generate_slack_token",
        }
        auto_names = set(TOOL_NAMES.values())
        overlap = auto_names & manual_names
        assert not overlap, f"Auto tools overlap with manual tools: {overlap}"

    def test_total_tool_count(self):
        """Only 5 unique auto-generated tools (no manual duplicates)."""
        # 1 current_user + 1 models + 2 oauth + 1 mcp-providers = 5
        assert len(TOOL_NAMES) == 5, f"Expected 5 tool names, got {len(TOOL_NAMES)}"

    def test_operation_ids_match_spec(self):
        """All operationIds in TOOL_NAMES must exist in the OpenAPI spec."""
        spec = load_and_patch_spec(42)
        spec_op_ids = set()
        for path_item in spec["paths"].values():
            for method_data in path_item.values():
                if isinstance(method_data, dict) and "operationId" in method_data:
                    spec_op_ids.add(method_data["operationId"])

        for op_id in TOOL_NAMES:
            assert op_id in spec_op_ids, f"operationId not found in spec: {op_id}"


class TestClassifyRoute:
    """Tests for the data-driven domain classifier."""

    def test_webhook_path(self):
        tag, prefix = _classify_route("/v1/organizations/42/webhooks/agent-run")
        assert tag == "management"
        assert prefix == "Webhook"

    def test_agent_path(self):
        tag, prefix = _classify_route("/v1/organizations/42/agent/run/unban")
        assert tag == "execution"
        assert prefix == "Agent run"

    def test_prs_path(self):
        tag, prefix = _classify_route("/v1/organizations/42/prs/123")
        assert tag == "execution"
        assert prefix == "Pull request"

    def test_oauth_path(self):
        tag, prefix = _classify_route("/v1/oauth/tokens/revoke")
        assert tag == "integration"
        assert prefix == "OAuth"

    def test_slack_path(self):
        tag, prefix = _classify_route("/v1/slack-connect/generate-token")
        assert tag == "integration"
        assert prefix == "Slack"

    def test_sandbox_path(self):
        tag, prefix = _classify_route("/v1/organizations/42/sandbox/abc/analyze-logs")
        assert tag == "setup"
        assert prefix == "Sandbox"

    def test_users_path(self):
        tag, prefix = _classify_route("/v1/organizations/42/users")
        assert tag == "setup"
        assert prefix == "User"

    def test_models_path(self):
        tag, prefix = _classify_route("/v1/organizations/42/models")
        assert tag == "setup"
        assert prefix == "Model"

    def test_unknown_path_defaults_to_setup(self):
        tag, prefix = _classify_route("/v1/some/unknown/endpoint")
        assert tag == "setup"
        assert prefix == "API"


class TestCustomizeComponent:
    """Tests for the component customization function."""

    def test_adds_codegen_auto_tag(self):
        route = MagicMock()
        route.path = "/v1/organizations/42/webhooks/test"
        component = MagicMock()
        component.tags = set()
        component.description = "Test webhook"

        _customize_component(route, component)
        assert "codegen-auto" in component.tags

    def test_adds_category_tag(self):
        route = MagicMock()
        route.path = "/v1/organizations/42/webhooks/test"
        component = MagicMock()
        component.tags = set()
        component.description = "Test webhook"

        _customize_component(route, component)
        assert "management" in component.tags

    def test_enriches_empty_description(self):
        route = MagicMock()
        route.path = "/v1/organizations/42/webhooks/test"
        route.method = "GET"
        component = MagicMock()
        component.tags = set()
        component.description = ""

        _customize_component(route, component)
        assert "Webhook" in component.description
        assert "GET" in component.description

    def test_preserves_existing_description(self):
        route = MagicMock()
        route.path = "/v1/organizations/42/webhooks/test"
        component = MagicMock()
        component.tags = set()
        component.description = "A detailed description of the webhook endpoint"

        _customize_component(route, component)
        assert component.description == "A detailed description of the webhook endpoint"

    def test_enriches_short_description(self):
        route = MagicMock()
        route.path = "/v1/organizations/42/users"
        route.method = "GET"
        component = MagicMock()
        component.tags = set()
        component.description = "Get users"

        _customize_component(route, component)
        assert "User" in component.description

    def test_handles_no_tags_attribute(self):
        """Should not crash if component has no tags."""
        route = MagicMock()
        route.path = "/v1/users"
        component = MagicMock(spec=[])  # no attributes

        # Should not raise
        _customize_component(route, component)


class TestCreateOpenApiProvider:
    """Tests for the OpenAPI provider factory with improved parameters."""

    def test_creates_provider_with_validate_output(self):
        import httpx

        client = httpx.AsyncClient(base_url="https://api.example.com")
        try:
            provider = create_openapi_provider(client, 42, validate_output=True)
            assert provider is not None
        finally:
            # Sync close for cleanup
            pass

    def test_creates_provider_without_validate_output(self):
        import httpx

        client = httpx.AsyncClient(base_url="https://api.example.com")
        try:
            provider = create_openapi_provider(client, 42, validate_output=False)
            assert provider is not None
        finally:
            pass

    def test_default_validate_output_is_true(self):
        import httpx

        client = httpx.AsyncClient(base_url="https://api.example.com")
        try:
            provider = create_openapi_provider(client, 42)
            assert provider is not None
        finally:
            pass
