"""Tests for cursor-based pagination helpers."""

from __future__ import annotations

import pytest

from bridge.helpers.pagination import (
    DEFAULT_PAGE_SIZE,
    build_paginated_response,
    cursor_to_offset,
    next_cursor_or_none,
    offset_to_cursor,
)

# ── cursor_to_offset / offset_to_cursor round-trip ───────


class TestCursorRoundTrip:
    def test_none_cursor_returns_zero(self):
        assert cursor_to_offset(None) == 0

    def test_round_trip_preserves_offset(self):
        for offset in (0, 1, 10, 100, 9999):
            encoded = offset_to_cursor(offset)
            assert cursor_to_offset(encoded) == offset

    def test_cursor_is_opaque_string(self):
        encoded = offset_to_cursor(42)
        assert isinstance(encoded, str)
        assert len(encoded) > 0
        # Should be base64-ish — no obvious integer in it
        assert "42" not in encoded or len(encoded) > 4

    def test_invalid_cursor_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid cursor"):
            cursor_to_offset("not-a-valid-cursor!!!")

    def test_empty_string_raises_value_error(self):
        with pytest.raises((ValueError, Exception)):
            cursor_to_offset("")


# ── next_cursor_or_none ──────────────────────────────────


class TestNextCursorOrNone:
    def test_returns_none_when_no_more_pages(self):
        # offset=0, page_size=10, total=5 → no more
        assert next_cursor_or_none(0, 10, 5) is None

    def test_returns_none_when_exactly_at_end(self):
        # offset=0, page_size=10, total=10 → exactly at end
        assert next_cursor_or_none(0, 10, 10) is None

    def test_returns_cursor_when_more_pages(self):
        # offset=0, page_size=10, total=25 → more exist
        result = next_cursor_or_none(0, 10, 25)
        assert result is not None
        assert cursor_to_offset(result) == 10

    def test_second_page_cursor(self):
        # offset=10, page_size=10, total=25 → still more
        result = next_cursor_or_none(10, 10, 25)
        assert result is not None
        assert cursor_to_offset(result) == 20

    def test_last_page_returns_none(self):
        # offset=20, page_size=10, total=25 → no more
        assert next_cursor_or_none(20, 10, 25) is None

    def test_single_item_total(self):
        assert next_cursor_or_none(0, 10, 1) is None

    def test_zero_total(self):
        assert next_cursor_or_none(0, 10, 0) is None


# ── build_paginated_response ─────────────────────────────


class TestBuildPaginatedResponse:
    def test_first_page_with_more(self):
        result = build_paginated_response(
            items=[{"id": 1}, {"id": 2}],
            total=5,
            offset=0,
            page_size=2,
        )
        assert result["items"] == [{"id": 1}, {"id": 2}]
        assert result["total"] == 5
        assert result["next_cursor"] is not None
        assert cursor_to_offset(result["next_cursor"]) == 2

    def test_last_page_no_cursor(self):
        result = build_paginated_response(
            items=[{"id": 5}],
            total=5,
            offset=4,
            page_size=2,
        )
        assert result["items"] == [{"id": 5}]
        assert result["total"] == 5
        assert result["next_cursor"] is None

    def test_custom_items_key(self):
        result = build_paginated_response(
            items=[{"name": "repo1"}],
            total=1,
            offset=0,
            page_size=10,
            items_key="repos",
        )
        assert "repos" in result
        assert "items" not in result
        assert result["repos"] == [{"name": "repo1"}]

    def test_empty_items(self):
        result = build_paginated_response(
            items=[],
            total=0,
            offset=0,
            page_size=10,
        )
        assert result["items"] == []
        assert result["total"] == 0
        assert result["next_cursor"] is None

    def test_full_page_walkthrough(self):
        """Walk through multiple pages to verify cursors chain correctly."""
        total = 5
        page_size = 2
        all_items = [{"id": i} for i in range(total)]

        # Page 1
        offset = 0
        page1 = build_paginated_response(
            items=all_items[offset : offset + page_size],
            total=total,
            offset=offset,
            page_size=page_size,
        )
        assert len(page1["items"]) == 2
        assert page1["next_cursor"] is not None

        # Page 2
        offset = cursor_to_offset(page1["next_cursor"])
        assert offset == 2
        page2 = build_paginated_response(
            items=all_items[offset : offset + page_size],
            total=total,
            offset=offset,
            page_size=page_size,
        )
        assert len(page2["items"]) == 2
        assert page2["next_cursor"] is not None

        # Page 3 (last)
        offset = cursor_to_offset(page2["next_cursor"])
        assert offset == 4
        page3 = build_paginated_response(
            items=all_items[offset : offset + page_size],
            total=total,
            offset=offset,
            page_size=page_size,
        )
        assert len(page3["items"]) == 1
        assert page3["next_cursor"] is None


# ── DEFAULT_PAGE_SIZE ────────────────────────────────────


class TestDefaultPageSize:
    def test_default_is_reasonable(self):
        assert DEFAULT_PAGE_SIZE > 0
        assert DEFAULT_PAGE_SIZE <= 100
