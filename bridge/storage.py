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


# ── MemoryStorage ───────────────────────────────────────────


class MemoryStorage:
    """In-memory storage backed by ``key_value.aio.stores.memory.MemoryStore``.

    Supports full key enumeration.  Data is lost on process exit.
    """

    def __init__(self) -> None:
        self._store = MemoryStore()

    async def setup(self) -> None:
        await self._store.setup()
        logger.debug("MemoryStorage initialised")

    async def get(self, key: str) -> dict[str, Any] | None:
        return await self._store.get(key, collection=_COLLECTION)

    async def put(self, key: str, value: dict[str, Any]) -> None:
        await self._store.put(key, value, collection=_COLLECTION)

    async def delete(self, key: str) -> bool:
        return await self._store.delete(key, collection=_COLLECTION)

    async def keys(self) -> list[str]:
        return await self._store.keys(collection=_COLLECTION)


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
        return await self._store.get(key, collection=_COLLECTION)

    async def put(self, key: str, value: dict[str, Any]) -> None:
        await self._store.put(key, value, collection=_COLLECTION)
        self._key_index.add(key)

    async def delete(self, key: str) -> bool:
        result = await self._store.delete(key, collection=_COLLECTION)
        self._key_index.discard(key)
        return result

    async def keys(self) -> list[str]:
        return list(self._key_index)

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
