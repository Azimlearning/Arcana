"""Ingest every PDF under eval/corpus/ into the production stores.

Entry point for `make ingest-demo`. Reads Settings from api/.env, so
ANTHROPIC_API_KEY (not needed for ingestion strictly but required by
Settings), OPENAI_API_KEY (embeddings), and PINECONE_API_KEY + index
must all be populated before this script runs.

Prints per-file status to stdout. Exits 0 on full success; non-zero
if any file fails (the rest still attempt).
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import sys
from pathlib import Path

from api.core.logging import configure_logging, get_logger
from api.core.settings import REPO_ROOT, get_settings
from api.embeddings.service import EmbeddingService
from api.ingestion.pipeline import ingest_pdf
from api.ingestion.stores_bundle import Stores
from api.stores.filesystem_doc_store import FilesystemDocStore
from api.stores.jsonl_chunk_store import JsonlChunkStore
from api.stores.networkx_store import NetworkXGraphStore
from api.stores.pinecone_store import PineconeVectorStore

CORPUS_DIR = REPO_ROOT / "eval" / "corpus"

# DocStore allowlist is [A-Za-z0-9_-]{1,128}; sanitize the filename stem
# down to that charset and clamp length.
_ID_SANITIZE = re.compile(r"[^A-Za-z0-9_\-]")

# Filenames matching a Windows reserved device name (CON.pdf, NUL.pdf,
# COM1.pdf, …) would yield a doc_id that FilesystemDocStore refuses.
# Prefix them so they pass the allowlist instead of erroring out.
_WIN_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})


def _doc_id_for(path: Path) -> str:
    stem = _ID_SANITIZE.sub("_", path.stem)
    stem = stem.strip("_") or "doc"
    if stem.upper() in _WIN_RESERVED:
        stem = f"doc_{stem}"
    return stem[:128]


async def main() -> int:
    configure_logging()
    logger = get_logger("eval.ingest_demo")

    settings = get_settings()
    pdfs = sorted(CORPUS_DIR.glob("*.pdf"))
    if not pdfs:
        print(
            f"No PDFs found in {CORPUS_DIR}.\n"
            f"Drop a PDF in that directory and re-run `make ingest-demo`.",
            file=sys.stderr,
        )
        return 1

    print(f"Ingesting {len(pdfs)} PDF(s) from {CORPUS_DIR}")
    print(f"  storage:  {settings.local_storage_path}")
    print(f"  pinecone: {settings.pinecone_index}\n")

    stores = Stores(
        doc=FilesystemDocStore(root=settings.local_storage_path),
        vector=PineconeVectorStore(
            api_key=settings.pinecone_api_key.get_secret_value(),
            index_name=settings.pinecone_index,
        ),
        graph=NetworkXGraphStore(
            persist_path=settings.local_storage_path / "graph.json",
        ),
        chunks=JsonlChunkStore(root=settings.local_storage_path),
    )
    embedder = EmbeddingService(settings=settings)

    failures = 0
    try:
        for pdf_path in pdfs:
            doc_id = _doc_id_for(pdf_path)
            print(f"--> {pdf_path.name}   (doc_id={doc_id})")
            try:
                raw = pdf_path.read_bytes()
                meta = await ingest_pdf(
                    doc_id=doc_id,
                    raw=raw,
                    title=pdf_path.name,
                    source_uri=str(pdf_path),
                    stores=stores,
                    embedder=embedder,
                )
                print(f"    OK  ({meta.size_bytes:>9,} bytes, status={meta.ingest_status})")
            except Exception as e:
                failures += 1
                print(f"    FAIL: {e}")
                logger.exception("ingest_demo.failed", file=pdf_path.name)
    finally:
        # Close everything we opened, independent of each other - a failure
        # in graph.save() must NOT skip the httpx-client close on Pinecone/
        # embedder (would leak sockets). Each step is its own context.
        async with contextlib.AsyncExitStack() as stack:
            stack.push_async_callback(embedder.aclose)
            stack.push_async_callback(stores.vector.aclose)
            stack.push_async_callback(stores.doc.aclose)
            stack.push_async_callback(stores.chunks.aclose)
            # Graph save runs synchronously; do it inside the stack so
            # the closes still run if save() raises.
            try:
                if isinstance(stores.graph, NetworkXGraphStore):
                    stores.graph.save()
            except Exception:
                logger.exception("ingest_demo.graph_save_failed")

    succeeded = len(pdfs) - failures
    print(f"\nDone. {succeeded}/{len(pdfs)} succeeded, {failures} failed.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
