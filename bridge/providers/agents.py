"""Custom provider that exposes agent definition markdown files as MCP resources.

Each ``.md`` file in the agents directory becomes an MCP resource with URI
``codegen://agents/{stem}``.  The YAML front-matter ``description`` field
(if present) is used as the resource description.

This follows the **Provider** pattern from FastMCP 3.x: a class that
implements ``_list_resources`` and optionally ``_get_resource`` to source
components from an arbitrary backend (in this case, a local directory).

Agent definitions are designed to be used with the Claude Code **Task** tool.
Each agent file contains structured instructions for how a subagent should
use the codegen MCP tools to accomplish a specific workflow (e.g., delegating
tasks, reviewing PRs).

Example directory layout::

    agents/
        codegen-delegator.md   -> codegen://agents/codegen-delegator
        pr-reviewer.md         -> codegen://agents/pr-reviewer
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from pathlib import Path

from fastmcp.resources import TextResource
from fastmcp.resources.resource import Resource
from fastmcp.server.providers import Provider

logger = logging.getLogger("bridge.providers.agents")

# Regex for YAML front-matter block (--- ... ---)
_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n?",
    re.DOTALL,
)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Extract YAML-like front-matter and body from a markdown file.

    Uses simple key: value parsing instead of a full YAML library to
    avoid adding a dependency.  Returns (metadata_dict, body_text).
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")

    body = text[match.end() :]
    return meta, body


class AgentsProvider(Provider):
    """Provider that exposes agent definition markdown files as MCP resources.

    Each ``.md`` file in *agents_dir* is exposed as a text resource.
    The resource URI follows the pattern ``codegen://agents/{name}``.

    Agent definitions contain instructions for Claude Code subagents that
    use the codegen MCP tools via the Task tool.

    Args:
        agents_dir: Path to the directory containing agent markdown files.
        uri_prefix: URI scheme and authority prefix for generated resources.
    """

    def __init__(
        self,
        agents_dir: str | Path,
        *,
        uri_prefix: str = "codegen://agents",
    ) -> None:
        super().__init__()
        self._agents_dir = Path(agents_dir)
        self._uri_prefix = uri_prefix.rstrip("/")

        if not self._agents_dir.is_dir():
            logger.warning(
                "Agents directory does not exist: %s", self._agents_dir
            )

    @property
    def agents_dir(self) -> Path:
        """Return the agents directory path."""
        return self._agents_dir

    def _scan_files(self) -> list[Path]:
        """Return sorted list of .md files in the agents directory."""
        if not self._agents_dir.is_dir():
            return []
        return sorted(self._agents_dir.glob("*.md"))

    async def _list_resources(self) -> Sequence[Resource]:
        """List all agent definition files as MCP resources."""
        resources: list[Resource] = []
        for path in self._scan_files():
            try:
                resource = self._file_to_resource(path)
                resources.append(resource)
            except Exception:
                logger.warning("Failed to load agent: %s", path.name, exc_info=True)
        logger.debug("AgentsProvider listed %d resources", len(resources))
        return resources

    def _file_to_resource(self, path: Path) -> TextResource:
        """Convert a single markdown file to a TextResource."""
        stem = path.stem
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)

        name = meta.get("name", stem)
        description = meta.get("description", f"Agent: {name}")
        uri = f"{self._uri_prefix}/{stem}"

        return TextResource(
            uri=uri,  # type: ignore[arg-type]
            name=f"agent_{stem.replace('-', '_')}",
            description=description,
            mime_type="text/markdown",
            text=body.strip(),
            tags={"agents", "task-tool"},
        )
