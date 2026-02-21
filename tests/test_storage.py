"""Tests for storage backends (MemoryStorage, FileStorage)."""

from __future__ import annotations

import pytest

from bridge.storage import FileStorage, MemoryStorage, StorageBackend


class TestStorageBackendProtocol:
    def test_memory_storage_is_storage_backend(self):
        assert isinstance(MemoryStorage(), StorageBackend)

    def test_file_storage_is_storage_backend(self, tmp_path):
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        assert isinstance(FileStorage(storage_dir=storage_dir), StorageBackend)


class _SharedStorageTests:
    """Shared test suite exercised by both MemoryStorage and FileStorage."""

    async def test_put_and_get(self, storage):
        await storage.put("k1", {"id": "k1", "data": "hello"})
        result = await storage.get("k1")
        assert result is not None
        assert result["id"] == "k1"
        assert result["data"] == "hello"

    async def test_get_missing_key_returns_none(self, storage):
        assert await storage.get("nonexistent") is None

    async def test_delete_existing_key(self, storage):
        await storage.put("del-me", {"id": "del-me"})
        deleted = await storage.delete("del-me")
        assert deleted is True
        assert await storage.get("del-me") is None

    async def test_delete_missing_key_returns_false(self, storage):
        deleted = await storage.delete("nope")
        assert deleted is False

    async def test_keys_empty_initially(self, storage):
        assert await storage.keys() == []

    async def test_keys_returns_stored_keys(self, storage):
        await storage.put("a", {"id": "a"})
        await storage.put("b", {"id": "b"})
        keys = await storage.keys()
        assert sorted(keys) == ["a", "b"]

    async def test_keys_updated_after_delete(self, storage):
        await storage.put("x", {"id": "x"})
        await storage.put("y", {"id": "y"})
        await storage.delete("x")
        keys = await storage.keys()
        assert keys == ["y"]

    async def test_put_overwrites_existing(self, storage):
        await storage.put("k", {"id": "k", "v": 1})
        await storage.put("k", {"id": "k", "v": 2})
        result = await storage.get("k")
        assert result["v"] == 2


class TestMemoryStorage(_SharedStorageTests):
    @pytest.fixture
    async def storage(self):
        s = MemoryStorage()
        await s.setup()
        return s


class TestFileStorage(_SharedStorageTests):
    @pytest.fixture
    async def storage(self, tmp_path):
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        s = FileStorage(storage_dir=storage_dir)
        await s.setup()
        return s

    async def test_rebuild_index_on_new_instance(self, tmp_path):
        """A fresh FileStorage should discover keys persisted by a previous instance."""
        storage_dir = tmp_path / "rebuild"
        storage_dir.mkdir()

        s1 = FileStorage(storage_dir=storage_dir)
        await s1.setup()
        await s1.put("persistent-key", {"id": "persistent-key", "data": "survives"})

        # New instance pointing to the same directory
        s2 = FileStorage(storage_dir=storage_dir)
        await s2.setup()
        keys = await s2.keys()
        assert "persistent-key" in keys
        result = await s2.get("persistent-key")
        assert result is not None
        assert result["data"] == "survives"

    async def test_rebuild_index_empty_dir(self, tmp_path):
        """Rebuilding from an empty directory should produce no keys."""
        storage_dir = tmp_path / "empty"
        storage_dir.mkdir()
        s = FileStorage(storage_dir=storage_dir)
        await s.setup()
        assert await s.keys() == []
