"""Internal ingestion types — backend-only.

`Chunk` here is the *internal* representation (carries `char_offset` for
chunk-id derivation). The wire-visible `Chunk` in `packages/schema/` is
strictly smaller and is only used if we ever expose chunks to the frontend.

Chunk-id strategy (production-shape):
  - Format: `{doc_id}_c_{sha256(doc_id|page|char_offset|text)[:16]}`
  - Same PDF + same chunker config → same ids (idempotent re-ingest).
  - Any text edit → new id; the stale vector is naturally orphaned and
    can be cleaned by a doc-prefix sweep.
  - Position baked into the hash disambiguates identical paragraphs
    within one doc (the slice's only failure mode for content-only hashes).
  - Doc-scoped prefix preserves provenance — identical chunks across two
    PDFs get different ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class PageText:
    page: int
    text: str


@dataclass(frozen=True, slots=True)
class Chunk:
    id: str
    doc_id: str
    text: str
    page: int
    char_offset: int


def make_chunk_id(*, doc_id: str, page: int, char_offset: int, text: str) -> str:
    """Deterministic per-doc content-addressable id. See module docstring."""
    payload = f"{doc_id}|{page}|{char_offset}|{text}".encode()
    digest = sha256(payload).hexdigest()[:16]
    return f"{doc_id}_c_{digest}"
