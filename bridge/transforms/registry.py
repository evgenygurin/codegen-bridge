"""Transform registry — build and apply transforms to a FastMCP server.

Follows the same architectural pattern as :mod:`bridge.middleware.stack`:
a ``_build_chain`` function assembles enabled transforms in the correct
order, and :func:`configure_transforms` registers them on the server.

The public entry point is :func:`configure_transforms`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastmcp.server.transforms import (
    Namespace,
    ToolTransform,
    Transform,
    VersionFilter,
    Visibility,
)
from fastmcp.tools.tool_transform import ToolTransformConfig as _FMToolTransformConfig

from bridge.transforms.config import TransformsConfig

if TYPE_CHECKING:
    from fastmcp import FastMCP

logger = logging.getLogger("bridge.transforms")


def _build_chain(config: TransformsConfig) -> list[Transform]:
    """Instantiate enabled transforms in the correct chain order.

    Returns a list ordered innermost -> outermost (first-added is
    innermost, closest to providers).

    Order rationale:
    1. **Namespace** — prefixes names first, so all subsequent transforms
       reference the namespaced names.
    2. **ToolTransform** — rename/modify tools (using namespaced names).
    3. **Visibility** — show/hide after renames are applied.
    4. **VersionFilter** — final gating by version range.
    """
    chain: list[Transform] = []

    # 1. Namespace
    ns = config.namespace
    if ns is not None and ns.enabled:
        chain.append(Namespace(ns.prefix))

    # 2. Tool Transform
    tt = config.tool_transform
    if tt is not None and tt.enabled and tt.tools:
        tool_configs: dict[str, _FMToolTransformConfig] = {}
        for tool_name, entry in tt.tools.items():
            kwargs: dict[str, Any] = {}
            if entry.name is not None:
                kwargs["name"] = entry.name
            if entry.description is not None:
                kwargs["description"] = entry.description
            if entry.tags is not None:
                kwargs["tags"] = entry.tags
            kwargs["enabled"] = entry.enabled
            tool_configs[tool_name] = _FMToolTransformConfig(**kwargs)
        chain.append(ToolTransform(tool_configs))

    # 3. Visibility rules
    vis = config.visibility
    if vis is not None and vis.enabled:
        for rule in vis.rules:
            chain.append(
                Visibility(
                    enabled=rule.enabled,
                    names=rule.names,
                    tags=rule.tags,
                    components=rule.components,
                    match_all=rule.match_all,
                )
            )

    # 4. Version filter
    vf = config.version_filter
    if vf is not None and vf.enabled:
        chain.append(VersionFilter(version_gte=vf.version_gte, version_lt=vf.version_lt))

    return chain


def configure_transforms(
    server: FastMCP,
    config: TransformsConfig | None = None,
) -> list[Transform]:
    """Build and register the transform chain on *server*.

    Parameters
    ----------
    server:
        The FastMCP server instance to configure.
    config:
        Optional configuration; defaults to ``TransformsConfig()`` which
        applies no transforms (full passthrough).

    Returns
    -------
    list[Transform]
        The transform instances that were registered, in chain order.
        Useful for testing or post-registration inspection.
    """
    if config is None:
        config = TransformsConfig()

    chain = _build_chain(config)

    for transform in chain:
        server.add_transform(transform)

    if chain:
        labels = [type(t).__name__ for t in chain]
        logger.info("Transform chain configured: %s", " -> ".join(labels))
    else:
        logger.debug("No transforms configured (passthrough mode)")

    return chain
