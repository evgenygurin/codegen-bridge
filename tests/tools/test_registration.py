"""Tests for MCP tool registration."""

from __future__ import annotations

from fastmcp import Client


class TestToolRegistration:
    async def test_core_tools_registered(self, client: Client):
        tools = await client.list_tools()
        names = {t.name for t in tools}
        core = {
            "codegen_create_run",
            "codegen_get_run",
            "codegen_list_runs",
            "codegen_resume_run",
            "codegen_stop_run",
            "codegen_get_logs",
            "codegen_list_orgs",
            "codegen_list_repos",
            "codegen_start_execution",
            "codegen_get_execution_context",
            "codegen_get_agent_rules",
        }
        assert core.issubset(names), f"Missing core tools: {core - names}"

    async def test_create_run_has_description(self, client: Client):
        tools = await client.list_tools()
        create_tool = next(t for t in tools if t.name == "codegen_create_run")
        assert "agent run" in create_tool.description.lower()
