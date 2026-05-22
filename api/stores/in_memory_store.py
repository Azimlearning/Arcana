"""In-memory MemoryStore. Slice 1 implementation; process-scoped.

P1 §1.8 (accounts + persistence) swaps this for a Firestore-backed
impl. The ABC contract is identical; the swap is one settings flip
(see FR-USR-02 / FR-KG-07 pattern).
"""

from __future__ import annotations

from collections import defaultdict

from api.llm.types import Message
from api.stores.memory_store import MemoryStore


class InMemoryMemoryStore(MemoryStore):
    """Single-process chat-history store. Resets on restart."""

    def __init__(self) -> None:
        self._history: dict[str, list[Message]] = defaultdict(list)

    async def get_messages(self, notebook_id: str) -> list[Message]:
        return list(self._history.get(notebook_id, []))

    async def append_messages(
        self, notebook_id: str, messages: list[Message]
    ) -> None:
        if not messages:
            return
        self._history[notebook_id].extend(messages)

    async def clear(self, notebook_id: str) -> None:
        self._history.pop(notebook_id, None)

    async def aclose(self) -> None:
        return None
