"""Custom provider that exposes slash-command markdown files as MCP resources.

Each ``.md`` file in the commands directory becomes an MCP resource with URI
``codegen://commands/{stem}``.  The YAML front-matter ``description`` field
(if present) is used as the resource description.

This follows the **Provider** pattern from FastMCP 3.x: a class that
implements ``_list_resources`` and optionally ``_get_resource`` to source
components from an arbitrary backend (in this case, a local directory).

Example directory layout::

    commands/
        codegen.md          -> codegen://commands/codegen
        cg-status.md        -> codegen://commands/cg-status
        cg-logs.md          -> codegen://commands/cg-logs
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from pathlib import Path

from fastmcp.resources import TextResource
from fastmcp.resources.resource import Resource
from fastmcp.server.providers import Provider

logger = logging.getLogger("bridge.providers.commands")

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


class CommandsProvider(Provider):
    """Provider that exposes markdown command files as MCP resources.

    Each ``.md`` file in *commands_dir* is exposed as a text resource.
    The resource URI follows the pattern ``codegen://commands/{name}``.

    Args:
        commands_dir: Path to the directory containing command markdown files.
        uri_prefix: URI scheme and authority prefix for generated resources.
    """

    def __init__(
        self,
        commands_dir: str | Path,
        *,
        uri_prefix: str = "codegen://commands",
    ) -> None:
        super().__init__()
        self._commands_dir = Path(commands_dir)
        self._uri_prefix = uri_prefix.rstrip("/")

        if not self._commands_dir.is_dir():
            logger.warning("Commands directory does not exist: %s", self._commands_dir)

    @property
    def commands_dir(self) -> Path:
        """Return the commands directory path."""
        return self._commands_dir

    def _scan_files(self) -> list[Path]:
        """Return sorted list of .md files in the commands directory."""
        if not self._commands_dir.is_dir():
            return []
        return sorted(self._commands_dir.glob("*.md"))

    async def _list_resources(self) -> Sequence[Resource]:
        """List all command files as MCP resources."""
        resources: list[Resource] = []
        for path in self._scan_files():
            try:
                resource = self._file_to_resource(path)
                resources.append(resource)
            except (OSError, ValueError, UnicodeDecodeError):
                logger.warning("Failed to load command: %s", path.name, exc_info=True)
        logger.debug("CommandsProvider listed %d resources", len(resources))
        return resources

    def _file_to_resource(self, path: Path) -> TextResource:
        """Convert a single markdown file to a TextResource."""
        stem = path.stem
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)

        description = meta.get("description", f"Slash command: /{stem}")
        uri = f"{self._uri_prefix}/{stem}"

        return TextResource(
            uri=uri,  # type: ignore[arg-type]
            name=f"command_{stem}",
            description=description,
            mime_type="text/markdown",
            text=body.strip(),
            tags={"commands", "slash-command"},
        )
