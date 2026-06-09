"""POST /ingest — multipart PDF upload → ingestion pipeline (FR-ING-01).

Accepts a single PDF file plus an optional `notebook_id` form field.
Runs the same pipeline as eval/ingest_demo.py and returns IngestResponse.

The IngestContext dependency is overridden by api/main.py at startup with
the shared store/embedder/llm instances so the graph_store is the same
object the orchestrator reads from — changes are immediately visible to
subsequent chat turns without a server restart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.core.logging import get_logger
from api.embeddings.service import EmbedderProtocol
from api.genui._generated import IngestResponse
from api.ingestion.pipeline import ingest_pdf
from api.ingestion.stores_bundle import Stores
from api.llm.service import LLMService

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

    logger.info("ingest.start", doc_id=doc_id, title=title, size_bytes=len(raw))
    try:
        await ingest_pdf(
            doc_id=doc_id,
            raw=raw,
            title=title,
            source_uri=f"upload/{title}",
            stores=ctx.stores,
            embedder=ctx.embedder,
            llm=ctx.llm,
        )
        # Count stored chunks for this doc (filter from full list).
        all_chunks = await ctx.stores.chunks.list_all()
        chunk_count = sum(1 for c in all_chunks if c.doc_id == doc_id)

        logger.info("ingest.done", doc_id=doc_id, chunk_count=chunk_count)
        return IngestResponse(
            docId=doc_id,
            title=title,
            status="ready",
            chunkCount=chunk_count,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ingest.failed", doc_id=doc_id)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}") from e
