"""VectorRetriever — embed → query → map to RetrievedChunk."""

from __future__ import annotations

from api.retrieval.vector import VectorRetriever
from api.stores.vector_store import VectorHit, VectorItem, VectorStore


class _StubEmbedder:
    def __init__(self, *, vec: list[float]) -> None:
        self._vec = vec
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self._vec for _ in texts]


class _StubVectorStore(VectorStore):
    dimension = 4

    def __init__(self, *, hits: list[VectorHit]) -> None:
        self._hits = hits
        self.query_calls: list[tuple[list[float], int]] = []

    async def upsert(self, items: list[VectorItem]) -> None: ...

    async def query(self, vector, *, top_k=10, filter=None) -> list[VectorHit]:
        self.query_calls.append((list(vector), top_k))
        return self._hits[:top_k]

    async def delete(self, ids: list[str]) -> None: ...

    async def aclose(self) -> None:
        return None


async def test_retrieve_maps_hits_to_chunks():
    hits = [
        VectorHit(
            id="v1",
            score=0.91,
            metadata={"doc_id": "d1", "text": "Alpha body.", "page": 2},
        ),
        VectorHit(
            id="v2",
            score=0.85,
            metadata={"doc_id": "d2", "text": "Beta body.", "page": 7},
        ),
    ]
    embedder = _StubEmbedder(vec=[0.1, 0.2, 0.3, 0.4])
    store = _StubVectorStore(hits=hits)
    retriever = VectorRetriever(vector_store=store, embedder=embedder)

    out = await retriever.retrieve("what is alpha?", top_k=5)
    assert [c.id for c in out] == ["v1", "v2"]
    assert out[0].text == "Alpha body."
    assert out[0].page == 2
    assert out[0].score == 0.91
    assert out[0].source == "vector"
    assert embedder.calls == [["what is alpha?"]]
    assert store.query_calls == [([0.1, 0.2, 0.3, 0.4], 5)]


async def test_missing_metadata_raises_fail_loud():
    """Invariant #1 (grounded citations) — missing metadata indicates a
    broken ingestion pipeline, not user input. Refuse rather than silently
    producing a `page=0` citation that would fail the citation-accuracy
    benchmark (R-02) without surfacing why."""
    import pytest

    from api.stores.errors import VectorStoreError

    hits = [VectorHit(id="v1", score=0.9, metadata={})]
    embedder = _StubEmbedder(vec=[0.0] * 4)
    store = _StubVectorStore(hits=hits)
    retriever = VectorRetriever(vector_store=store, embedder=embedder)
    with pytest.raises(VectorStoreError):
        await retriever.retrieve("query")


async def test_non_int_page_raises_fail_loud():
    import pytest

    from api.stores.errors import VectorStoreError

    hits = [VectorHit(id="v1", score=0.9, metadata={"doc_id": "d1", "text": "x", "page": "abc"})]
    embedder = _StubEmbedder(vec=[0.0] * 4)
    store = _StubVectorStore(hits=hits)
    retriever = VectorRetriever(vector_store=store, embedder=embedder)
    with pytest.raises(VectorStoreError):
        await retriever.retrieve("query")


async def test_empty_embedder_returns_empty():
    class _EmptyEmbedder:
        async def embed(self, texts):
            return []
    retriever = VectorRetriever(
        vector_store=_StubVectorStore(hits=[]),
        embedder=_EmptyEmbedder(),  # type: ignore[arg-type]
    )
    assert await retriever.retrieve("q") == []
