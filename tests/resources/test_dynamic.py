"""Tests for dynamic resources (runs, logs, models)."""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from httpx import Response

_SAMPLE_MODELS = {
    "providers": [
        {
            "name": "Anthropic",
            "models": [
                {"label": "Claude Sonnet 4", "value": "claude-sonnet-4-20250514"},
            ],
        },
    ],
    "default_model": "claude-sonnet-4-20250514",
}


class TestModelsResource:
    async def test_resource_registered(self, client: Client):
        """The codegen://models resource should be discoverable."""
        resources = await client.list_resources()
        uris = {str(r.uri) for r in resources}
        assert "codegen://models" in uris

    @respx.mock
    async def test_read_models(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/models").mock(
            return_value=Response(200, json=_SAMPLE_MODELS)
        )

        result = await client.read_resource("codegen://models")
        data = json.loads(result[0].text)
        assert data["default_model"] == "claude-sonnet-4-20250514"
        assert len(data["providers"]) == 1
        assert data["providers"][0]["name"] == "Anthropic"


class TestRunsResourceTemplate:
    async def test_run_template_registered(self, client: Client):
        """The codegen://runs/{run_id} template should be discoverable."""
        templates = await client.list_resource_templates()
        uris = {str(t.uriTemplate) for t in templates}
        assert "codegen://runs/{run_id}" in uris

    async def test_logs_template_registered(self, client: Client):
        """The codegen://runs/{run_id}/logs template should be discoverable."""
        templates = await client.list_resource_templates()
        uris = {str(t.uriTemplate) for t in templates}
        assert "codegen://runs/{run_id}/logs" in uris
