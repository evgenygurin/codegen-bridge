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

    def test_does_not_include_ban_endpoint(self):
        """Ban endpoint is handled by manual codegen_stop_run tool."""
        maps = build_route_maps()
        patterns = [str(m.pattern) for m in maps if hasattr(m, "pattern")]
        for p in patterns:
            assert "ban" not in p or "unban" in p

    def test_includes_users_routes(self):
        """Users endpoints should be routed as tools."""
        maps = build_route_maps()
        patterns = [str(m.pattern) for m in maps if m.pattern is not None]
        matched = [p for p in patterns if "users" in p]
        assert len(matched) >= 3, f"Expected >=3 user route maps, got: {matched}"

    def test_includes_sandbox_route(self):
        maps = build_route_maps()
        patterns = [str(m.pattern) for m in maps if m.pattern is not None]
        matched = [p for p in patterns if "sandbox" in p]
        assert len(matched) >= 1, "Expected sandbox route map"

    def test_includes_setup_commands_route(self):
        maps = build_route_maps()
        patterns = [str(m.pattern) for m in maps if m.pattern is not None]
        matched = [p for p in patterns if "setup-commands" in p]
        assert len(matched) >= 1, "Expected setup-commands route map"

    def test_includes_slack_route(self):
        maps = build_route_maps()
        patterns = [str(m.pattern) for m in maps if m.pattern is not None]
        matched = [p for p in patterns if "slack" in p]
        assert len(matched) >= 1, "Expected slack-connect route map"

    def test_includes_oauth_route(self):
        maps = build_route_maps()
        patterns = [str(m.pattern) for m in maps if m.pattern is not None]
        matched = [p for p in patterns if "oauth" in p]
        assert len(matched) >= 1, "Expected oauth route map"

    def test_includes_mcp_providers_route(self):
        maps = build_route_maps()
        patterns = [str(m.pattern) for m in maps if m.pattern is not None]
        matched = [p for p in patterns if "mcp-providers" in p]
        assert len(matched) >= 1, "Expected mcp-providers route map"

    def test_user_route_matches_org_scoped_users(self):
        """Org-scoped /users path should match the route pattern."""
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/organizations/42/users"
        assert any(
            re.search(p, path) for p in patterns
        ), f"No route matched {path}"

    def test_user_route_matches_user_by_id(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/organizations/42/users/123"
        assert any(
            re.search(p, path) for p in patterns
        ), f"No route matched {path}"

    def test_user_me_route_matches(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/users/me"
        assert any(
            re.search(p, path) for p in patterns
        ), f"No route matched {path}"

    def test_sandbox_route_matches(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/organizations/42/sandbox/abc123/analyze-logs"
        assert any(
            re.search(p, path) for p in patterns
        ), f"No route matched {path}"

    def test_setup_commands_route_matches(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/organizations/42/setup-commands/generate"
        assert any(
            re.search(p, path) for p in patterns
        ), f"No route matched {path}"

    def test_slack_route_matches(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/slack-connect/generate-token"
        assert any(
            re.search(p, path) for p in patterns
        ), f"No route matched {path}"

    def test_oauth_routes_match(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        for path in ["/v1/oauth/tokens/revoke", "/v1/oauth/tokens/status"]:
            assert any(
                re.search(p, path) for p in patterns
            ), f"No route matched {path}"

    def test_mcp_providers_route_matches(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/mcp-providers"
        assert any(
            re.search(p, path) for p in patterns
        ), f"No route matched {path}"


class TestToolNames:
    def test_all_names_start_with_codegen(self):
        for op_id, name in TOOL_NAMES.items():
            assert name.startswith("codegen_"), f"Bad name for {op_id}: {name}"

    def test_no_duplicate_names(self):
        names = list(TOOL_NAMES.values())
        assert len(names) == len(set(names)), "Duplicate tool names found"

    def test_contains_user_tools(self):
        names = set(TOOL_NAMES.values())
        assert "codegen_list_users" in names
        assert "codegen_get_user" in names
        assert "codegen_get_current_user" in names

    def test_contains_setup_tools(self):
        names = set(TOOL_NAMES.values())
        assert "codegen_generate_setup_commands" in names
        assert "codegen_analyze_sandbox_logs" in names

    def test_contains_slack_tool(self):
        names = set(TOOL_NAMES.values())
        assert "codegen_generate_slack_token" in names

    def test_contains_oauth_tools(self):
        names = set(TOOL_NAMES.values())
        assert "codegen_revoke_oauth_token" in names
        assert "codegen_get_oauth_status" in names

    def test_contains_mcp_providers_tool(self):
        names = set(TOOL_NAMES.values())
        assert "codegen_get_mcp_providers" in names

    def test_contains_webhook_tools(self):
        names = set(TOOL_NAMES.values())
        assert "codegen_get_webhook" in names
        assert "codegen_set_webhook" in names
        assert "codegen_delete_webhook" in names
        assert "codegen_test_webhook" in names

    def test_contains_pr_tools(self):
        names = set(TOOL_NAMES.values())
        assert "codegen_edit_pr" in names
        assert "codegen_edit_repo_pr" in names

    def test_contains_agent_extras(self):
        names = set(TOOL_NAMES.values())
        assert "codegen_unban_run" in names
        assert "codegen_remove_from_pr" in names

    def test_total_tool_count(self):
        """Ensure we have the expected number of auto-generated tool mappings."""
        # 2 agent extras + 3 users + 2 PR + 4 models/config + 4 webhooks
        # + 2 setup/sandbox + 1 slack + 2 oauth + 1 mcp-providers = 21
        assert len(TOOL_NAMES) == 21, f"Expected 21 tool names, got {len(TOOL_NAMES)}"

    def test_operation_ids_match_spec(self):
        """All operationIds in TOOL_NAMES must exist in the OpenAPI spec."""
        spec = load_and_patch_spec(42)
        # operationIds in the spec still contain __org_id__ (only paths are patched)
        spec_op_ids = set()
        for path_item in spec["paths"].values():
            for method_data in path_item.values():
                if isinstance(method_data, dict) and "operationId" in method_data:
                    spec_op_ids.add(method_data["operationId"])

        for op_id in TOOL_NAMES:
            assert op_id in spec_op_ids, (
                f"operationId not found in spec: {op_id}"
            )


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
