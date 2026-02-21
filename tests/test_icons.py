"""Tests for icon registration on tools, resources, and prompts."""

from __future__ import annotations

import base64

import pytest
from mcp.types import Icon

from bridge.icons import (
    ICON_CONFIG,
    ICON_CONTEXT,
    ICON_DASHBOARD,
    ICON_DELEGATE,
    ICON_EXECUTION,
    ICON_GET_RUN,
    ICON_LIST,
    ICON_LOGS,
    ICON_MONITOR,
    ICON_ORG,
    ICON_REPO,
    ICON_RESUME,
    ICON_RULES,
    ICON_RUN,
    ICON_STOP,
    ICON_SUMMARY,
    ICON_TEMPLATE,
    _svg_icon,
)

# ── Unit tests for the _svg_icon helper ───────────────────


class TestSvgIconHelper:
    def test_returns_single_element_list(self):
        result = _svg_icon('<circle cx="12" cy="12" r="10"/>')
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returns_icon_instance(self):
        result = _svg_icon('<circle cx="12" cy="12" r="10"/>')
        assert isinstance(result[0], Icon)

    def test_src_is_data_uri(self):
        result = _svg_icon('<circle cx="12" cy="12" r="10"/>')
        assert result[0].src.startswith("data:image/svg+xml;base64,")

    def test_mime_type_is_svg(self):
        result = _svg_icon('<circle cx="12" cy="12" r="10"/>')
        assert result[0].mimeType == "image/svg+xml"

    def test_data_uri_decodes_to_valid_svg(self):
        result = _svg_icon('<rect x="0" y="0" width="24" height="24"/>')
        b64_part = result[0].src.split(",", 1)[1]
        svg = base64.b64decode(b64_part).decode()
        assert svg.startswith("<svg")
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg
        assert 'width="24"' in svg
        assert 'height="24"' in svg
        assert "<rect" in svg
        assert svg.endswith("</svg>")


# ── Verify all icon constants are well-formed ─────────────

ALL_ICONS = {
    "ICON_RUN": ICON_RUN,
    "ICON_GET_RUN": ICON_GET_RUN,
    "ICON_LIST": ICON_LIST,
    "ICON_RESUME": ICON_RESUME,
    "ICON_STOP": ICON_STOP,
    "ICON_LOGS": ICON_LOGS,
    "ICON_EXECUTION": ICON_EXECUTION,
    "ICON_CONTEXT": ICON_CONTEXT,
    "ICON_RULES": ICON_RULES,
    "ICON_ORG": ICON_ORG,
    "ICON_REPO": ICON_REPO,
    "ICON_CONFIG": ICON_CONFIG,
    "ICON_DASHBOARD": ICON_DASHBOARD,
    "ICON_DELEGATE": ICON_DELEGATE,
    "ICON_MONITOR": ICON_MONITOR,
    "ICON_TEMPLATE": ICON_TEMPLATE,
    "ICON_SUMMARY": ICON_SUMMARY,
}


class TestIconConstants:
    @pytest.mark.parametrize("name,icon_list", list(ALL_ICONS.items()))
    def test_is_single_element_list(self, name: str, icon_list: list[Icon]):
        assert len(icon_list) == 1, f"{name} should have exactly one icon"

    @pytest.mark.parametrize("name,icon_list", list(ALL_ICONS.items()))
    def test_is_svg_data_uri(self, name: str, icon_list: list[Icon]):
        assert icon_list[0].src.startswith("data:image/svg+xml;base64,"), name

    @pytest.mark.parametrize("name,icon_list", list(ALL_ICONS.items()))
    def test_has_svg_mime_type(self, name: str, icon_list: list[Icon]):
        assert icon_list[0].mimeType == "image/svg+xml", name

    @pytest.mark.parametrize("name,icon_list", list(ALL_ICONS.items()))
    def test_decodes_to_valid_svg(self, name: str, icon_list: list[Icon]):
        b64_part = icon_list[0].src.split(",", 1)[1]
        svg = base64.b64decode(b64_part).decode()
        assert svg.startswith("<svg"), f"{name}: SVG must start with <svg"
        assert svg.endswith("</svg>"), f"{name}: SVG must end with </svg>"

    def test_all_icons_are_unique(self):
        srcs = [icon_list[0].src for icon_list in ALL_ICONS.values()]
        assert len(srcs) == len(set(srcs)), "All icon data URIs should be unique"


# ── Integration: verify icons are attached to server components ──

from fastmcp import Client  # noqa: E402

from bridge.server import mcp  # noqa: E402

TOOL_ICON_MAP = {
    "codegen_create_run": ICON_RUN,
    "codegen_get_run": ICON_GET_RUN,
    "codegen_list_runs": ICON_LIST,
    "codegen_resume_run": ICON_RESUME,
    "codegen_stop_run": ICON_STOP,
    "codegen_get_logs": ICON_LOGS,
    "codegen_start_execution": ICON_EXECUTION,
    "codegen_get_execution_context": ICON_CONTEXT,
    "codegen_get_agent_rules": ICON_RULES,
    "codegen_list_orgs": ICON_ORG,
    "codegen_list_repos": ICON_REPO,
}


class TestToolIcons:
    @pytest.mark.parametrize("tool_name,expected_icon", list(TOOL_ICON_MAP.items()))
    async def test_tool_has_correct_icon(
        self, client: Client, tool_name: str, expected_icon: list[Icon]
    ):
        tool = await mcp.get_tool(tool_name)
        assert tool.icons is not None, f"{tool_name} should have icons"
        assert len(tool.icons) == 1
        assert tool.icons[0].src == expected_icon[0].src

    async def test_all_core_tools_have_icons(self, client: Client):
        """Every core tool registered on the server should have an icon."""
        for tool_name in TOOL_ICON_MAP:
            tool = await mcp.get_tool(tool_name)
            assert tool.icons, f"{tool_name} is missing icons"


RESOURCE_ICON_MAP = {
    "codegen://config": ICON_CONFIG,
    "codegen://execution/current": ICON_DASHBOARD,
}


class TestResourceIcons:
    @pytest.mark.parametrize("uri,expected_icon", list(RESOURCE_ICON_MAP.items()))
    async def test_resource_has_correct_icon(
        self, client: Client, uri: str, expected_icon: list[Icon]
    ):
        resource = await mcp.get_resource(uri)
        assert resource.icons is not None, f"{uri} should have icons"
        assert len(resource.icons) == 1
        assert resource.icons[0].src == expected_icon[0].src


PROMPT_ICON_MAP = {
    "delegate_task": ICON_DELEGATE,
    "monitor_runs": ICON_MONITOR,
    "build_task_prompt_template": ICON_TEMPLATE,
    "execution_summary": ICON_SUMMARY,
}


class TestPromptIcons:
    @pytest.mark.parametrize("prompt_name,expected_icon", list(PROMPT_ICON_MAP.items()))
    async def test_prompt_has_correct_icon(
        self, client: Client, prompt_name: str, expected_icon: list[Icon]
    ):
        prompt = await mcp.get_prompt(prompt_name)
        assert prompt.icons is not None, f"{prompt_name} should have icons"
        assert len(prompt.icons) == 1
        assert prompt.icons[0].src == expected_icon[0].src
