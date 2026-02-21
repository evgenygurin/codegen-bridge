"""Cursor-based pagination helpers for MCP tool results.

Uses FastMCP's ``CursorState`` for opaque cursor encoding/decoding,
mapping cursors to ``skip`` offsets for the Codegen REST API.

Typical usage inside an MCP tool::

    offset = cursor_to_offset(cursor)
    page = await client.list_runs(skip=offset, limit=page_size)
    result = build_paginated_response(
        items=[...],
        total=page.total,
        offset=offset,
        page_size=page_size,
    )
"""

from __future__ import annotations

from typing import Any

from fastmcp.utilities.pagination import CursorState

# Default page size when none is specified by the caller.
DEFAULT_PAGE_SIZE = 20


def cursor_to_offset(cursor: str | None) -> int:
    """Decode an opaque cursor string into an integer offset.

    Args:
        cursor: Base64-encoded cursor from a previous response, or ``None``
            for the first page.

    Returns:
        Integer offset (``skip``) for the API call.  ``0`` when *cursor* is
        ``None``.

    Raises:
        ValueError: If *cursor* is non-``None`` but malformed.
    """
    if cursor is None:
        return 0
    return CursorState.decode(cursor).offset


def offset_to_cursor(offset: int) -> str:
    """Encode an integer offset into an opaque cursor string.

    Args:
        offset: The position in the result set for the next page.

    Returns:
        Base64-encoded cursor string.
    """
    return CursorState(offset=offset).encode()


def next_cursor_or_none(offset: int, page_size: int, total: int) -> str | None:
    """Return the cursor for the next page, or ``None`` if exhausted.

    Args:
        offset: Current page start offset.
        page_size: Number of items requested for this page.
        total: Total number of items reported by the API.

    Returns:
        Opaque cursor string when more pages exist, otherwise ``None``.
    """
    next_offset = offset + page_size
    if next_offset < total:
        return offset_to_cursor(next_offset)
    return None


def build_paginated_response(
    *,
    items: list[dict[str, Any]],
    total: int,
    offset: int,
    page_size: int,
    items_key: str = "items",
) -> dict[str, Any]:
    """Build a standardised paginated response dict for an MCP tool.

    The returned dict always contains:

    * ``<items_key>``: the page of items.
    * ``total``: total items available.
    * ``next_cursor``: opaque cursor for the next page, or ``null``.

    Args:
        items: Serialised items for the current page.
        total: Total items available across all pages.
        offset: Offset used for the current page.
        page_size: Page size used for the current page.
        items_key: Key under which items are placed (default ``"items"``).

    Returns:
        Dict ready to be serialised with ``json.dumps``.
    """
    return {
        items_key: items,
        "total": total,
        "next_cursor": next_cursor_or_none(offset, page_size, total),
    }
