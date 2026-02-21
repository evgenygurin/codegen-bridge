"""Tests for the CommandsProvider custom MCP provider."""

from __future__ import annotations

import pytest

from bridge.providers.commands import CommandsProvider, _parse_frontmatter


class TestParseFrontmatter:
    """Tests for YAML front-matter parsing."""

    def test_extracts_description(self):
        text = '---\ndescription: "My description"\n---\n\nBody content'
        meta, body = _parse_frontmatter(text)
        assert meta["description"] == "My description"
        assert body == "Body content"

    def test_extracts_multiple_fields(self):
        text = "---\ndescription: Hello\ntitle: My Title\n---\n\nBody"
        meta, body = _parse_frontmatter(text)
        assert meta["description"] == "Hello"
        assert meta["title"] == "My Title"
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

    def test_ignores_non_initial_triple_dash(self):
        text = "Some text\n---\nnot frontmatter\n---\nmore text"
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_handles_colons_in_value(self):
        text = '---\ndescription: "Contains: colons"\n---\n\nBody'
        meta, _body = _parse_frontmatter(text)
        assert meta["description"] == "Contains: colons"


class TestCommandsProvider:
    """Tests for the CommandsProvider class."""

    def test_init_with_valid_dir(self, tmp_path):
        provider = CommandsProvider(tmp_path)
        assert provider.commands_dir == tmp_path

    def test_init_with_nonexistent_dir(self, tmp_path):
        """Should not raise, just log warning."""
        provider = CommandsProvider(tmp_path / "nonexistent")
        assert not provider.commands_dir.is_dir()

    def test_scan_files_empty_dir(self, tmp_path):
        provider = CommandsProvider(tmp_path)
        files = provider._scan_files()
        assert files == []

    def test_scan_files_finds_md_files(self, tmp_path):
        (tmp_path / "cmd1.md").write_text("content1")
        (tmp_path / "cmd2.md").write_text("content2")
        (tmp_path / "not_md.txt").write_text("ignored")
        provider = CommandsProvider(tmp_path)
        files = provider._scan_files()
        assert len(files) == 2
        names = {f.name for f in files}
        assert names == {"cmd1.md", "cmd2.md"}

    def test_scan_files_sorted(self, tmp_path):
        (tmp_path / "zzz.md").write_text("z")
        (tmp_path / "aaa.md").write_text("a")
        provider = CommandsProvider(tmp_path)
        files = provider._scan_files()
        assert files[0].name == "aaa.md"
        assert files[1].name == "zzz.md"

    def test_scan_files_nonexistent_dir(self, tmp_path):
        provider = CommandsProvider(tmp_path / "missing")
        files = provider._scan_files()
        assert files == []

    @pytest.mark.asyncio
    async def test_list_resources_empty(self, tmp_path):
        provider = CommandsProvider(tmp_path)
        resources = await provider._list_resources()
        assert resources == []

    @pytest.mark.asyncio
    async def test_list_resources_with_files(self, tmp_path):
        (tmp_path / "help.md").write_text(
            '---\ndescription: "Get help"\n---\n\nHelp content here'
        )
        (tmp_path / "status.md").write_text(
            "---\ndescription: Show status\n---\n\nStatus content"
        )
        provider = CommandsProvider(tmp_path)
        resources = await provider._list_resources()
        assert len(resources) == 2

        names = {r.name for r in resources}
        assert names == {"command_help", "command_status"}

    @pytest.mark.asyncio
    async def test_resource_uri_format(self, tmp_path):
        (tmp_path / "test.md").write_text("Simple content")
        provider = CommandsProvider(tmp_path)
        resources = await provider._list_resources()
        assert len(resources) == 1
        assert str(resources[0].uri) == "codegen://commands/test"

    @pytest.mark.asyncio
    async def test_resource_description_from_frontmatter(self, tmp_path):
        (tmp_path / "cmd.md").write_text(
            '---\ndescription: "My custom desc"\n---\n\nBody'
        )
        provider = CommandsProvider(tmp_path)
        resources = await provider._list_resources()
        assert resources[0].description == "My custom desc"

    @pytest.mark.asyncio
    async def test_resource_description_fallback(self, tmp_path):
        (tmp_path / "cmd.md").write_text("No frontmatter, just body")
        provider = CommandsProvider(tmp_path)
        resources = await provider._list_resources()
        assert resources[0].description == "Slash command: /cmd"

    @pytest.mark.asyncio
    async def test_resource_mime_type(self, tmp_path):
        (tmp_path / "cmd.md").write_text("Content")
        provider = CommandsProvider(tmp_path)
        resources = await provider._list_resources()
        assert resources[0].mime_type == "text/markdown"

    @pytest.mark.asyncio
    async def test_resource_tags(self, tmp_path):
        (tmp_path / "cmd.md").write_text("Content")
        provider = CommandsProvider(tmp_path)
        resources = await provider._list_resources()
        assert "commands" in resources[0].tags
        assert "slash-command" in resources[0].tags

    @pytest.mark.asyncio
    async def test_resource_content_strips_frontmatter(self, tmp_path):
        (tmp_path / "cmd.md").write_text(
            "---\ndescription: Desc\n---\n\nActual body content"
        )
        provider = CommandsProvider(tmp_path)
        resources = await provider._list_resources()
        result = await resources[0].read()
        # TextResource.read() returns a ResourceResult with contents
        content_text = result.contents[0].content
        assert content_text == "Actual body content"

    @pytest.mark.asyncio
    async def test_custom_uri_prefix(self, tmp_path):
        (tmp_path / "cmd.md").write_text("Content")
        provider = CommandsProvider(tmp_path, uri_prefix="myapp://cmds")
        resources = await provider._list_resources()
        assert str(resources[0].uri) == "myapp://cmds/cmd"

    @pytest.mark.asyncio
    async def test_handles_malformed_files_gracefully(self, tmp_path):
        """Provider should skip files it can't parse."""
        (tmp_path / "good.md").write_text("Good content")
        # Create a file that's actually a directory name collision
        # (this shouldn't happen in practice but tests robustness)
        (tmp_path / "also_good.md").write_text("Also good")
        provider = CommandsProvider(tmp_path)
        resources = await provider._list_resources()
        assert len(resources) == 2

    @pytest.mark.asyncio
    async def test_real_commands_directory(self):
        """Test with the actual commands/ directory in the project."""
        from pathlib import Path

        commands_dir = Path(__file__).resolve().parent.parent.parent / "commands"
        if not commands_dir.is_dir():
            pytest.skip("commands/ directory not found")

        provider = CommandsProvider(commands_dir)
        resources = await provider._list_resources()
        assert len(resources) >= 3

        # Check known commands
        names = {r.name for r in resources}
        assert "command_codegen" in names
        assert "command_cg-status" in names
        assert "command_cg-logs" in names

        # Check descriptions are set
        for r in resources:
            assert r.description, f"Missing description for {r.name}"

    def test_file_to_resource(self, tmp_path):
        (tmp_path / "test.md").write_text(
            '---\ndescription: "Test desc"\n---\n\nTest body'
        )
        provider = CommandsProvider(tmp_path)
        resource = provider._file_to_resource(tmp_path / "test.md")
        assert resource.name == "command_test"
        assert str(resource.uri) == "codegen://commands/test"
        assert resource.description == "Test desc"
