"""Tests for bridge.sampling.tools — MCP tool registration.

These tests verify that sampling tools are registered correctly
and validate the tool metadata / tags. Actual sampling is tested
in test_service.py; here we focus on the wiring layer.
"""

from __future__ import annotations

import os

from fastmcp import Client

# Ensure test env before importing server
os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "42"

from bridge.sampling.config import SamplingConfig
from bridge.sampling.tools import _get_sampling_config


class TestGetSamplingConfig:
    """_get_sampling_config resolves from lifespan context or falls back."""

    def test_returns_config_from_lifespan(self):
        cfg = SamplingConfig(summary_max_tokens=999)
        ctx = type("FakeCtx", (), {"lifespan_context": {"sampling_config": cfg}})()
        result = _get_sampling_config(ctx)
        assert result is cfg
        assert result.summary_max_tokens == 999

    def test_returns_default_when_missing(self):
        ctx = type("FakeCtx", (), {"lifespan_context": {}})()
        result = _get_sampling_config(ctx)
        assert isinstance(result, SamplingConfig)
        assert result.summary_max_tokens == 512  # default

    def test_returns_default_when_no_lifespan(self):
        class FakeCtx:
            lifespan_context = None

        result = _get_sampling_config(FakeCtx())
        assert isinstance(result, SamplingConfig)


SAMPLING_TOOL_NAMES = {
    "codegen_summarise_run",
    "codegen_summarise_execution",
    "codegen_generate_task_prompt",
    "codegen_analyse_run_logs",
}


class TestSamplingToolRegistration:
    """Sampling tools are registered with correct metadata."""

    async def test_tools_registered_on_server(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert SAMPLING_TOOL_NAMES.issubset(names), (
            f"Missing sampling tools: {SAMPLING_TOOL_NAMES - names}"
        )

    async def test_sampling_tools_have_descriptions(self, client: Client):
        tools = await client.list_tools()
        sampling_tools = {t.name: t for t in tools if t.name in SAMPLING_TOOL_NAMES}
        for name, tool in sampling_tools.items():
            assert tool.description, f"{name} has no description"
            assert len(tool.description) > 20, f"{name} description too short"

    async def test_summarise_run_has_run_id_param(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_summarise_run")
        schema = tool.inputSchema
        assert "run_id" in schema.get("properties", {}), "Missing run_id parameter"
        assert "run_id" in schema.get("required", []), "run_id should be required"

    async def test_generate_task_prompt_has_goal_param(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_generate_task_prompt")
        schema = tool.inputSchema
        assert "goal" in schema.get("properties", {}), "Missing goal parameter"
        assert "task_description" in schema.get("properties", {}), "Missing task_description"

    async def test_analyse_run_logs_has_run_id_param(self, client: Client):
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "codegen_analyse_run_logs")
        schema = tool.inputSchema
        assert "run_id" in schema.get("properties", {}), "Missing run_id parameter"
