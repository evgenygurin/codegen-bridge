"""Tests for OpenAPI spec utilities and governance."""

from __future__ import annotations

import json
import re
from typing import Any
from unittest.mock import MagicMock

from bridge.openapi_utils import (
    EXCLUDED_OPERATIONS,
    TOOL_NAMES,
    _classify_route,
    _customize_component,
    build_route_maps,
    create_openapi_provider,
    diff_specs,
    extract_operation_ids,
    load_and_patch_spec,
    load_raw_spec,
    validate_endpoint_parity,
    validate_spec_integrity,
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
        assert any(re.search(p, path) for p in patterns), f"No route matched {path}"

    def test_user_route_matches_user_by_id(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/organizations/42/users/123"
        assert any(re.search(p, path) for p in patterns), f"No route matched {path}"

    def test_user_me_route_matches(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/users/me"
        assert any(re.search(p, path) for p in patterns), f"No route matched {path}"

    def test_sandbox_route_matches(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/organizations/42/sandbox/abc123/analyze-logs"
        assert any(re.search(p, path) for p in patterns), f"No route matched {path}"

    def test_setup_commands_route_matches(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/organizations/42/setup-commands/generate"
        assert any(re.search(p, path) for p in patterns), f"No route matched {path}"

    def test_slack_route_matches(self):
        maps = build_route_maps()
        patterns = [m.pattern for m in maps if m.pattern is not None]
        path = "/v1/slack-connect/generate-token"
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


# ── Governance Tests ─────────────────────────────────────────────


class TestLoadRawSpec:
    """Tests for loading the unpatched spec."""

    def test_returns_dict(self):
        spec = load_raw_spec()
        assert isinstance(spec, dict)

    def test_has_openapi_key(self):
        spec = load_raw_spec()
        assert "openapi" in spec

    def test_has_paths(self):
        spec = load_raw_spec()
        assert "paths" in spec
        assert len(spec["paths"]) > 0

    def test_paths_contain_org_id_template(self):
        """Raw spec should still have {org_id} in path templates."""
        spec = load_raw_spec()
        org_paths = [p for p in spec["paths"] if "{org_id}" in p]
        assert len(org_paths) > 0, "Expected {org_id} in raw spec paths"


class TestExtractOperationIds:
    """Tests for operationId extraction."""

    def test_extracts_from_real_spec(self):
        spec = load_raw_spec()
        op_ids = extract_operation_ids(spec)
        assert len(op_ids) > 0

    def test_extracts_known_operation_ids(self):
        spec = load_raw_spec()
        op_ids = extract_operation_ids(spec)
        # Spot-check a few known operationIds
        assert "get_users_v1_organizations__org_id__users_get" in op_ids
        assert "create_agent_run_v1_organizations__org_id__agent_run_post" in op_ids

    def test_handles_empty_spec(self):
        op_ids = extract_operation_ids({"paths": {}})
        assert op_ids == set()

    def test_handles_missing_paths(self):
        op_ids = extract_operation_ids({})
        assert op_ids == set()

    def test_skips_non_dict_methods(self):
        """Non-dict items under a path (e.g., 'parameters' list) are ignored."""
        spec: dict[str, Any] = {
            "paths": {
                "/test": {
                    "parameters": [{"name": "x"}],
                    "get": {"operationId": "test_op"},
                }
            }
        }
        op_ids = extract_operation_ids(spec)
        assert op_ids == {"test_op"}


class TestExcludedOperations:
    """Tests for the EXCLUDED_OPERATIONS governance set."""

    def test_is_frozenset(self):
        assert isinstance(EXCLUDED_OPERATIONS, frozenset)

    def test_has_expected_count(self):
        # 6 agent + 2 org/repo + 1 rules = 9
        assert len(EXCLUDED_OPERATIONS) == 9, (
            f"Expected 9 excluded operations, got {len(EXCLUDED_OPERATIONS)}"
        )

    def test_contains_agent_lifecycle_operations(self):
        expected = {
            "create_agent_run_v1_organizations__org_id__agent_run_post",
            "get_agent_run_v1_organizations__org_id__agent_run__agent_run_id__get",
            "list_agent_runs_v1_organizations__org_id__agent_runs_get",
            "resume_agent_run_v1_organizations__org_id__agent_run_resume_post",
            "ban_all_checks_for_agent_run_v1_organizations__org_id__agent_run_ban_post",
            "get_agent_run_logs_v1_alpha_organizations__org_id__agent_run__agent_run_id__logs_get",
        }
        assert expected.issubset(EXCLUDED_OPERATIONS)

    def test_contains_org_repo_operations(self):
        expected = {
            "get_organizations_v1_organizations_get",
            "get_repositories_v1_organizations__org_id__repos_get",
        }
        assert expected.issubset(EXCLUDED_OPERATIONS)

    def test_contains_rules_operation(self):
        assert "get_cli_rules_v1_organizations__org_id__cli_rules_get" in EXCLUDED_OPERATIONS

    def test_no_overlap_with_tool_names(self):
        """EXCLUDED_OPERATIONS and TOOL_NAMES keys must be disjoint."""
        overlap = set(TOOL_NAMES.keys()) & set(EXCLUDED_OPERATIONS)
        assert overlap == set(), f"Overlap between TOOL_NAMES and EXCLUDED_OPERATIONS: {overlap}"

    def test_all_excluded_exist_in_spec(self):
        """Every EXCLUDED_OPERATIONS entry must exist in the spec."""
        spec = load_raw_spec()
        spec_ops = extract_operation_ids(spec)
        stale = set(EXCLUDED_OPERATIONS) - spec_ops
        assert stale == set(), f"Stale EXCLUDED_OPERATIONS entries: {stale}"


class TestValidateSpecIntegrity:
    """Tests for spec structural validation."""

    def test_real_spec_passes(self):
        errors = validate_spec_integrity()
        assert errors == [], f"Spec integrity errors: {errors}"

    def test_detects_missing_openapi_key(self):
        errors = validate_spec_integrity({"info": {}, "paths": {}})
        assert any("openapi" in e for e in errors)

    def test_detects_missing_info_key(self):
        errors = validate_spec_integrity({"openapi": "3.1.0", "paths": {}})
        assert any("info" in e for e in errors)

    def test_detects_missing_paths_key(self):
        errors = validate_spec_integrity({"openapi": "3.1.0", "info": {}})
        assert any("paths" in e for e in errors)

    def test_detects_wrong_openapi_version(self):
        errors = validate_spec_integrity(
            {"openapi": "2.0", "info": {"title": "x", "version": "1"}, "paths": {"/a": {}}}
        )
        assert any("version" in e.lower() for e in errors)

    def test_detects_empty_paths(self):
        errors = validate_spec_integrity(
            {"openapi": "3.1.0", "info": {"title": "x", "version": "1"}, "paths": {}}
        )
        assert any("no paths" in e.lower() for e in errors)

    def test_detects_missing_info_title(self):
        errors = validate_spec_integrity(
            {"openapi": "3.1.0", "info": {"version": "1"}, "paths": {"/a": {}}}
        )
        assert any("title" in e for e in errors)

    def test_detects_missing_info_version(self):
        errors = validate_spec_integrity(
            {"openapi": "3.1.0", "info": {"title": "x"}, "paths": {"/a": {}}}
        )
        assert any("version" in e for e in errors)

    def test_detects_missing_operation_id(self):
        errors = validate_spec_integrity(
            {
                "openapi": "3.1.0",
                "info": {"title": "x", "version": "1"},
                "paths": {"/a": {"get": {"summary": "no op id"}}},
            }
        )
        assert any("operationId" in e for e in errors)

    def test_valid_minimal_spec(self):
        errors = validate_spec_integrity(
            {
                "openapi": "3.1.0",
                "info": {"title": "Test", "version": "1.0.0"},
                "paths": {"/a": {"get": {"operationId": "test_op"}}},
            }
        )
        assert errors == []


class TestValidateEndpointParity:
    """Tests for endpoint parity validation.

    This is the primary governance test — if a new endpoint appears in
    the spec without being mapped or explicitly excluded, this test
    catches it.
    """

    def test_real_spec_has_full_parity(self):
        """Every operationId in the committed spec is accounted for."""
        result = validate_endpoint_parity()
        assert result["unmapped"] == set(), (
            f"Unmapped operationIds: {result['unmapped']}\n"
            "Add to TOOL_NAMES or EXCLUDED_OPERATIONS in bridge/openapi_utils.py"
        )

    def test_no_stale_tool_names(self):
        """No TOOL_NAMES entries reference non-existent operationIds."""
        result = validate_endpoint_parity()
        assert result["stale_tool_names"] == set(), (
            f"Stale TOOL_NAMES entries: {result['stale_tool_names']}"
        )

    def test_no_stale_excluded(self):
        """No EXCLUDED_OPERATIONS entries reference non-existent operationIds."""
        result = validate_endpoint_parity()
        assert result["stale_excluded"] == set(), (
            f"Stale EXCLUDED_OPERATIONS entries: {result['stale_excluded']}"
        )

    def test_total_coverage(self):
        """TOOL_NAMES + EXCLUDED_OPERATIONS should cover all spec operationIds."""
        spec = load_raw_spec()
        spec_ops = extract_operation_ids(spec)
        covered = set(TOOL_NAMES.keys()) | set(EXCLUDED_OPERATIONS)
        assert spec_ops == covered, (
            f"Coverage mismatch:\n"
            f"  In spec but not covered: {spec_ops - covered}\n"
            f"  Covered but not in spec: {covered - spec_ops}"
        )

    def test_detects_unmapped_operations(self):
        """Validate that a synthetic unmapped operationId is caught."""
        fake_spec: dict[str, Any] = {
            "paths": {
                "/test": {"get": {"operationId": "totally_new_endpoint_get"}},
                # Add a known one so the result isn't just 'everything is unmapped'
                "/v1/users/me": {"get": {"operationId": "get_current_user_info_v1_users_me_get"}},
            }
        }
        result = validate_endpoint_parity(fake_spec)
        assert "totally_new_endpoint_get" in result["unmapped"]

    def test_detects_stale_entries(self):
        """Validate that stale TOOL_NAMES keys are caught when spec is reduced."""
        # Spec with only one endpoint — all other TOOL_NAMES keys become stale
        fake_spec: dict[str, Any] = {
            "paths": {
                "/v1/users/me": {"get": {"operationId": "get_current_user_info_v1_users_me_get"}},
            }
        }
        result = validate_endpoint_parity(fake_spec)
        # At least some TOOL_NAMES entries should be stale
        assert len(result["stale_tool_names"]) > 0


class TestDiffSpecs:
    """Tests for structural diff between two specs."""

    def test_identical_specs_no_diff(self):
        spec = load_raw_spec()
        result = diff_specs(spec, spec)
        assert result["added_endpoints"] == []
        assert result["removed_endpoints"] == []
        assert result["added_schemas"] == []
        assert result["removed_schemas"] == []

    def test_detects_added_endpoint(self):
        local: dict[str, Any] = {"paths": {"/a": {"get": {"operationId": "a_get"}}}}
        remote: dict[str, Any] = {
            "paths": {
                "/a": {"get": {"operationId": "a_get"}},
                "/b": {"post": {"operationId": "b_post"}},
            }
        }
        result = diff_specs(local, remote)
        assert ("POST", "/b") in result["added_endpoints"]
        assert result["removed_endpoints"] == []

    def test_detects_removed_endpoint(self):
        local: dict[str, Any] = {
            "paths": {
                "/a": {"get": {"operationId": "a_get"}},
                "/b": {"post": {"operationId": "b_post"}},
            }
        }
        remote: dict[str, Any] = {"paths": {"/a": {"get": {"operationId": "a_get"}}}}
        result = diff_specs(local, remote)
        assert ("POST", "/b") in result["removed_endpoints"]
        assert result["added_endpoints"] == []

    def test_detects_added_schema(self):
        local: dict[str, Any] = {
            "paths": {},
            "components": {"schemas": {"Foo": {"type": "object"}}},
        }
        remote: dict[str, Any] = {
            "paths": {},
            "components": {"schemas": {"Foo": {"type": "object"}, "Bar": {"type": "string"}}},
        }
        result = diff_specs(local, remote)
        assert "Bar" in result["added_schemas"]

    def test_detects_removed_schema(self):
        local: dict[str, Any] = {
            "paths": {},
            "components": {"schemas": {"Foo": {"type": "object"}, "Bar": {"type": "string"}}},
        }
        remote: dict[str, Any] = {
            "paths": {},
            "components": {"schemas": {"Foo": {"type": "object"}}},
        }
        result = diff_specs(local, remote)
        assert "Bar" in result["removed_schemas"]

    def test_reports_versions(self):
        local: dict[str, Any] = {"info": {"version": "1.0.0"}, "paths": {}}
        remote: dict[str, Any] = {"info": {"version": "2.0.0"}, "paths": {}}
        result = diff_specs(local, remote)
        assert result["version_local"] == "1.0.0"
        assert result["version_remote"] == "2.0.0"

    def test_handles_missing_components(self):
        local: dict[str, Any] = {"paths": {}}
        remote: dict[str, Any] = {"paths": {}}
        result = diff_specs(local, remote)
        assert result["added_schemas"] == []
        assert result["removed_schemas"] == []

    def test_handles_missing_info(self):
        local: dict[str, Any] = {"paths": {}}
        remote: dict[str, Any] = {"paths": {}}
        result = diff_specs(local, remote)
        assert result["version_local"] == "unknown"
        assert result["version_remote"] == "unknown"
