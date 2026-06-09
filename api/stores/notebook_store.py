"""NotebookStore abstraction — FR-USR-03, FR-USR-06.

Notebooks are the top-level workspace owned by a user. Each notebook has its
own isolated document collection (per-user isolation — FR-USR-06).

ABC:
  NotebookStore  — interface; implementations swap without changing callers.

Concrete impls:
  JsonlNotebookStore — JSONL file per user under ``data/notebooks/``.
                       Suitable for local dev and demo. Firestore impl in P2.

Per-user isolation is enforced by keying every operation on ``user_id``.
An implementation MUST NOT let one user read or mutate another user's data.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ── Domain object ─────────────────────────────────────────────────────────────


class Notebook:
    __slots__ = ("created_at", "doc_count", "id", "title", "updated_at", "user_id")

    def __init__(
        self,
        *,
        id: str,
        user_id: str,
        title: str,
        created_at: str,
        updated_at: str,
        doc_count: int = 0,
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.title = title
        self.created_at = created_at
        self.updated_at = updated_at
        self.doc_count = doc_count

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "userId": self.user_id,
            "title": self.title,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "docCount": self.doc_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Notebook:
        return cls(
            id=d["id"],
            user_id=d["userId"],
            title=d["title"],
            created_at=d["createdAt"],
            updated_at=d["updatedAt"],
            doc_count=int(d.get("docCount", 0)),
        )


# ── Abstract interface ────────────────────────────────────────────────────────


class NotebookStore(ABC):
    """Storage abstraction for user notebook workspaces."""

    @abstractmethod
    async def create(self, *, user_id: str, title: str) -> Notebook:
        """Create and persist a new notebook; return it."""

    @abstractmethod
    async def list(self, user_id: str) -> list[Notebook]:
        """Return all notebooks owned by ``user_id``, ordered by updatedAt desc."""

    @abstractmethod
    async def get(self, *, user_id: str, notebook_id: str) -> Notebook | None:
        """Return the notebook if it exists and is owned by ``user_id``."""

    @abstractmethod
    async def delete(self, *, user_id: str, notebook_id: str) -> bool:
        """Delete the notebook. Returns True if deleted, False if not found."""

    @abstractmethod
    async def increment_doc_count(self, *, user_id: str, notebook_id: str) -> None:
        """Increment doc_count after a successful ingest into this notebook."""

    @abstractmethod
    async def aclose(self) -> None:
        """Release any held resources."""


# ── JSONL implementation ──────────────────────────────────────────────────────


class JsonlNotebookStore(NotebookStore):
    """Appends-only JSONL store, one file per user: ``{root}/{user_id}.jsonl``.

    Each line is a JSON object representing a notebook record.  On read, the
    file is scanned linearly (suitable for up to ~1 000 notebooks per user).
    Soft-delete: deletions write a tombstone record ``{"_del": id}``.
    """

    def __init__(self, root: Path | str = "data/notebooks") -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str) -> Path:
        # Sanitise user_id to prevent path traversal.
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in user_id)
        return self._root / f"{safe}.jsonl"

    async def _load(self, user_id: str) -> dict[str, Notebook]:
        """Read all non-deleted notebooks for this user into a dict by id."""
        path = self._path(user_id)
        if not path.exists():
            return {}

        notebooks: dict[str, Notebook] = {}
        deleted: set[str] = set()

        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if "_del" in record:
                deleted.add(str(record["_del"]))
            else:
                nb = Notebook.from_dict(record)
                notebooks[nb.id] = nb

        # Remove tombstoned entries.
        for del_id in deleted:
            notebooks.pop(del_id, None)

        return notebooks

    def _append(self, user_id: str, record: dict) -> None:
        path = self._path(user_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    async def create(self, *, user_id: str, title: str) -> Notebook:
        now = _now_iso()
        nb = Notebook(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title[:200].strip() or "Untitled",
            created_at=now,
            updated_at=now,
            doc_count=0,
        )
        self._append(user_id, nb.to_dict())
        return nb

    async def list(self, user_id: str) -> list[Notebook]:
        notebooks = await self._load(user_id)
        return sorted(
            notebooks.values(),
            key=lambda nb: nb.updated_at,
            reverse=True,
        )

    async def get(self, *, user_id: str, notebook_id: str) -> Notebook | None:
        notebooks = await self._load(user_id)
        return notebooks.get(notebook_id)

    async def delete(self, *, user_id: str, notebook_id: str) -> bool:
        notebooks = await self._load(user_id)
        if notebook_id not in notebooks:
            return False
        self._append(user_id, {"_del": notebook_id})
        return True

    async def increment_doc_count(self, *, user_id: str, notebook_id: str) -> None:
        notebooks = await self._load(user_id)
        nb = notebooks.get(notebook_id)
        if nb is None:
            return
        updated = Notebook(
            id=nb.id,
            user_id=nb.user_id,
            title=nb.title,
            created_at=nb.created_at,
            updated_at=_now_iso(),
            doc_count=nb.doc_count + 1,
        )
        # Write updated record; _load always uses the last version for each id.
        self._append(user_id, updated.to_dict())

    async def aclose(self) -> None:
        pass  # no persistent connection to close
