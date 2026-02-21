"""MCP providers for the Codegen Bridge server.

Providers source MCP components (tools, resources, prompts) from various
backends.  The Bridge uses three provider types:

1. **OpenAPIProvider** — auto-generates tools from the Codegen REST API spec.
   Configured in ``bridge.openapi_utils`` and registered during server lifespan.

2. **SkillsDirectoryProvider** — exposes agent skills from the ``skills/``
   directory as MCP resources.  Each skill folder must contain a ``SKILL.md``.

3. **CommandsProvider** — exposes slash-command markdown files from the
   ``commands/`` directory as MCP resources.

Usage::

    from bridge.providers import create_all_providers

    for provider in create_all_providers():
        server.add_provider(provider)
"""

from bridge.providers.commands import CommandsProvider
from bridge.providers.registry import (
    create_all_providers,
    create_commands_provider,
    create_skills_provider,
)

__all__ = [
    "CommandsProvider",
    "create_all_providers",
    "create_commands_provider",
    "create_skills_provider",
]
