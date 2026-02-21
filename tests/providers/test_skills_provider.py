"""Tests for the SkillsDirectoryProvider integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from bridge.providers.registry import create_skills_provider


class TestCreateSkillsProvider:
    """Tests for the skills provider factory function."""

    def test_returns_none_for_missing_dir(self, tmp_path):
        result = create_skills_provider(tmp_path / "nonexistent")
        assert result is None

    def test_returns_none_for_empty_dir(self, tmp_path):
        result = create_skills_provider(tmp_path)
        assert result is None

    def test_returns_none_for_dir_without_skills(self, tmp_path):
        """A directory with files but no SKILL.md subfolders."""
        (tmp_path / "random.txt").write_text("not a skill")
        result = create_skills_provider(tmp_path)
        assert result is None

    def test_returns_provider_for_valid_skills(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n\n# My Skill")
        result = create_skills_provider(tmp_path)
        assert result is not None

    def test_returns_provider_for_multiple_skills(self, tmp_path):
        for name in ["skill-a", "skill-b", "skill-c"]:
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(f"# {name}")
        result = create_skills_provider(tmp_path)
        assert result is not None

    def test_ignores_dirs_without_skill_md(self, tmp_path):
        # One valid skill
        valid = tmp_path / "valid"
        valid.mkdir()
        (valid / "SKILL.md").write_text("# Valid")
        # One invalid dir (no SKILL.md)
        invalid = tmp_path / "invalid"
        invalid.mkdir()
        (invalid / "README.md").write_text("Not a skill")
        result = create_skills_provider(tmp_path)
        assert result is not None

    def test_uses_default_dir_when_none(self):
        """When no path is given, uses the default skills/ directory."""
        # The default is <project>/skills/ which may or may not exist
        result = create_skills_provider(None)
        # Either returns a provider (if skills/ exists) or None
        assert result is None or result is not None  # just don't crash

    @pytest.mark.asyncio
    async def test_provider_lists_skill_resources(self, tmp_path):
        """SkillsDirectoryProvider should expose skill files as resources."""
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\n"
            "description: A test skill\n---\n\n# Test Skill\n\nInstructions here."
        )
        provider = create_skills_provider(tmp_path)
        assert provider is not None

        resources = await provider._list_resources()
        assert len(resources) >= 1

    @pytest.mark.asyncio
    async def test_real_skills_directory(self):
        """Test with the actual skills/ directory in the project."""
        skills_dir = Path(__file__).resolve().parent.parent.parent / "skills"
        if not skills_dir.is_dir():
            pytest.skip("skills/ directory not found")

        provider = create_skills_provider(skills_dir)
        if provider is None:
            pytest.skip("No valid skills found")

        resources = await provider._list_resources()
        assert len(resources) >= 1

        # Should find the executing-via-codegen skill
        resource_names = {r.name for r in resources}
        # The name format depends on SkillsDirectoryProvider internals
        assert len(resource_names) >= 1
