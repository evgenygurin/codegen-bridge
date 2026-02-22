"""Tests for the AgentsProvider custom MCP provider."""

from __future__ import annotations

import pytest

from bridge.providers.agents import AgentsProvider, _parse_frontmatter


class TestParseFrontmatter:
    """Tests for YAML front-matter parsing (agents module)."""

    def test_extracts_description(self):
        text = '---\ndescription: "Agent description"\n---\n\nBody content'
        meta, body = _parse_frontmatter(text)
        assert meta["description"] == "Agent description"
        assert body == "Body content"

    def test_extracts_name_and_description(self):
        text = "---\nname: my-agent\ndescription: Does things\n---\n\nBody"
        meta, body = _parse_frontmatter(text)
        assert meta["name"] == "my-agent"
        assert meta["description"] == "Does things"
        assert body == "Body"

    def test_strips_quotes(self):
        text = "---\ndescription: 'single quoted'\n---\n\nBody"
        meta, _body = _parse_frontmatter(text)
        assert meta["description"] == "single quoted"

    def test_handles_no_frontmatter(self):
        text = "Just plain markdown\n\nWith paragraphs"
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_handles_empty_string(self):
        meta, body = _parse_frontmatter("")
        assert meta == {}
        assert body == ""

    def test_handles_frontmatter_only(self):
        text = "---\nkey: value\n---\n"
        meta, body = _parse_frontmatter(text)
        assert meta["key"] == "value"
        assert body == ""

    def test_handles_colons_in_value(self):
        text = '---\ndescription: "Contains: colons: here"\n---\n\nBody'
        meta, _body = _parse_frontmatter(text)
        assert meta["description"] == "Contains: colons: here"


class TestAgentsProvider:
    """Tests for the AgentsProvider class."""

    def test_init_with_valid_dir(self, tmp_path):
        provider = AgentsProvider(tmp_path)
        assert provider.agents_dir == tmp_path

    def test_init_with_nonexistent_dir(self, tmp_path):
        """Should not raise, just log warning."""
        provider = AgentsProvider(tmp_path / "nonexistent")
        assert not provider.agents_dir.is_dir()

    def test_scan_files_empty_dir(self, tmp_path):
        provider = AgentsProvider(tmp_path)
        files = provider._scan_files()
        assert files == []

    def test_scan_files_finds_md_files(self, tmp_path):
        (tmp_path / "agent1.md").write_text("content1")
        (tmp_path / "agent2.md").write_text("content2")
        (tmp_path / "not_md.txt").write_text("ignored")
        provider = AgentsProvider(tmp_path)
        files = provider._scan_files()
        assert len(files) == 2
        names = {f.name for f in files}
        assert names == {"agent1.md", "agent2.md"}

    def test_scan_files_sorted(self, tmp_path):
        (tmp_path / "zzz.md").write_text("z")
        (tmp_path / "aaa.md").write_text("a")
        provider = AgentsProvider(tmp_path)
        files = provider._scan_files()
        assert files[0].name == "aaa.md"
        assert files[1].name == "zzz.md"

    def test_scan_files_nonexistent_dir(self, tmp_path):
        provider = AgentsProvider(tmp_path / "missing")
        files = provider._scan_files()
        assert files == []

    @pytest.mark.asyncio
    async def test_list_resources_empty(self, tmp_path):
        provider = AgentsProvider(tmp_path)
        resources = await provider._list_resources()
        assert resources == []

    @pytest.mark.asyncio
    async def test_list_resources_with_files(self, tmp_path):
        (tmp_path / "delegator.md").write_text(
            '---\nname: delegator\ndescription: "Delegates tasks"\n---\n\nAgent body'
        )
        (tmp_path / "reviewer.md").write_text(
            "---\nname: reviewer\ndescription: Reviews PRs\n---\n\nReview body"
        )
        provider = AgentsProvider(tmp_path)
        resources = await provider._list_resources()
        assert len(resources) == 2

        names = {r.name for r in resources}
        assert names == {"agent_delegator", "agent_reviewer"}

    @pytest.mark.asyncio
    async def test_resource_uri_format(self, tmp_path):
        (tmp_path / "test-agent.md").write_text("Simple content")
        provider = AgentsProvider(tmp_path)
        resources = await provider._list_resources()
        assert len(resources) == 1
        assert str(resources[0].uri) == "codegen://agents/test-agent"

    @pytest.mark.asyncio
    async def test_resource_description_from_frontmatter(self, tmp_path):
        (tmp_path / "agent.md").write_text(
            '---\nname: my-agent\ndescription: "Custom agent description"\n---\n\nBody'
        )
        provider = AgentsProvider(tmp_path)
        resources = await provider._list_resources()
        assert resources[0].description == "Custom agent description"

    @pytest.mark.asyncio
    async def test_resource_description_fallback(self, tmp_path):
        (tmp_path / "my-agent.md").write_text("No frontmatter, just body")
        provider = AgentsProvider(tmp_path)
        resources = await provider._list_resources()
        assert resources[0].description == "Agent: my-agent"

    @pytest.mark.asyncio
    async def test_resource_name_from_frontmatter(self, tmp_path):
        (tmp_path / "file.md").write_text("---\nname: custom-name\ndescription: Desc\n---\n\nBody")
        provider = AgentsProvider(tmp_path)
        resources = await provider._list_resources()
        # Resource name uses the file stem, not the frontmatter name
        assert resources[0].name == "agent_file"

    @pytest.mark.asyncio
    async def test_resource_name_hyphen_to_underscore(self, tmp_path):
        (tmp_path / "codegen-delegator.md").write_text("content")
        provider = AgentsProvider(tmp_path)
        resources = await provider._list_resources()
        assert resources[0].name == "agent_codegen_delegator"

    @pytest.mark.asyncio
    async def test_resource_mime_type(self, tmp_path):
        (tmp_path / "agent.md").write_text("Content")
        provider = AgentsProvider(tmp_path)
        resources = await provider._list_resources()
        assert resources[0].mime_type == "text/markdown"

    @pytest.mark.asyncio
    async def test_resource_tags(self, tmp_path):
        (tmp_path / "agent.md").write_text("Content")
        provider = AgentsProvider(tmp_path)
        resources = await provider._list_resources()
        assert "agents" in resources[0].tags
        assert "task-tool" in resources[0].tags

    @pytest.mark.asyncio
    async def test_resource_content_strips_frontmatter(self, tmp_path):
        (tmp_path / "agent.md").write_text("---\ndescription: Desc\n---\n\nActual body content")
        provider = AgentsProvider(tmp_path)
        resources = await provider._list_resources()
        result = await resources[0].read()
        content_text = result.contents[0].content
        assert content_text == "Actual body content"

    @pytest.mark.asyncio
    async def test_custom_uri_prefix(self, tmp_path):
        (tmp_path / "agent.md").write_text("Content")
        provider = AgentsProvider(tmp_path, uri_prefix="myapp://agents")
        resources = await provider._list_resources()
        assert str(resources[0].uri) == "myapp://agents/agent"

    @pytest.mark.asyncio
    async def test_handles_malformed_files_gracefully(self, tmp_path):
        """Provider should skip files it can't parse."""
        (tmp_path / "good.md").write_text("Good content")
        (tmp_path / "also_good.md").write_text("Also good")
        provider = AgentsProvider(tmp_path)
        resources = await provider._list_resources()
        assert len(resources) == 2

    @pytest.mark.asyncio
    async def test_real_agents_directory(self):
        """Test with the actual agents/ directory in the project."""
        from pathlib import Path

        agents_dir = Path(__file__).resolve().parent.parent.parent / "agents"
        if not agents_dir.is_dir():
            pytest.skip("agents/ directory not found")

        provider = AgentsProvider(agents_dir)
        resources = await provider._list_resources()
        assert len(resources) >= 2

        # Check known agents
        names = {r.name for r in resources}
        assert "agent_codegen_delegator" in names
        assert "agent_pr_reviewer" in names

        # Check descriptions are set from frontmatter
        for r in resources:
            assert r.description, f"Missing description for {r.name}"

    def test_file_to_resource(self, tmp_path):
        (tmp_path / "test.md").write_text(
            '---\nname: test-agent\ndescription: "Test desc"\n---\n\nTest body'
        )
        provider = AgentsProvider(tmp_path)
        resource = provider._file_to_resource(tmp_path / "test.md")
        assert resource.name == "agent_test"
        assert str(resource.uri) == "codegen://agents/test"
        assert resource.description == "Test desc"

    def test_file_to_resource_description_uses_name_fallback(self, tmp_path):
        (tmp_path / "my-agent.md").write_text("---\nname: my-agent\n---\n\nBody")
        provider = AgentsProvider(tmp_path)
        resource = provider._file_to_resource(tmp_path / "my-agent.md")
        assert resource.description == "Agent: my-agent"
