"""Tests for dynamic workflow prompts."""

from __future__ import annotations

from fastmcp import Client


class TestReviewRunPrompt:
    async def test_prompt_registered(self, client: Client):
        prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert "review_run" in names

    async def test_basic_review(self, client: Client):
        result = await client.get_prompt("review_run", {"run_id": "42"})
        text = result.messages[0].content.text
        assert "42" in text
        assert "Load Run Details" in text
        assert "Verdict" in text

    async def test_with_focus_areas(self, client: Client):
        result = await client.get_prompt(
            "review_run",
            {"run_id": "42", "focus_areas": "tests,performance"},
        )
        text = result.messages[0].content.text
        assert "tests" in text
        assert "performance" in text


class TestDebugRunPrompt:
    async def test_prompt_registered(self, client: Client):
        prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert "debug_run" in names

    async def test_basic_debug(self, client: Client):
        result = await client.get_prompt("debug_run", {"run_id": "99"})
        text = result.messages[0].content.text
        assert "99" in text
        assert "Load Logs" in text
        assert "Root Cause" in text

    async def test_with_error_context(self, client: Client):
        result = await client.get_prompt(
            "debug_run",
            {"run_id": "99", "error_context": "TimeoutError: API call timed out"},
        )
        text = result.messages[0].content.text
        assert "TimeoutError" in text


class TestMultiRepoTaskPrompt:
    async def test_prompt_registered(self, client: Client):
        prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert "multi_repo_task" in names

    async def test_basic_multi_repo(self, client: Client):
        result = await client.get_prompt(
            "multi_repo_task",
            {
                "repos": "api-server,web-frontend",
                "task_description": "Update auth flow",
            },
        )
        text = result.messages[0].content.text
        assert "api-server" in text
        assert "web-frontend" in text
        assert "Update auth flow" in text
        assert "2" in text  # repo count

    async def test_with_dependencies(self, client: Client):
        result = await client.get_prompt(
            "multi_repo_task",
            {
                "repos": "shared,api,frontend",
                "task_description": "Migrate to v2",
                "dependencies": "shared→api,api→frontend",
            },
        )
        text = result.messages[0].content.text
        assert "shared→api" in text
        assert "dependency order" in text.lower()


class TestCodeReviewPrompt:
    async def test_prompt_registered(self, client: Client):
        prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert "code_review" in names

    async def test_basic_review(self, client: Client):
        result = await client.get_prompt(
            "code_review",
            {"repo_name": "codegen-bridge", "pr_number": "42"},
        )
        text = result.messages[0].content.text
        assert "codegen-bridge" in text
        assert "42" in text
        assert "Correctness" in text
        assert "Tests" in text

    async def test_with_focus_areas(self, client: Client):
        result = await client.get_prompt(
            "code_review",
            {
                "repo_name": "codegen-bridge",
                "pr_number": "42",
                "focus_areas": "security,performance",
            },
        )
        text = result.messages[0].content.text
        assert "security" in text
        assert "performance" in text
