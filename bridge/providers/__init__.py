"""MCP providers for the Codegen Bridge server.

Providers source MCP components (tools, resources, prompts) from various
backends.  The Bridge uses four provider types:

1. **OpenAPIProvider** — auto-generates tools from the Codegen REST API spec.
   Configured in ``bridge.openapi_utils`` and registered during server lifespan.

2. **SkillsDirectoryProvider** — exposes agent skills from the ``skills/``
   directory as MCP resources.  Each skill folder must contain a ``SKILL.md``.

3. **CommandsProvider** — exposes slash-command markdown files from the
   ``commands/`` directory as MCP resources.

4. **AgentsProvider** — exposes agent definition markdown files from the
   ``agents/`` directory as MCP resources.  Each agent defines a subagent
   workflow for the Claude Code Task tool.

Usage::

    from bridge.providers import create_all_providers

    for provider in create_all_providers():
        server.add_provider(provider)
"""

from bridge.providers.agents import AgentsProvider
from bridge.providers.commands import CommandsProvider
from bridge.providers.registry import (
    create_agents_provider,
    create_all_providers,
    create_commands_provider,
    create_skills_provider,
)
from bridge.providers.remote import create_remote_proxy

__all__ = [
    "AgentsProvider",
    "CommandsProvider",
    "create_agents_provider",
    "create_all_providers",
    "create_commands_provider",
    "create_remote_proxy",
    "create_skills_provider",
]
