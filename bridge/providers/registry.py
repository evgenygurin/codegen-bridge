"""Provider registry — factory functions for all non-OpenAPI providers.

The OpenAPI provider requires an HTTP client and org_id, so it's created
separately in the server lifespan.  The providers here are static/filesystem
based and can be created without async context.

Usage in server lifespan::

    from bridge.providers import create_all_providers

    for provider in create_all_providers():
        server.add_provider(provider)
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastmcp.server.providers import Provider
from fastmcp.server.providers.skills import SkillsDirectoryProvider

from bridge.providers.agents import AgentsProvider
from bridge.providers.commands import CommandsProvider

logger = logging.getLogger("bridge.providers.registry")

# Default paths relative to the project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_SKILLS_DIR = _PROJECT_ROOT / "skills"
_DEFAULT_COMMANDS_DIR = _PROJECT_ROOT / "commands"
_DEFAULT_AGENTS_DIR = _PROJECT_ROOT / "agents"


def create_skills_provider(
    skills_dir: str | Path | None = None,
) -> SkillsDirectoryProvider | None:
    """Create a SkillsDirectoryProvider for agent skill files.

    Scans the given directory for subdirectories containing ``SKILL.md``
    and exposes each skill as an MCP resource.

    Args:
        skills_dir: Path to the skills root directory.
            Defaults to ``<project>/skills/``.

    Returns:
        Configured provider, or ``None`` if the directory doesn't exist
        or contains no valid skills.
    """
    root = Path(skills_dir) if skills_dir else _DEFAULT_SKILLS_DIR

    if not root.is_dir():
        logger.info("Skills directory not found: %s", root)
        return None

    # Check that at least one skill subfolder exists
    skill_folders = [d for d in root.iterdir() if d.is_dir() and (d / "SKILL.md").is_file()]
    if not skill_folders:
        logger.info("No skills found in: %s", root)
        return None

    logger.info(
        "Creating SkillsDirectoryProvider: root=%s, skills=%d",
        root,
        len(skill_folders),
    )
    return SkillsDirectoryProvider(roots=root)


def create_commands_provider(
    commands_dir: str | Path | None = None,
) -> CommandsProvider | None:
    """Create a CommandsProvider for slash-command markdown files.

    Args:
        commands_dir: Path to the commands directory.
            Defaults to ``<project>/commands/``.

    Returns:
        Configured provider, or ``None`` if the directory doesn't exist
        or contains no ``.md`` files.
    """
    root = Path(commands_dir) if commands_dir else _DEFAULT_COMMANDS_DIR

    if not root.is_dir():
        logger.info("Commands directory not found: %s", root)
        return None

    md_files = list(root.glob("*.md"))
    if not md_files:
        logger.info("No command files found in: %s", root)
        return None

    logger.info(
        "Creating CommandsProvider: root=%s, commands=%d",
        root,
        len(md_files),
    )
    return CommandsProvider(commands_dir=root)


def create_agents_provider(
    agents_dir: str | Path | None = None,
) -> AgentsProvider | None:
    """Create an AgentsProvider for agent definition markdown files.

    Agent definitions are designed to be used with the Claude Code **Task**
    tool.  Each ``.md`` file describes a subagent workflow that uses the
    codegen MCP tools.

    Args:
        agents_dir: Path to the agents directory.
            Defaults to ``<project>/agents/``.

    Returns:
        Configured provider, or ``None`` if the directory doesn't exist
        or contains no ``.md`` files.
    """
    root = Path(agents_dir) if agents_dir else _DEFAULT_AGENTS_DIR

    if not root.is_dir():
        logger.info("Agents directory not found: %s", root)
        return None

    md_files = list(root.glob("*.md"))
    if not md_files:
        logger.info("No agent files found in: %s", root)
        return None

    logger.info(
        "Creating AgentsProvider: root=%s, agents=%d",
        root,
        len(md_files),
    )
    return AgentsProvider(agents_dir=root)


def create_all_providers(
    *,
    skills_dir: str | Path | None = None,
    commands_dir: str | Path | None = None,
    agents_dir: str | Path | None = None,
) -> list[Provider]:
    """Create all filesystem-based providers.

    Convenience factory that creates the skills, commands, and agents
    providers.  Providers whose directories don't exist are silently skipped.

    Args:
        skills_dir: Override for skills directory path.
        commands_dir: Override for commands directory path.
        agents_dir: Override for agents directory path.

    Returns:
        List of successfully created providers (may be empty).
    """
    providers: list[Provider] = []

    skills = create_skills_provider(skills_dir)
    if skills is not None:
        providers.append(skills)

    commands = create_commands_provider(commands_dir)
    if commands is not None:
        providers.append(commands)

    agents = create_agents_provider(agents_dir)
    if agents is not None:
        providers.append(agents)

    logger.info("Provider registry created %d filesystem providers", len(providers))
    return providers
