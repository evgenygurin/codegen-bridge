"""Tests for MCP prompt templates."""

from __future__ import annotations

from fastmcp import Client


class TestDelegateTaskPrompt:
    async def test_registered(self, client: Client):
        prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert "delegate_task" in names

    async def test_includes_task_and_constraints(self, client: Client):
        result = await client.get_prompt(
            "delegate_task",
            {"task_description": "Fix login bug"},
        )
        text = result.messages[0].content.text
        assert "Fix login bug" in text
        assert "Constraints" in text


class TestMonitorRunsPrompt:
    async def test_registered(self, client: Client):
        prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert "monitor_runs" in names


class TestBuildTaskPromptTemplate:
    async def test_registered(self, client: Client):
        prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert "build_task_prompt_template" in names


class TestExecutionSummaryPrompt:
    async def test_registered(self, client: Client):
        prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert "execution_summary" in names
