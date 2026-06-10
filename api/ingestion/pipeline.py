"""Ingestion pipeline — PDF → chunks → embeddings → vectors → graph → ready.

Slice 1: entity extraction lands. After embedding + chunk-store upsert,
the pipeline runs `extract_entities()` per chunk and merges nodes/edges
into the GraphStore. Extraction failure on one chunk is recoverable: it
logs and continues so the rest of the doc still ingests (vector + chunk
store are unaffected).

Status state machine:
    pending → parsing → embedding → ready
    any → failed (on uncaught exception, with status update)

If `llm` is None, extraction is skipped entirely — preserves the slice-0
test contract and lets the eval harness ingest into a vector-only graph
when API keys aren't available.
"""

from __future__ import annotations

from api.core.errors import IngestFailed
from api.core.logging import get_logger
from api.embeddings.service import EmbedderProtocol
from api.ingestion.chunker import chunk as chunk_pages
from api.ingestion.extractor import ExtractionResult, extract_entities
from api.ingestion.parsers import pdf
from api.ingestion.parsers import web as web_parser
from api.ingestion.stores_bundle import Stores
from api.ingestion.types import Chunk
from api.llm.service import LLMService
from api.stores.chunk_store import StoredChunk
from api.stores.doc_store import DocMetadata
from api.stores.errors import GraphStoreError
from api.stores.graph_store import GraphNode, GraphStore
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
    llm: LLMService | None = None,
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

        # Entity extraction (slice 1, FR-ING-06). Per-chunk failures are
        # logged and skipped so one bad LLM response doesn't sink the
        # whole doc - the vector + chunk store remain populated and the
        # doc is still usable via dense + keyword retrieval.
        if llm is not None:
            await _extract_and_upsert_graph(
                chunks=chunks,
                doc_id=doc_id,
                llm=llm,
                graph=stores.graph,
            )

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


async def _mark_failed(stores: Stores, doc_id: str, *, cause: str | None = None) -> None:
    try:
        extra = {"error_cause": cause} if cause else None
        await stores.doc.update_status(doc_id, "failed", extra_update=extra)
    except Exception:
        # Don't mask the original error if the status update itself fails.
        logger.warning("ingest.status_update_failed", doc_id=doc_id)


async def _extract_and_upsert_graph(
    *,
    chunks: list[Chunk],
    doc_id: str,
    llm: LLMService,
    graph: GraphStore,
) -> int:
    """Run extraction per chunk, merge into the graph. Returns total
    nodes upserted across all chunks (for telemetry / tests).

    Cross-chunk merge semantics: when the same slug is mentioned in
    multiple chunks, we accumulate `mentioned_in_chunks` + `doc_ids`
    lists on the node properties so the GraphRetriever (chunk 3) can
    map entity → chunks. Other node fields (type, label) are taken from
    the FIRST mention - later renames would otherwise thrash the graph."""
    total_nodes = 0
    for chunk in chunks:
        try:
            extraction = await extract_entities(
                text=chunk.text,
                chunk_id=chunk.id,
                doc_id=doc_id,
                llm=llm,
            )
        except IngestFailed as e:
            logger.warning(
                "ingest.extraction_failed_chunk",
                doc_id=doc_id,
                chunk_id=chunk.id,
                error=str(e),
            )
            continue

        await _merge_extraction(extraction, graph=graph)
        total_nodes += len(extraction.nodes)

    return total_nodes


async def _merge_extraction(extraction: ExtractionResult, *, graph: GraphStore) -> None:
    """Upsert nodes (merging chunk/doc lists with existing) then edges.
    Edge upsert is idempotent in MultiDiGraph keyed on (src, dst, type)."""
    for node in extraction.nodes:
        existing = await graph.get_node(node.id)
        if existing is None:
            await graph.upsert_node(node)
            continue
        # Merge accumulating lists; preserve insertion order via dict-keys.
        prev_chunks = list(existing.properties.get("mentioned_in_chunks", []))
        prev_docs = list(existing.properties.get("doc_ids", []))
        new_chunks = list(
            dict.fromkeys(
                prev_chunks + node.properties.get("mentioned_in_chunks", [])
            )
        )
        new_docs = list(
            dict.fromkeys(prev_docs + node.properties.get("doc_ids", []))
        )
        merged_props = {
            **existing.properties,
            **{k: v for k, v in node.properties.items()
               if k not in {"mentioned_in_chunks", "doc_ids"}},
            "mentioned_in_chunks": new_chunks,
            "doc_ids": new_docs,
        }
        await graph.upsert_node(
            GraphNode(
                id=node.id,
                type=existing.type,
                label=existing.label,
                properties=merged_props,
            )
        )

    for edge in extraction.edges:
        try:
            await graph.upsert_edge(edge)
        except GraphStoreError:
            # Endpoint absent — shouldn't happen since we just upserted
            # all entities from this extraction batch. Log and continue.
            logger.warning(
                "ingest.skipped_edge",
                src=edge.src,
                dst=edge.dst,
                type=edge.type,
            )


async def ingest_url(
    *,
    url: str,
    stores: Stores,
    embedder: EmbedderProtocol,
    llm: LLMService | None = None,
) -> DocMetadata:
    """Fetch *url*, extract text, and ingest it into the knowledge graph.

    Mirrors ingest_pdf but uses the web parser instead of PyMuPDF.
    Returns final DocMetadata on success; raises IngestFailed on error.
    """
    doc_id = web_parser.doc_id_for_url(url)

    # Persist a placeholder immediately so _mark_failed can always write the
    # cause even if fetch_and_parse raises before we have the real bytes.
    await stores.doc.put(
        doc_id,
        b"",
        content_type="text/plain",
        title=url[:256],
        source_uri=url,
        ingest_status="parsing",
    )
    logger.info("ingest_url.start", doc_id=doc_id, url=url)

    try:
        title, pages = await web_parser.fetch_and_parse(url)

        raw = "\n\n".join(p.text for p in pages).encode("utf-8")
        # Update stored raw bytes and title now that we have real content.
        await stores.doc.put(
            doc_id,
            raw,
            content_type="text/plain",
            title=title,
            source_uri=url,
            ingest_status="parsing",
        )

        chunks: list[Chunk] = chunk_pages(pages, doc_id=doc_id)
        if not chunks:
            raise IngestFailed("chunker produced zero chunks", details={"doc_id": doc_id, "url": url})

        await stores.doc.update_status(doc_id, "embedding")

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
                        "text": c.text,
                    },
                )
                for c, v in zip(chunks, vectors, strict=True)
            ]
        )
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

        if llm is not None:
            await _extract_and_upsert_graph(
                chunks=chunks,
                doc_id=doc_id,
                llm=llm,
                graph=stores.graph,
            )

        meta = await stores.doc.update_status(doc_id, "ready")
        logger.info("ingest_url.ready", doc_id=doc_id, chunks=len(chunks))
        return meta

    except IngestFailed as exc:
        await _mark_failed(stores, doc_id, cause=str(exc))
        raise
    except Exception as e:
        await _mark_failed(stores, doc_id, cause=str(e))
        logger.exception("ingest_url.unhandled", doc_id=doc_id)
        raise IngestFailed(f"unhandled error during URL ingest: {e}") from e
