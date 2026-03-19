"""Storage backends for ContextRegistry persistence.

Provides a ``StorageBackend`` protocol and two concrete implementations
backed by `py-key-value-aio <https://github.com/strawgate/py-key-value>`_
(the storage layer used by FastMCP):

* **MemoryStorage** — in-memory store, ideal for tests and ephemeral sessions.
* **FileStorage** — filesystem-based store that survives restarts.

Both follow the Strategy pattern (GoF), injected into ``ContextRegistry``
at construction time so callers never depend on a concrete backend.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from key_value.aio.stores.filetree import (
    FileTreeStore,
    FileTreeV1CollectionSanitizationStrategy,
    FileTreeV1KeySanitizationStrategy,
)
from key_value.aio.stores.memory import MemoryStore

logger = logging.getLogger("bridge.storage")

# Collection name used for all execution contexts.
_COLLECTION = "executions"

# Key inside the value dict that holds the original key / id.
_ID_FIELD = "id"


# ── Protocol ────────────────────────────────────────────────


@runtime_checkable
class StorageBackend(Protocol):
    """Async key-value interface for ``ContextRegistry`` persistence.

    Implementations must support basic CRUD plus key enumeration so
    ``ContextRegistry`` can scan for active executions.
    """

    async def setup(self) -> None:
        """Perform any one-time initialisation (create dirs, etc.)."""
        ...

    async def get(self, key: str) -> dict[str, Any] | None:
        """Return the stored dict for *key*, or ``None``."""
        ...

    async def put(self, key: str, value: dict[str, Any]) -> None:
        """Persist *value* under *key*."""
        ...

    async def delete(self, key: str) -> bool:
        """Remove *key* and return whether it existed."""
        ...

    async def keys(self) -> list[str]:
        """Return all stored keys."""
        ...

    async def health_check(self) -> dict[str, Any]:
        """Return a health status dict for the storage backend."""
        ...


# ── MemoryStorage ───────────────────────────────────────────


class MemoryStorage:
    """In-memory storage with optional TTL-based expiry.

    Supports full key enumeration.  Data is lost on process exit.

    Parameters
    ----------
    ttl_seconds:
        When set, entries expire after this many seconds.  Expired entries
        are lazily evicted on ``get`` and ``keys`` calls.  ``None`` means
        entries never expire.
    """

    def __init__(self, ttl_seconds: int | None = None) -> None:
        self._ttl = ttl_seconds
        # When TTL is enabled we track expiry ourselves.
        # key -> (value, expire_time)  — expire_time is 0.0 when TTL is None.
        self._data: dict[str, tuple[dict[str, Any], float]] = {}
        self._store = MemoryStore()
        self._setup_done = False

    async def setup(self) -> None:
        await self._store.setup()
        self._setup_done = True
        logger.debug("MemoryStorage initialised (ttl=%s)", self._ttl)

    async def get(self, key: str) -> dict[str, Any] | None:
        if self._ttl is not None:
            entry = self._data.get(key)
            if entry is None:
                return None
            value, expire_at = entry
            if time.monotonic() >= expire_at:
                # Expired — evict
                self._data.pop(key, None)
                await self._store.delete(key, collection=_COLLECTION)
                return None
            return value

        result: dict[str, Any] | None = await self._store.get(key, collection=_COLLECTION)
        return result

    async def put(self, key: str, value: dict[str, Any]) -> None:
        await self._store.put(key, value, collection=_COLLECTION)
        if self._ttl is not None:
            expire_at = time.monotonic() + self._ttl
            self._data[key] = (value, expire_at)
        else:
            self._data[key] = (value, 0.0)

    async def delete(self, key: str) -> bool:
        self._data.pop(key, None)
        result: bool = await self._store.delete(key, collection=_COLLECTION)
        return result

    async def keys(self) -> list[str]:
        if self._ttl is not None:
            now = time.monotonic()
            expired = [k for k, (_, exp) in self._data.items() if now >= exp]
            for k in expired:
                self._data.pop(k, None)
                await self._store.delete(k, collection=_COLLECTION)
            return list(self._data.keys())

        result: list[str] = await self._store.keys(collection=_COLLECTION)
        return result

    async def health_check(self) -> dict[str, Any]:
        """Return health status of the in-memory storage."""
        key_count = len(self._data) if self._data else 0
        return {
            "backend": "memory",
            "healthy": self._setup_done,
            "key_count": key_count,
            "ttl_seconds": self._ttl,
        }


# ── FileStorage ─────────────────────────────────────────────


class FileStorage:
    """Filesystem storage backed by ``key_value.aio.stores.filetree.FileTreeStore``.

    Data persists across server restarts.  ``FileTreeStore`` does not natively
    support key enumeration and uses sanitised filenames, so this adapter
    maintains an in-memory key index that is rebuilt on startup by reading
    the ``id`` field from each persisted JSON file.
    """

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        if storage_dir is None:
            storage_dir = Path(".codegen-bridge") / "storage"
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._store = FileTreeStore(
            data_directory=self._storage_dir,
            key_sanitization_strategy=FileTreeV1KeySanitizationStrategy(self._storage_dir),
            collection_sanitization_strategy=FileTreeV1CollectionSanitizationStrategy(
                self._storage_dir
            ),
        )
        self._key_index: set[str] = set()

    async def setup(self) -> None:
        await self._store.setup()
        await self._rebuild_index()
        logger.debug(
            "FileStorage initialised: dir=%s, keys=%d",
            self._storage_dir,
            len(self._key_index),
        )

    async def get(self, key: str) -> dict[str, Any] | None:
        result: dict[str, Any] | None = await self._store.get(key, collection=_COLLECTION)
        return result

    async def put(self, key: str, value: dict[str, Any]) -> None:
        await self._store.put(key, value, collection=_COLLECTION)
        self._key_index.add(key)

    async def delete(self, key: str) -> bool:
        result: bool = await self._store.delete(key, collection=_COLLECTION)
        self._key_index.discard(key)
        return result

    async def keys(self) -> list[str]:
        return list(self._key_index)

    async def health_check(self) -> dict[str, Any]:
        """Return health status of the file storage."""
        dir_exists = self._storage_dir.exists()
        return {
            "backend": "file",
            "healthy": dir_exists,
            "key_count": len(self._key_index),
            "storage_dir": str(self._storage_dir),
        }

    # ── Internal ────────────────────────────────────────────

    async def _rebuild_index(self) -> None:
        """Scan the collection directory and read each JSON envelope to recover keys.

        ``FileTreeStore`` uses sanitised filenames so we cannot derive the
        original key from the path.  Instead we read each file's JSON
        envelope (``{"value": {...}, ...}``) and extract the ``id`` field
        from the stored value.
        """
        self._key_index.clear()
        collection_dir = self._storage_dir / _COLLECTION
        if not collection_dir.exists():
            return
        for child in collection_dir.iterdir():
            if not child.is_file() or child.suffix != ".json":
                continue
            try:
                envelope = json.loads(child.read_text())
                value = envelope.get("value", {})
                key = value.get(_ID_FIELD)
                if key is not None:
                    self._key_index.add(str(key))
            except (json.JSONDecodeError, OSError):
                logger.warning("Skipping unreadable storage file: %s", child.name)
