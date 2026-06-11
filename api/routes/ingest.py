"""POST /ingest — multipart PDF upload → ingestion pipeline (FR-ING-01).

Accepts a single PDF file plus an optional `notebook_id` form field.
Runs the same pipeline as eval/ingest_demo.py and returns IngestResponse.

The IngestContext dependency is overridden by api/main.py at startup with
the shared store/embedder/llm instances so the graph_store is the same
object the orchestrator reads from — changes are immediately visible to
subsequent chat turns without a server restart.

Slice 14 (FR-KG-02): IngestContext now carries a UserGraphRegistry. Each
ingest call writes entities into the requesting user's personal graph
(resolved from CurrentUser.uid) and saves it to disk after completion.

Slice 20 (FR-ING-08): POST /ingest/retry/{doc_id} re-runs the pipeline
using stored bytes for documents that previously failed ingestion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.core.auth import CurrentUser, get_current_user
from api.core.errors import IngestFailed
from api.core.logging import get_logger
from api.embeddings.service import EmbedderProtocol
from api.genui._generated import (
    DocListResponse,
    DocStatusResponse,
    IngestResponse,
    UrlIngestRequest,
)
from api.ingestion.pipeline import ingest_pdf, ingest_url, reextract_from_stored_chunks
from api.ingestion.stores_bundle import Stores
from api.llm.service import LLMService
from api.stores.doc_store import DocMetadata
from api.stores.errors import DocNotFound

if TYPE_CHECKING:
    from api.stores.user_graph_registry import UserGraphRegistry

logger = get_logger(__name__)

router = APIRouter()

# ── doc_id sanitisation (mirrors eval/ingest_demo.py) ────────────────────────
_ID_SANITIZE = re.compile(r"[^A-Za-z0-9_\-]")
_WIN_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})


def _doc_id_for(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    stem = _ID_SANITIZE.sub("_", stem).strip("_") or "doc"
    if stem.upper() in _WIN_RESERVED:
        stem = f"doc_{stem}"
    return stem[:128]


# ── dependency ────────────────────────────────────────────────────────────────

@dataclass
class IngestContext:
    """Shared infrastructure injected by api/main.py at startup.

    Using the same stores/embedder/llm instances as the orchestrator means
    an upload is immediately visible in the next chat turn (same in-memory
    NetworkXGraphStore object, same Pinecone client).
    """
    stores: Stores
    embedder: EmbedderProtocol
    llm: LLMService
    graph_registry: UserGraphRegistry | None = field(default=None)


def get_ingest_context() -> IngestContext:
    """Placeholder dependency — api/main.py overrides with real instances."""
    raise HTTPException(
        status_code=503,
        detail=(
            "Ingest context not configured. "
            "api.main.create_app() wires this at startup."
        ),
    )


# ── route ─────────────────────────────────────────────────────────────────────

@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(..., description="PDF file to ingest"),  # noqa: B008
    notebook_id: str = Form("demo"),
    ctx: IngestContext = Depends(get_ingest_context),  # noqa: B008
    user: CurrentUser = Depends(get_current_user),    # noqa: B008
) -> IngestResponse:
    """Ingest a PDF into the knowledge graph + vector index.

    Returns immediately once the document is embedded and stored.
    The next chat turn will be able to retrieve content from it.
    """
    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are supported.")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    doc_id = _doc_id_for(filename)
    title = filename

    # FR-KG-02: resolve the requesting user's personal graph store so that
    # ingested entities land in their namespace, not a shared corpus graph.
    stores = ctx.stores
    if ctx.graph_registry is not None:
        user_graph = await ctx.graph_registry.get_or_create(user.uid)
        from api.ingestion.stores_bundle import Stores as _Stores
        stores = _Stores(
            doc=ctx.stores.doc,
            vector=ctx.stores.vector,
            graph=user_graph,
            chunks=ctx.stores.chunks,
        )

    logger.info("ingest.start", doc_id=doc_id, title=title, size_bytes=len(raw), user_id=user.uid)
    try:
        await ingest_pdf(
            doc_id=doc_id,
            raw=raw,
            title=title,
            source_uri=f"upload/{title}",
            stores=stores,
            embedder=ctx.embedder,
            llm=ctx.llm,
        )
        # Persist the user's graph to disk after successful ingestion.
        if ctx.graph_registry is not None:
            await ctx.graph_registry.save(user.uid)

        all_chunks = await ctx.stores.chunks.list_all()
        chunk_count = sum(1 for c in all_chunks if c.doc_id == doc_id)

        logger.info("ingest.done", doc_id=doc_id, chunk_count=chunk_count)
        return IngestResponse(
            docId=doc_id,
            title=title,
            status="ready",
            chunkCount=chunk_count,
            error=None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ingest.failed", doc_id=doc_id)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}") from e


# ── Re-extract entities from existing chunks ─────────────────────────────────

@router.post("/ingest/reextract")
async def reextract(
    ctx: IngestContext = Depends(get_ingest_context),  # noqa: B008
    user: CurrentUser = Depends(get_current_user),    # noqa: B008
) -> dict:
    """Re-run entity extraction on all chunks already in the chunk store.

    Call this when documents were ingested without a working LLM key so
    the knowledge graph was left empty. Reads from the existing chunk
    store — no re-upload needed. Idempotent (merge semantics).
    """
    if ctx.graph_registry is None:
        raise HTTPException(status_code=503, detail="Graph registry not available.")

    all_chunks = await ctx.stores.chunks.list_all()
    if not all_chunks:
        return {"docs": 0, "nodes": 0, "message": "No chunks found — ingest documents first."}

    user_graph = await ctx.graph_registry.get_or_create(user.uid)
    result = await reextract_from_stored_chunks(
        stored_chunks=all_chunks,
        llm=ctx.llm,
        graph=user_graph,
    )
    await ctx.graph_registry.save(user.uid)

    logger.info("reextract.complete", user_id=user.uid, **result)
    return {**result, "message": f"Re-extracted {result['nodes']} nodes from {result['docs']} documents."}


# ── URL ingest ────────────────────────────────────────────────────────────────

@router.post("/ingest/url", response_model=IngestResponse)
async def ingest_url_route(
    body: UrlIngestRequest,
    ctx: IngestContext = Depends(get_ingest_context),  # noqa: B008
    user: CurrentUser = Depends(get_current_user),    # noqa: B008
) -> IngestResponse:
    """Fetch a public URL, extract text, and ingest it."""
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=422, detail="url must not be empty.")

    # FR-KG-02: same per-user graph resolution as the PDF route.
    stores = ctx.stores
    if ctx.graph_registry is not None:
        user_graph = await ctx.graph_registry.get_or_create(user.uid)
        from api.ingestion.stores_bundle import Stores as _Stores
        stores = _Stores(
            doc=ctx.stores.doc,
            vector=ctx.stores.vector,
            graph=user_graph,
            chunks=ctx.stores.chunks,
        )

    logger.info("ingest_url.request", url=url, user_id=user.uid)
    try:
        meta = await ingest_url(
            url=url,
            stores=stores,
            embedder=ctx.embedder,
            llm=ctx.llm,
        )
        if ctx.graph_registry is not None:
            await ctx.graph_registry.save(user.uid)

        all_chunks = await ctx.stores.chunks.list_all()
        chunk_count = sum(1 for c in all_chunks if c.doc_id == meta.id)
        return IngestResponse(
            docId=meta.id,
            title=meta.title,
            status="ready",
            chunkCount=chunk_count,
            error=None,
        )
    except IngestFailed:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ingest_url.failed")
        raise HTTPException(status_code=500, detail=f"URL ingestion failed: {e}") from e


# ── Document status ───────────────────────────────────────────────────────────

def _meta_to_status(meta: DocMetadata) -> DocStatusResponse:
    """Map DocMetadata to the wire-visible DocStatusResponse."""
    return DocStatusResponse(
        docId=meta.id,
        title=meta.title,
        sourceUri=meta.source_uri,
        status=meta.ingest_status,
        sizeBytes=float(meta.size_bytes),
        error=meta.extra.get("error_cause"),
        createdAt=meta.created_at.isoformat(),
    )


@router.get("/docs", response_model=DocListResponse)
async def list_docs(
    ctx: IngestContext = Depends(get_ingest_context),  # noqa: B008
) -> DocListResponse:
    """List all ingested documents and their current status."""
    docs = await ctx.stores.doc.list_documents()
    return DocListResponse(docs=[_meta_to_status(m) for m in docs])


@router.get("/docs/{doc_id}", response_model=DocStatusResponse)
async def get_doc_status(
    doc_id: str,
    ctx: IngestContext = Depends(get_ingest_context),  # noqa: B008
) -> DocStatusResponse:
    """Get ingestion status for a specific document."""
    try:
        meta = await ctx.stores.doc.get_metadata(doc_id)
    except DocNotFound:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found.") from None
    return _meta_to_status(meta)


# ── Retry failed ingestion (FR-ING-08) ───────────────────────────────────────

@router.post("/ingest/retry/{doc_id}", response_model=IngestResponse)
async def retry_ingest(
    doc_id: str,
    ctx: IngestContext = Depends(get_ingest_context),  # noqa: B008
    user: CurrentUser = Depends(get_current_user),    # noqa: B008
) -> IngestResponse:
    """Retry a previously failed ingestion using stored document bytes.

    Reads raw bytes saved by the original upload and re-runs the full
    pipeline. Only allowed for documents with status 'failed' or 'pending'.
    """
    try:
        meta = await ctx.stores.doc.get_metadata(doc_id)
    except DocNotFound:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found.") from None

    if meta.ingest_status not in ("failed", "pending"):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Document {doc_id!r} has status {meta.ingest_status!r}; "
                "only 'failed' or 'pending' documents can be retried."
            ),
        )

    try:
        raw = await ctx.stores.doc.get_bytes(doc_id)
    except DocNotFound:
        raise HTTPException(
            status_code=404,
            detail=f"No stored bytes for {doc_id!r}. Please re-upload the file.",
        ) from None

    stores = ctx.stores
    if ctx.graph_registry is not None:
        user_graph = await ctx.graph_registry.get_or_create(user.uid)
        from api.ingestion.stores_bundle import Stores as _Stores
        stores = _Stores(
            doc=ctx.stores.doc,
            vector=ctx.stores.vector,
            graph=user_graph,
            chunks=ctx.stores.chunks,
        )

    logger.info("ingest_retry.start", doc_id=doc_id, user_id=user.uid)
    try:
        await ingest_pdf(
            doc_id=doc_id,
            raw=raw,
            title=meta.title,
            source_uri=meta.source_uri,
            stores=stores,
            embedder=ctx.embedder,
            llm=ctx.llm,
        )
        if ctx.graph_registry is not None:
            await ctx.graph_registry.save(user.uid)

        all_chunks = await ctx.stores.chunks.list_all()
        chunk_count = sum(1 for c in all_chunks if c.doc_id == doc_id)
        logger.info("ingest_retry.done", doc_id=doc_id, chunk_count=chunk_count)
        return IngestResponse(
            docId=doc_id,
            title=meta.title,
            status="ready",
            chunkCount=chunk_count,
            error=None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ingest_retry.failed", doc_id=doc_id)
        raise HTTPException(status_code=500, detail=f"Retry failed: {e}") from e
