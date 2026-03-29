"""Tests for MemoryStorage TTL support and storage health checks."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from bridge.storage import FileStorage, MemoryStorage

# ── TTL basic behaviour ──────────────────────────────────


class TestMemoryStorageTTL:
    @pytest.fixture
    async def storage(self) -> MemoryStorage:
        s = MemoryStorage(ttl_seconds=60)
        await s.setup()
        return s

    async def test_get_returns_value_before_expiry(self, storage: MemoryStorage) -> None:
        await storage.put("k1", {"id": "k1", "data": "hello"})
        result = await storage.get("k1")
        assert result is not None
        assert result["data"] == "hello"

    async def test_get_returns_none_after_expiry(self) -> None:
        s = MemoryStorage(ttl_seconds=1)
        await s.setup()
        await s.put("k1", {"id": "k1"})

        # Simulate time passing beyond TTL
        with patch("bridge.storage.time") as mock_time:
            # First call to put used real time.monotonic(), so we need to
            # make the get() call see a time far in the future.
            mock_time.monotonic.return_value = 1e12  # far future
            result = await s.get("k1")
        assert result is None

    async def test_keys_excludes_expired(self) -> None:
        s = MemoryStorage(ttl_seconds=1)
        await s.setup()
        await s.put("fresh", {"id": "fresh"})
        await s.put("stale", {"id": "stale"})

        with patch("bridge.storage.time") as mock_time:
            mock_time.monotonic.return_value = 1e12
            keys = await s.keys()
        assert keys == []

    async def test_keys_keeps_non_expired(self, storage: MemoryStorage) -> None:
        await storage.put("a", {"id": "a"})
        await storage.put("b", {"id": "b"})
        keys = await storage.keys()
        assert sorted(keys) == ["a", "b"]

    async def test_put_overwrites_resets_ttl(self) -> None:
        s = MemoryStorage(ttl_seconds=100)
        await s.setup()
        await s.put("k", {"id": "k", "v": 1})

        # Overwrite — should get a fresh TTL
        await s.put("k", {"id": "k", "v": 2})
        result = await s.get("k")
        assert result is not None
        assert result["v"] == 2

    async def test_delete_removes_from_ttl_tracking(self, storage: MemoryStorage) -> None:
        await storage.put("k", {"id": "k"})
        await storage.delete("k")
        assert await storage.get("k") is None
        assert "k" not in await storage.keys()


# ── No TTL (backwards compatibility) ─────────────────────


class TestMemoryStorageNoTTL:
    @pytest.fixture
    async def storage(self) -> MemoryStorage:
        s = MemoryStorage()  # no ttl_seconds
        await s.setup()
        return s

    async def test_get_returns_value(self, storage: MemoryStorage) -> None:
        await storage.put("k1", {"id": "k1", "data": "hello"})
        result = await storage.get("k1")
        assert result is not None
        assert result["data"] == "hello"

    async def test_keys_returns_all(self, storage: MemoryStorage) -> None:
        await storage.put("a", {"id": "a"})
        await storage.put("b", {"id": "b"})
        keys = await storage.keys()
        assert sorted(keys) == ["a", "b"]

    async def test_data_never_expires(self, storage: MemoryStorage) -> None:
        await storage.put("persistent", {"id": "persistent"})
        # No TTL — value should always be available (via delegate store)
        result = await storage.get("persistent")
        assert result is not None


# ── Health checks ─────────────────────────────────────────


class TestMemoryStorageHealthCheck:
    async def test_healthy_after_setup(self) -> None:
        s = MemoryStorage()
        await s.setup()
        health = await s.health_check()
        assert health["backend"] == "memory"
        assert health["healthy"] is True
        assert health["key_count"] == 0
        assert health["ttl_seconds"] is None

    async def test_reports_ttl(self) -> None:
        s = MemoryStorage(ttl_seconds=300)
        await s.setup()
        health = await s.health_check()
        assert health["ttl_seconds"] == 300

    async def test_reports_key_count(self) -> None:
        s = MemoryStorage(ttl_seconds=60)
        await s.setup()
        await s.put("a", {"id": "a"})
        await s.put("b", {"id": "b"})
        health = await s.health_check()
        assert health["key_count"] == 2

    async def test_not_healthy_before_setup(self) -> None:
        s = MemoryStorage()
        health = await s.health_check()
        assert health["healthy"] is False


class TestFileStorageHealthCheck:
    async def test_healthy_after_setup(self, tmp_path: object) -> None:
        from pathlib import Path

        storage_dir = Path(str(tmp_path)) / "health"
        storage_dir.mkdir()
        s = FileStorage(storage_dir=storage_dir)
        await s.setup()
        health = await s.health_check()
        assert health["backend"] == "file"
        assert health["healthy"] is True
        assert health["key_count"] == 0
        assert health["storage_dir"] == str(storage_dir)

    async def test_reports_key_count(self, tmp_path: object) -> None:
        from pathlib import Path

        storage_dir = Path(str(tmp_path)) / "count"
        storage_dir.mkdir()
        s = FileStorage(storage_dir=storage_dir)
        await s.setup()
        await s.put("x", {"id": "x"})
        health = await s.health_check()
        assert health["key_count"] == 1
