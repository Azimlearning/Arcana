"""JSONL-backed ChunkStore — slice-time implementation.

One line of JSON per chunk; appended on every `upsert_many`. Reads dedupe
by id (last write wins — upsert semantics). `delete_by_doc` rewrites the
file atomically.

Why a single file and not SQLite for the slice:
  - No new heavy dep, no schema migration story.
  - Trivial to inspect during the FYP defence (`cat chunks.jsonl | head`).
  - The full corpus for the slice's `ingest-demo` is small enough that a
    full-file scan per query (BM25's pattern) costs <100 ms.
P1 should swap to a paginated store when concurrent notebook writes land
(FR-USR-06).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from api.core.logging import get_logger
from api.stores.chunk_store import ChunkStore, StoredChunk
from api.stores.errors import StoreError

logger = get_logger(__name__)


class JsonlChunkStore(ChunkStore):
    def __init__(self, *, root: Path) -> None:
        self._path = root / "chunks.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = asyncio.Lock()

    async def upsert_many(self, chunks: list[StoredChunk]) -> None:
        if not chunks:
            return
        lines = [_encode(c) for c in chunks]
        async with self._write_lock:
            # Append-only: upsert semantics enforced at read-time (dedupe by id).
            with self._path.open("a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")

    async def get(self, chunk_id: str) -> StoredChunk | None:
        for c in await self.list_all():
            if c.id == chunk_id:
                return c
        return None

    async def list_all(self) -> list[StoredChunk]:
        if not self._path.exists():
            return []
        # Dedupe by id, keeping LAST occurrence (so re-ingest of an
        # updated doc reflects the new text rather than the stale one).
        seen: dict[str, StoredChunk] = {}
        try:
            content = self._path.read_text(encoding="utf-8")
        except OSError as e:
            raise StoreError(f"cannot read chunks.jsonl: {e}") from e
        # Surface corrupt rows in logs — silent skip would otherwise shrink the
        # retrieval corpus unseen, which the benchmark (R-02) can't detect.
        corrupt_count = 0
        for line_no, line in enumerate(content.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                corrupt_count += 1
                logger.warning(
                    "chunk_store.corrupt_json",
                    path=str(self._path),
                    line_no=line_no,
                )
                continue
            try:
                chunk = StoredChunk(**data)
            except TypeError:
                corrupt_count += 1
                logger.warning(
                    "chunk_store.schema_drift",
                    path=str(self._path),
                    line_no=line_no,
                )
                continue
            seen[chunk.id] = chunk
        if corrupt_count:
            logger.info(
                "chunk_store.corrupt_summary",
                path=str(self._path),
                corrupt=corrupt_count,
                kept=len(seen),
            )
        return list(seen.values())

    async def delete_by_doc(self, doc_id: str) -> int:
        async with self._write_lock:
            existing = await self.list_all()
            keep = [c for c in existing if c.doc_id != doc_id]
            count = len(existing) - len(keep)
            if count == 0:
                return 0
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(
                "\n".join(_encode(c) for c in keep) + ("\n" if keep else ""),
                encoding="utf-8",
            )
            os.replace(tmp, self._path)
            return count

    async def aclose(self) -> None:
        return None


def _encode(c: StoredChunk) -> str:
    return json.dumps(
        {
            "id": c.id,
            "doc_id": c.doc_id,
            "text": c.text,
            "page": c.page,
            "char_offset": c.char_offset,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
