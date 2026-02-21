"""Tests for OpenAPI spec utilities."""

from __future__ import annotations

import json

from bridge.openapi_utils import (
    TOOL_NAMES,
    build_route_maps,
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


class TestToolNames:
    def test_all_names_start_with_codegen(self):
        for op_id, name in TOOL_NAMES.items():
            assert name.startswith("codegen_"), f"Bad name for {op_id}: {name}"

    def test_no_duplicate_names(self):
        names = list(TOOL_NAMES.values())
        assert len(names) == len(set(names)), "Duplicate tool names found"
