"""Tests for BackgroundTaskManager (bridge/monitoring.py).

Validates:
- MonitorRecord creation and serialisation
- BackgroundTaskManager lifecycle: create, update, fail, query
- Cleanup of completed monitors
- Constants are within safe ranges
"""

from __future__ import annotations

from bridge.monitoring import (
    DEFAULT_MAX_DURATION,
    DEFAULT_POLL_INTERVAL,
    MAX_DURATION_LIMIT,
    MAX_POLL_INTERVAL,
    MIN_DURATION,
    MIN_POLL_INTERVAL,
    TERMINAL_STATUSES,
    BackgroundTaskManager,
    MonitorRecord,
)

# ── Constants ────────────────────────────────────────────


class TestConstants:
    def test_terminal_statuses_is_frozenset(self):
        assert isinstance(TERMINAL_STATUSES, frozenset)

    def test_terminal_statuses_contains_completed(self):
        assert "completed" in TERMINAL_STATUSES

    def test_terminal_statuses_contains_failed(self):
        assert "failed" in TERMINAL_STATUSES

    def test_terminal_statuses_contains_cancelled(self):
        assert "cancelled" in TERMINAL_STATUSES

    def test_terminal_statuses_contains_stopped(self):
        assert "stopped" in TERMINAL_STATUSES

    def test_terminal_statuses_running_not_terminal(self):
        assert "running" not in TERMINAL_STATUSES

    def test_terminal_statuses_queued_not_terminal(self):
        assert "queued" not in TERMINAL_STATUSES

    def test_default_poll_interval_reasonable(self):
        assert MIN_POLL_INTERVAL <= DEFAULT_POLL_INTERVAL <= MAX_POLL_INTERVAL

    def test_default_max_duration_reasonable(self):
        assert MIN_DURATION <= DEFAULT_MAX_DURATION <= MAX_DURATION_LIMIT

    def test_min_poll_interval_positive(self):
        assert MIN_POLL_INTERVAL > 0

    def test_max_duration_limit_ten_minutes(self):
        assert MAX_DURATION_LIMIT == 600


# ── MonitorRecord ─────────────────────────────────────────


class TestMonitorRecord:
    def test_to_dict_includes_all_fields(self):
        record = MonitorRecord(
            monitor_id="abc123",
            run_id=42,
            started_at="2025-01-01T00:00:00",
        )
        d = record.to_dict()
        assert d["monitor_id"] == "abc123"
        assert d["run_id"] == 42
        assert d["started_at"] == "2025-01-01T00:00:00"
        assert d["active"] is True
        assert d["poll_count"] == 0
        assert d["last_status"] is None
        assert d["error"] is None

    def test_to_dict_active_false_when_terminal(self):
        record = MonitorRecord(
            monitor_id="xyz",
            run_id=1,
            started_at="2025-01-01T00:00:00",
            terminal=True,
        )
        assert record.to_dict()["active"] is False

    def test_default_values(self):
        record = MonitorRecord(
            monitor_id="test",
            run_id=10,
            started_at="2025-01-01T00:00:00",
        )
        assert record.last_polled_at is None
        assert record.last_status is None
        assert record.poll_count == 0
        assert record.terminal is False
        assert record.final_result is None
        assert record.error is None


# ── BackgroundTaskManager ─────────────────────────────────


class TestBackgroundTaskManager:
    def test_create_monitor_returns_record(self):
        mgr = BackgroundTaskManager()
        record = mgr.create_monitor(run_id=42)
        assert isinstance(record, MonitorRecord)
        assert record.run_id == 42
        assert record.terminal is False

    def test_create_monitor_generates_unique_ids(self):
        mgr = BackgroundTaskManager()
        r1 = mgr.create_monitor(run_id=1)
        r2 = mgr.create_monitor(run_id=2)
        assert r1.monitor_id != r2.monitor_id

    def test_create_monitor_sets_started_at(self):
        mgr = BackgroundTaskManager()
        record = mgr.create_monitor(run_id=10)
        assert record.started_at is not None
        assert len(record.started_at) > 0

    def test_get_monitor_returns_created(self):
        mgr = BackgroundTaskManager()
        record = mgr.create_monitor(run_id=5)
        found = mgr.get_monitor(record.monitor_id)
        assert found is record

    def test_get_monitor_returns_none_for_missing(self):
        mgr = BackgroundTaskManager()
        assert mgr.get_monitor("nonexistent") is None

    def test_update_monitor_changes_status(self):
        mgr = BackgroundTaskManager()
        record = mgr.create_monitor(run_id=1)
        mgr.update_monitor(record.monitor_id, status="running")
        assert record.last_status == "running"
        assert record.poll_count == 1

    def test_update_monitor_increments_poll_count(self):
        mgr = BackgroundTaskManager()
        record = mgr.create_monitor(run_id=1)
        mgr.update_monitor(record.monitor_id, status="running")
        mgr.update_monitor(record.monitor_id, status="running")
        mgr.update_monitor(record.monitor_id, status="running")
        assert record.poll_count == 3

    def test_update_monitor_sets_terminal(self):
        mgr = BackgroundTaskManager()
        record = mgr.create_monitor(run_id=1)
        mgr.update_monitor(
            record.monitor_id,
            status="completed",
            terminal=True,
            result={"id": 1, "status": "completed"},
        )
        assert record.terminal is True
        assert record.final_result == {"id": 1, "status": "completed"}

    def test_update_monitor_sets_last_polled_at(self):
        mgr = BackgroundTaskManager()
        record = mgr.create_monitor(run_id=1)
        assert record.last_polled_at is None
        mgr.update_monitor(record.monitor_id, status="running")
        assert record.last_polled_at is not None

    def test_update_monitor_ignores_missing_id(self):
        mgr = BackgroundTaskManager()
        # Should not raise
        mgr.update_monitor("nonexistent", status="running")

    def test_fail_monitor_sets_terminal_and_error(self):
        mgr = BackgroundTaskManager()
        record = mgr.create_monitor(run_id=1)
        mgr.fail_monitor(record.monitor_id, "Connection timeout")
        assert record.terminal is True
        assert record.error == "Connection timeout"

    def test_fail_monitor_ignores_missing_id(self):
        mgr = BackgroundTaskManager()
        # Should not raise
        mgr.fail_monitor("nonexistent", "Error")

    def test_list_monitors_returns_all(self):
        mgr = BackgroundTaskManager()
        mgr.create_monitor(run_id=1)
        mgr.create_monitor(run_id=2)
        mgr.create_monitor(run_id=3)
        records = mgr.list_monitors()
        assert len(records) == 3

    def test_list_monitors_active_only(self):
        mgr = BackgroundTaskManager()
        r1 = mgr.create_monitor(run_id=1)
        mgr.create_monitor(run_id=2)
        mgr.update_monitor(r1.monitor_id, status="completed", terminal=True)

        active = mgr.list_monitors(active_only=True)
        assert len(active) == 1
        assert active[0].run_id == 2

    def test_list_monitors_empty(self):
        mgr = BackgroundTaskManager()
        assert mgr.list_monitors() == []

    def test_get_monitors_for_run(self):
        mgr = BackgroundTaskManager()
        mgr.create_monitor(run_id=42)
        mgr.create_monitor(run_id=42)
        mgr.create_monitor(run_id=99)

        run_42 = mgr.get_monitors_for_run(42)
        assert len(run_42) == 2
        assert all(r.run_id == 42 for r in run_42)

    def test_get_monitors_for_run_empty(self):
        mgr = BackgroundTaskManager()
        mgr.create_monitor(run_id=1)
        assert mgr.get_monitors_for_run(999) == []

    def test_clear_completed_removes_terminal(self):
        mgr = BackgroundTaskManager()
        r1 = mgr.create_monitor(run_id=1)
        mgr.create_monitor(run_id=2)
        r3 = mgr.create_monitor(run_id=3)
        mgr.update_monitor(r1.monitor_id, status="completed", terminal=True)
        mgr.update_monitor(r3.monitor_id, status="failed", terminal=True)

        removed = mgr.clear_completed()
        assert removed == 2
        assert len(mgr.list_monitors()) == 1

    def test_clear_completed_returns_zero_when_none(self):
        mgr = BackgroundTaskManager()
        mgr.create_monitor(run_id=1)
        assert mgr.clear_completed() == 0

    def test_clear_completed_on_empty_manager(self):
        mgr = BackgroundTaskManager()
        assert mgr.clear_completed() == 0
