"""Ingestion pipeline — PDF → chunks → embeddings → vectors → ready.

Slice scope (per the slice ADR): no entity extraction, no graph build.
The graph store is left empty until the next slice; `retrieval/graph.py`
will return empty for every query. Vector + BM25 alone power the slice's
`CitedSummary`.

Status state machine:
    pending → parsing → embedding → ready
    any → failed (on uncaught exception, with status update)
"""

from __future__ import annotations

from api.core.errors import IngestFailed
from api.core.logging import get_logger
from api.embeddings.service import EmbedderProtocol
from api.ingestion.chunker import chunk as chunk_pages
from api.ingestion.parsers import pdf
from api.ingestion.stores_bundle import Stores
from api.ingestion.types import Chunk
from api.stores.chunk_store import StoredChunk
from api.stores.doc_store import DocMetadata
from api.stores.vector_store import VectorItem

logger = get_logger(__name__)


async def ingest_pdf(
    *,
    doc_id: str,
    raw: bytes,
    title: str,
    source_uri: str,
    stores: Stores,
    embedder: EmbedderProtocol,
) -> DocMetadata:
    """End-to-end ingest of a single PDF. Returns final DocMetadata.

    Raises `IngestFailed` (FR-ING-08) if any stage fails after the
    initial DocStore.put — and the doc's status is updated to `failed`
    so a UI/replay path can show the cause.
    """
    meta = await stores.doc.put(
        doc_id,
        raw,
        content_type="application/pdf",
        title=title,
        source_uri=source_uri,
        ingest_status="parsing",
    )
    logger.info("ingest.start", doc_id=doc_id, bytes=len(raw), title=title)

    try:
        pages = pdf.parse(raw)
        if not any(p.text.strip() for p in pages):
            raise IngestFailed(
                "PDF parsed to zero text — likely scanned. OCR (FR-ING-04) is P1.",
                details={"doc_id": doc_id, "page_count": len(pages)},
            )

        chunks: list[Chunk] = chunk_pages(pages, doc_id=doc_id)
        if not chunks:
            raise IngestFailed("chunker produced zero chunks", details={"doc_id": doc_id})

        await stores.doc.update_status(doc_id, "embedding")
        logger.info("ingest.chunked", doc_id=doc_id, chunks=len(chunks), pages=len(pages))

        vectors = await embedder.embed([c.text for c in chunks])
        if len(vectors) != len(chunks):
            raise IngestFailed(
                f"embedder returned {len(vectors)} vectors for {len(chunks)} chunks",
                details={"doc_id": doc_id},
            )

        await stores.vector.upsert(
            [
                VectorItem(
                    id=c.id,
                    vector=v,
                    metadata={
                        "doc_id": c.doc_id,
                        "page": c.page,
                        "char_offset": c.char_offset,
                        # text in metadata = no second store call to render citations
                        "text": c.text,
                    },
                )
                for c, v in zip(chunks, vectors, strict=True)
            ]
        )
        # BM25 indexes from the ChunkStore — write in lock-step with the vector store.
        await stores.chunks.upsert_many([
            StoredChunk(
                id=c.id,
                doc_id=c.doc_id,
                text=c.text,
                page=c.page,
                char_offset=c.char_offset,
            )
            for c in chunks
        ])
        meta = await stores.doc.update_status(doc_id, "ready")
        logger.info("ingest.ready", doc_id=doc_id, vectors=len(vectors))
        return meta

    except IngestFailed:
        await _mark_failed(stores, doc_id)
        raise
    except Exception as e:
        await _mark_failed(stores, doc_id)
        logger.exception("ingest.unhandled", doc_id=doc_id)
        raise IngestFailed(f"unhandled error during ingest: {e}") from e


async def _mark_failed(stores: Stores, doc_id: str) -> None:
    try:
        await stores.doc.update_status(doc_id, "failed")
    except Exception:
        # Don't mask the original error if the status update itself fails.
        logger.warning("ingest.status_update_failed", doc_id=doc_id)
