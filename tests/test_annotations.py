"""Validation tests for ToolAnnotations presets and tool coverage."""

from __future__ import annotations

import os

# Set test env before importing bridge modules.
os.environ["CODEGEN_API_KEY"] = "test-key"
os.environ["CODEGEN_ORG_ID"] = "42"
os.environ["CODEGEN_ALLOW_DANGEROUS_TOOLS"] = "true"

from fastmcp import Client

from bridge.annotations import (
    CREATES,
    DESTRUCTIVE,
    MUTATES,
    MUTATES_LOCAL,
    READ_ONLY,
    READ_ONLY_LOCAL,
)
from bridge.middleware.authorization import DEFAULT_DANGEROUS_TOOLS
from bridge.openapi_utils import TOOL_NAMES

# OpenAPI-generated tools cannot carry ToolAnnotations.
OPENAPI_TOOL_NAMES = frozenset(TOOL_NAMES.values())


def test_read_only_is_safe() -> None:
    assert READ_ONLY.readOnlyHint is True
    assert READ_ONLY.destructiveHint is False
    assert READ_ONLY.idempotentHint is True
    assert READ_ONLY.openWorldHint is True


def test_read_only_local_is_safe_local() -> None:
    assert READ_ONLY_LOCAL.readOnlyHint is True
    assert READ_ONLY_LOCAL.destructiveHint is False
    assert READ_ONLY_LOCAL.idempotentHint is True
    assert READ_ONLY_LOCAL.openWorldHint is False


def test_creates_is_not_idempotent() -> None:
    assert CREATES.readOnlyHint is False
    assert CREATES.idempotentHint is False
    assert CREATES.destructiveHint is False
    assert CREATES.openWorldHint is True


def test_mutates_is_idempotent() -> None:
    assert MUTATES.readOnlyHint is False
    assert MUTATES.destructiveHint is False
    assert MUTATES.idempotentHint is True
    assert MUTATES.openWorldHint is True


def test_mutates_local_is_idempotent_local() -> None:
    assert MUTATES_LOCAL.readOnlyHint is False
    assert MUTATES_LOCAL.destructiveHint is False
    assert MUTATES_LOCAL.idempotentHint is True
    assert MUTATES_LOCAL.openWorldHint is False


def test_destructive_is_dangerous() -> None:
    assert DESTRUCTIVE.readOnlyHint is False
    assert DESTRUCTIVE.destructiveHint is True
    assert DESTRUCTIVE.idempotentHint is False
    assert DESTRUCTIVE.openWorldHint is True


class TestToolAnnotationCoverage:
    async def test_all_manual_tools_have_annotations(self, client: Client) -> None:
        """Every manually-registered codegen_* tool should have annotations."""
        tools = await client.list_tools()
        manual_tools = [
            tool
            for tool in tools
            if tool.name.startswith("codegen_") and tool.name not in OPENAPI_TOOL_NAMES
        ]

        missing = [tool.name for tool in manual_tools if tool.annotations is None]
        assert missing == [], f"Manual tools missing annotations: {missing}"

    async def test_dangerous_manual_tools_have_destructive_hint(
        self,
        client: Client,
    ) -> None:
        """Dangerous manual tools must be marked as destructive."""
        dangerous_manual_tools = DEFAULT_DANGEROUS_TOOLS - OPENAPI_TOOL_NAMES

        tools = await client.list_tools()
        tools_by_name = {tool.name: tool for tool in tools}

        for name in dangerous_manual_tools:
            tool = tools_by_name.get(name)
            assert tool is not None, f"Expected dangerous tool '{name}' to be registered"
            assert tool.annotations is not None, f"Dangerous tool '{name}' missing annotations"
            assert tool.annotations.destructiveHint is True, (
                f"Dangerous tool '{name}' should have destructiveHint=True"
            )

    async def test_read_only_tools_have_correct_hints(self, client: Client) -> None:
        """Selected read-only tools should be marked readOnly."""
        read_tools = {
            "codegen_get_run",
            "codegen_list_runs",
            "codegen_get_logs",
            "codegen_get_current_user",
            "codegen_list_users",
            "codegen_get_user",
            "codegen_list_orgs",
            "codegen_list_repos",
            "codegen_get_organization_settings",
            "codegen_get_integrations",
            "codegen_get_webhook_config",
            "codegen_get_oauth_status",
            "codegen_get_mcp_providers",
            "codegen_get_check_suite_settings",
            "codegen_get_execution_context",
            "codegen_get_agent_rules",
        }

        tools = await client.list_tools()
        tools_by_name = {tool.name: tool for tool in tools}

        for name in read_tools:
            tool = tools_by_name.get(name)
            if tool is None or tool.annotations is None:
                # OpenAPI-generated tools may not have annotations.
                continue
            assert tool.annotations.readOnlyHint is True, (
                f"Read tool '{name}' should have readOnlyHint=True"
            )
