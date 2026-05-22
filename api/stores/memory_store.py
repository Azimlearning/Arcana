"""MemoryStore - per-notebook chat history. PRD §12 Memory Agent.

The Memory Agent's storage seam. Slice 1 ships an in-memory implementation
(process-scoped, lost on restart) under `in_memory_store.py`; the
Firestore-backed version arrives in P1 §1.8 with accounts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from api.llm.types import Message


class MemoryStore(ABC):
    """Async ABC for per-notebook chat history persistence."""

    @abstractmethod
    async def get_messages(self, notebook_id: str) -> list[Message]:
        """Return all messages stored under `notebook_id`, in original
        chronological order. Empty list for an unknown notebook."""

    @abstractmethod
    async def append_messages(
        self, notebook_id: str, messages: list[Message]
    ) -> None:
        """Append messages to the notebook's history. No-op for empty input."""

    @abstractmethod
    async def clear(self, notebook_id: str) -> None:
        """Drop all history for a notebook. Used by tests + future
        'clear conversation' UX."""

    @abstractmethod
    async def aclose(self) -> None: ...
