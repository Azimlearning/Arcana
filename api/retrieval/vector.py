"""Dense vector retrieval — FR-RET-01.

Embeds the query, runs ANN search against `VectorStore`, maps the hits'
metadata back to `RetrievedChunk`s. Depends on the `EmbedderProtocol` so
a test can inject a deterministic embedder.
"""

from __future__ import annotations

from api.embeddings.service import EmbedderProtocol
from api.retrieval.types import RetrievedChunk
from api.stores.errors import VectorStoreError
from api.stores.vector_store import VectorStore


class VectorRetriever:
    def __init__(self, *, vector_store: VectorStore, embedder: EmbedderProtocol) -> None:
        self._vec = vector_store
        self._embed = embedder

    async def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        vectors = await self._embed.embed([query])
        if not vectors:
            return []
        hits = await self._vec.query(vectors[0], top_k=top_k)
        out: list[RetrievedChunk] = []
        for h in hits:
            meta = h.metadata or {}
            # Fail-loud: invariant #1 ("ground before generating") requires every
            # retrieved chunk carry a real page for citation provenance. A missing
            # or non-int `page` means the vector store was populated incorrectly
            # — silent fallback would let CitedSummary cite "page 0", which would
            # fail the citation-accuracy benchmark without surfacing a cause.
            for required in ("doc_id", "text", "page"):
                if required not in meta:
                    raise VectorStoreError(
                        f"vector hit {h.id!r} missing required metadata field {required!r}"
                    )
            try:
                page = int(meta["page"])
            except (TypeError, ValueError) as e:
                raise VectorStoreError(
                    f"vector hit {h.id!r} has non-int page metadata: {meta['page']!r}"
                ) from e
            out.append(
                RetrievedChunk(
                    id=h.id,
                    doc_id=str(meta["doc_id"]),
                    text=str(meta["text"]),
                    page=page,
                    score=h.score,
                    source="vector",
                )
            )
        return out
