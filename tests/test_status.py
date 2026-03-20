"""Tests for bridge.status — status normalization and terminal detection."""

from __future__ import annotations

import pytest

from bridge.status import TERMINAL_STATUSES, is_terminal, normalize_status

# ── normalize_status ────────────────────────────────────────────


class TestNormalizeStatus:
    """Verify that normalize_status handles all API variants."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # Lowercase canonical
            ("completed", "completed"),
            ("failed", "failed"),
            ("error", "error"),
            ("running", "running"),
            ("unknown", "unknown"),
            # Uppercase (API returns these)
            ("COMPLETED", "completed"),
            ("FAILED", "failed"),
            ("ERROR", "error"),
            ("RUNNING", "running"),
            # Alias: "complete" → "completed"
            ("complete", "completed"),
            ("COMPLETE", "completed"),
            ("Complete", "completed"),
            # Mixed case
            ("Completed", "completed"),
            ("Failed", "failed"),
            ("Error", "error"),
            # None → "unknown"
            (None, "unknown"),
        ],
    )
    def test_normalizes(self, raw: str | None, expected: str) -> None:
        assert normalize_status(raw) == expected

    def test_passthrough_unknown_status(self) -> None:
        """Unknown statuses are lowercased but not mapped."""
        assert normalize_status("PENDING") == "pending"
        assert normalize_status("queued") == "queued"


# ── is_terminal ─────────────────────────────────────────────────


class TestIsTerminal:
    """Verify terminal detection with various case/alias combinations."""

    @pytest.mark.parametrize(
        "status",
        [
            "completed",
            "COMPLETED",
            "COMPLETE",
            "complete",
            "failed",
            "FAILED",
            "error",
            "ERROR",
        ],
    )
    def test_terminal_statuses(self, status: str) -> None:
        assert is_terminal(status) is True

    @pytest.mark.parametrize(
        "status",
        [
            "running",
            "RUNNING",
            "pending",
            "queued",
            None,
        ],
    )
    def test_non_terminal_statuses(self, status: str | None) -> None:
        assert is_terminal(status) is False


# ── TERMINAL_STATUSES constant ──────────────────────────────────


def test_terminal_statuses_is_frozenset() -> None:
    assert isinstance(TERMINAL_STATUSES, frozenset)
    assert "completed" in TERMINAL_STATUSES
    assert "failed" in TERMINAL_STATUSES
    assert "error" in TERMINAL_STATUSES
