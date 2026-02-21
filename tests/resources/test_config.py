"""Tests for MCP resources (config, execution state)."""

from __future__ import annotations

import json

from fastmcp import Client


class TestConfigResource:
    async def test_config_resource_registered(self, client: Client):
        resources = await client.list_resources()
        uris = {str(r.uri) for r in resources}
        assert "codegen://config" in uris

    async def test_config_returns_org_id(self, client: Client):
        result = await client.read_resource("codegen://config")
        data = json.loads(result[0].text)
        assert data["org_id"] == "42"
        assert data["has_api_key"] is True


class TestExecutionResource:
    async def test_execution_resource_registered(self, client: Client):
        resources = await client.list_resources()
        uris = {str(r.uri) for r in resources}
        assert "codegen://execution/current" in uris

    async def test_returns_valid_json(self, client: Client):
        result = await client.read_resource("codegen://execution/current")
        data = json.loads(result[0].text)
        # Returns either an active execution or no_active_execution status
        assert "status" in data
