"""JSONL-backed MemoryStore — persistent chat history (FR-USR-04).

One file per notebook: `{root}/{notebook_id}.jsonl`. Each line is a JSON
object `{"role": "user"|"assistant", "content": "..."}`. Appends on write;
full-file read on get (suitable for the FYP's notebook sizes).

Replaces InMemoryMemoryStore in main.py so history survives server restarts.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from api.core.logging import get_logger
from api.llm.types import Message
from api.stores.memory_store import MemoryStore

logger = get_logger(__name__)

_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


def _safe_id(notebook_id: str) -> str:
    """Sanitise notebook_id to a safe filename stem."""
    safe = "".join(c if c in _ID_CHARS else "_" for c in notebook_id)
    return (safe or "default")[:128]


class JsonlMemoryStore(MemoryStore):
    """Per-notebook JSONL chat history. Survives server restarts."""

    def __init__(self, *, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()

    def _path(self, notebook_id: str) -> Path:
        return self._root / f"{_safe_id(notebook_id)}.jsonl"

    async def _lock(self, notebook_id: str) -> asyncio.Lock:
        async with self._meta_lock:
            if notebook_id not in self._locks:
                self._locks[notebook_id] = asyncio.Lock()
        return self._locks[notebook_id]

    async def get_messages(self, notebook_id: str) -> list[Message]:
        path = self._path(notebook_id)
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            logger.warning("memory_store.read_failed", notebook_id=notebook_id)
            return []
        messages: list[Message] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                messages.append(Message(role=obj["role"], content=obj["content"]))
            except (json.JSONDecodeError, KeyError):
                continue
        return messages

    async def append_messages(self, notebook_id: str, messages: list[Message]) -> None:
        if not messages:
            return
        path = self._path(notebook_id)
        lines = "\n".join(
            json.dumps({"role": m.role, "content": m.content}, ensure_ascii=False)
            for m in messages
        ) + "\n"
        lock = await self._lock(notebook_id)
        async with lock:
            try:
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(lines)
            except OSError:
                logger.warning("memory_store.write_failed", notebook_id=notebook_id)

    async def clear(self, notebook_id: str) -> None:
        path = self._path(notebook_id)
        lock = await self._lock(notebook_id)
        async with lock:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("memory_store.clear_failed", notebook_id=notebook_id)

    async def aclose(self) -> None:
        return None
