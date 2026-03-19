"""Remote Codegen MCP proxy provider.

Mounts the hosted Codegen MCP server (``https://mcp.codegen.com/mcp/``)
as a proxy, exposing its tools under a configurable namespace.  The
remote server is accessed via FastMCP's ``create_proxy()`` with bearer
token authentication derived from ``CODEGEN_API_KEY``.

Usage in the server lifespan::

    from bridge.providers.remote import create_remote_proxy

    proxy = create_remote_proxy(api_key=api_key)
    if proxy is not None:
        server.mount(proxy, namespace="remote")

The proxy is created lazily — if the remote URL is unreachable at
creation time no error is raised; individual tool calls will fail
gracefully when the remote server is unavailable.
"""

from __future__ import annotations

import logging
import os

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server import create_proxy
from fastmcp.server.providers.proxy import FastMCPProxy

logger = logging.getLogger("bridge.providers.remote")

DEFAULT_REMOTE_MCP_URL = "https://mcp.codegen.com/mcp/"


def create_remote_proxy(
    api_key: str,
    *,
    remote_url: str | None = None,
    namespace: str = "remote",
) -> FastMCPProxy | None:
    """Create a proxy to the remote Codegen MCP server.

    The proxy forwards tool/resource/prompt calls to the hosted Codegen
    MCP endpoint using bearer token authentication.

    Args:
        api_key: Codegen API key used as a bearer token.
        remote_url: Override the default remote MCP URL.  Falls back to
            ``CODEGEN_REMOTE_MCP_URL`` env var, then to
            ``https://mcp.codegen.com/mcp/``.
        namespace: Namespace prefix for mounted tools (unused here,
            passed by caller to ``server.mount()``).

    Returns:
        A configured ``FastMCPProxy`` ready to be mounted via
        ``server.mount(proxy, namespace=...)``, or ``None`` if
        the proxy could not be created (e.g. missing API key).
    """
    if not api_key:
        logger.warning("Cannot create remote proxy: no API key provided")
        return None

    url = remote_url or os.environ.get("CODEGEN_REMOTE_MCP_URL", DEFAULT_REMOTE_MCP_URL)
    logger.info("Creating remote MCP proxy: url=%s", url)

    try:
        transport = StreamableHttpTransport(url=url, auth=api_key)
        client = Client(transport=transport, auth=api_key)
        proxy = create_proxy(client, name=f"Codegen Remote ({namespace})")
        logger.info("Remote MCP proxy created successfully")
        return proxy
    except (ImportError, ValueError, OSError, ConnectionError, RuntimeError):
        logger.warning("Failed to create remote MCP proxy", exc_info=True)
        return None
