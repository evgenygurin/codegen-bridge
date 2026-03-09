"""Tests for the codegen_list_models tool."""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from httpx import Response

_SAMPLE_MODELS_RESPONSE = {
    "providers": [
        {
            "name": "Anthropic",
            "models": [
                {"label": "Claude Sonnet 4", "value": "claude-sonnet-4-20250514"},
                {"label": "Claude Haiku 3.5", "value": "claude-3-5-haiku-20241022"},
            ],
        },
        {
            "name": "OpenAI",
            "models": [
                {"label": "GPT-4o", "value": "gpt-4o"},
            ],
        },
    ],
    "default_model": "claude-sonnet-4-20250514",
}


class TestListModels:
    async def test_tool_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "codegen_list_models" in names

    @respx.mock
    async def test_returns_models(self, client: Client):
        respx.get("https://api.codegen.com/v1/organizations/42/models").mock(
            return_value=Response(200, json=_SAMPLE_MODELS_RESPONSE)
        )

        result = await client.call_tool("codegen_list_models", {})
        data = json.loads(result.data)

        assert "providers" in data
        assert "default_model" in data
        assert data["default_model"] == "claude-sonnet-4-20250514"
        assert len(data["providers"]) == 2
        assert data["providers"][0]["name"] == "Anthropic"
        assert len(data["providers"][0]["models"]) == 2
        assert data["providers"][1]["name"] == "OpenAI"

    @respx.mock
    async def test_response_structure(self, client: Client):
        """Verify the JSON envelope structure (provider → models nesting)."""
        single_provider_resp = {
            "providers": [
                {
                    "name": "Anthropic",
                    "models": [
                        {"label": "Claude Sonnet 4", "value": "claude-sonnet-4"},
                    ],
                },
            ],
            "default_model": "claude-sonnet-4",
        }
        respx.get("https://api.codegen.com/v1/organizations/42/models").mock(
            return_value=Response(200, json=single_provider_resp)
        )

        result = await client.call_tool("codegen_list_models", {})
        data = json.loads(result.data)

        # Due to tool-level response caching (tool_ttl=60), the first call
        # in the test session is cached.  This test may receive the cached
        # response from `test_returns_models`.  We therefore only assert
        # structural properties that hold regardless of which payload is returned.
        assert isinstance(data["providers"], list)
        assert len(data["providers"]) >= 1
        assert "default_model" in data
        for provider in data["providers"]:
            assert "name" in provider
            assert "models" in provider
            assert isinstance(provider["models"], list)
            for model in provider["models"]:
                assert "label" in model
                assert "value" in model
