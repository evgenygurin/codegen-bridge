"""Tests for the provider registry factory functions."""

from __future__ import annotations

from pathlib import Path

from bridge.providers.agents import AgentsProvider
from bridge.providers.commands import CommandsProvider
from bridge.providers.registry import (
    create_agents_provider,
    create_all_providers,
    create_commands_provider,
)


class TestCreateCommandsProvider:
    def test_returns_none_for_missing_dir(self, tmp_path):
        result = create_commands_provider(tmp_path / "nonexistent")
        assert result is None

    def test_returns_none_for_empty_dir(self, tmp_path):
        result = create_commands_provider(tmp_path)
        assert result is None

    def test_returns_provider_for_md_files(self, tmp_path):
        (tmp_path / "cmd.md").write_text("content")
        result = create_commands_provider(tmp_path)
        assert result is not None
        assert isinstance(result, CommandsProvider)

    def test_ignores_non_md_files(self, tmp_path):
        (tmp_path / "file.txt").write_text("not markdown")
        (tmp_path / "file.py").write_text("not markdown")
        result = create_commands_provider(tmp_path)
        assert result is None

    def test_uses_default_dir_when_none(self):
        result = create_commands_provider(None)
        # Either returns a provider (if commands/ exists) or None
        assert result is None or isinstance(result, CommandsProvider)


class TestCreateAgentsProvider:
    def test_returns_none_for_missing_dir(self, tmp_path):
        result = create_agents_provider(tmp_path / "nonexistent")
        assert result is None

    def test_returns_none_for_empty_dir(self, tmp_path):
        result = create_agents_provider(tmp_path)
        assert result is None

    def test_returns_provider_for_md_files(self, tmp_path):
        (tmp_path / "agent.md").write_text("content")
        result = create_agents_provider(tmp_path)
        assert result is not None
        assert isinstance(result, AgentsProvider)

    def test_ignores_non_md_files(self, tmp_path):
        (tmp_path / "file.txt").write_text("not markdown")
        (tmp_path / "file.py").write_text("not markdown")
        result = create_agents_provider(tmp_path)
        assert result is None

    def test_uses_default_dir_when_none(self):
        result = create_agents_provider(None)
        # Either returns a provider (if agents/ exists) or None
        assert result is None or isinstance(result, AgentsProvider)


class TestCreateAllProviders:
    def test_returns_empty_for_nonexistent_dirs(self, tmp_path):
        providers = create_all_providers(
            skills_dir=tmp_path / "no-skills",
            commands_dir=tmp_path / "no-commands",
            agents_dir=tmp_path / "no-agents",
        )
        assert providers == []

    def test_returns_commands_only(self, tmp_path):
        commands = tmp_path / "commands"
        commands.mkdir()
        (commands / "cmd.md").write_text("content")

        providers = create_all_providers(
            skills_dir=tmp_path / "no-skills",
            commands_dir=commands,
            agents_dir=tmp_path / "no-agents",
        )
        assert len(providers) == 1
        assert isinstance(providers[0], CommandsProvider)

    def test_returns_skills_only(self, tmp_path):
        skills = tmp_path / "skills"
        skills.mkdir()
        skill = skills / "my-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("# Skill")

        providers = create_all_providers(
            skills_dir=skills,
            commands_dir=tmp_path / "no-commands",
            agents_dir=tmp_path / "no-agents",
        )
        assert len(providers) == 1

    def test_returns_agents_only(self, tmp_path):
        agents = tmp_path / "agents"
        agents.mkdir()
        (agents / "my-agent.md").write_text("content")

        providers = create_all_providers(
            skills_dir=tmp_path / "no-skills",
            commands_dir=tmp_path / "no-commands",
            agents_dir=agents,
        )
        assert len(providers) == 1
        assert isinstance(providers[0], AgentsProvider)

    def test_returns_commands_and_agents(self, tmp_path):
        commands = tmp_path / "commands"
        commands.mkdir()
        (commands / "cmd.md").write_text("content")

        agents = tmp_path / "agents"
        agents.mkdir()
        (agents / "agent.md").write_text("content")

        providers = create_all_providers(
            skills_dir=tmp_path / "no-skills",
            commands_dir=commands,
            agents_dir=agents,
        )
        assert len(providers) == 2
        types = {type(p) for p in providers}
        assert CommandsProvider in types
        assert AgentsProvider in types

    def test_returns_all_three_providers(self, tmp_path):
        # Skills
        skills = tmp_path / "skills"
        skills.mkdir()
        skill = skills / "my-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("# Skill")

        # Commands
        commands = tmp_path / "commands"
        commands.mkdir()
        (commands / "cmd.md").write_text("content")

        # Agents
        agents = tmp_path / "agents"
        agents.mkdir()
        (agents / "agent.md").write_text("content")

        providers = create_all_providers(
            skills_dir=skills,
            commands_dir=commands,
            agents_dir=agents,
        )
        assert len(providers) == 3

    def test_uses_defaults_when_no_args(self):
        """When no args, uses project-relative defaults."""
        providers = create_all_providers()
        # Should work regardless of whether default dirs exist
        assert isinstance(providers, list)

    def test_real_project_providers(self):
        """Test with actual project directories."""
        project_root = Path(__file__).resolve().parent.parent.parent
        skills_dir = project_root / "skills"
        commands_dir = project_root / "commands"
        agents_dir = project_root / "agents"

        providers = create_all_providers(
            skills_dir=skills_dir,
            commands_dir=commands_dir,
            agents_dir=agents_dir,
        )

        # We know all three directories exist in the project
        if skills_dir.is_dir() and commands_dir.is_dir() and agents_dir.is_dir():
            # Should have at least commands + agents providers
            assert len(providers) >= 2
