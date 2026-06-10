"""Per-user NetworkXGraphStore pool — FR-KG-02.

Each user's knowledge graph is stored at `{root}/{uid}.json` (JSON
node-link format, same as the single-graph prototype).  The registry
lazily loads graphs on first access and keeps them in-process for the
lifetime of the server.  `save(uid)` flushes a single user's graph;
`save_all()` flushes every loaded graph (called from the lifespan
shutdown hook).

Thread safety: a per-uid asyncio.Lock prevents a race where two
concurrent requests for the same new uid would both try to initialise
the store from disk.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from api.stores.networkx_store import NetworkXGraphStore


class UserGraphRegistry:
    """Lazy in-process pool of per-user NetworkXGraphStore instances."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._stores: dict[str, NetworkXGraphStore] = {}
        self._init_locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()

    async def get_or_create(self, uid: str) -> NetworkXGraphStore:
        """Return the store for *uid*, creating/loading it if needed."""
        if uid in self._stores:
            return self._stores[uid]

        async with self._meta_lock:
            if uid not in self._init_locks:
                self._init_locks[uid] = asyncio.Lock()

        async with self._init_locks[uid]:
            if uid not in self._stores:
                self._root.mkdir(parents=True, exist_ok=True)
                path = self._root / f"{uid}.json"
                self._stores[uid] = NetworkXGraphStore(persist_path=path)

        return self._stores[uid]

    def get_if_loaded(self, uid: str) -> NetworkXGraphStore | None:
        """Return the store for *uid* only if already in memory, else None."""
        return self._stores.get(uid)

    async def save(self, uid: str) -> None:
        """Flush the graph for *uid* to disk. No-op if not loaded."""
        store = self._stores.get(uid)
        if store is not None:
            store.save()

    async def save_all(self) -> None:
        """Flush every loaded graph to disk (call on shutdown)."""
        for store in self._stores.values():
            store.save()
