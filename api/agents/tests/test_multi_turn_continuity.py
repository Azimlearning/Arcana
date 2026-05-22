"""Multi-turn memory continuity — turn N+1 sees turn N's history.

Locks the slice-1 contract that Memory Agent + Orchestrator.memory
writeback round-trip through the same InMemoryMemoryStore correctly:
  - User query from turn 1 lands in the store.
  - Assistant response (when status != error) lands in the store.
  - Turn 2's MemoryAgent loads turn 1's history into state.messages.
  - Error-status responses do NOT pollute history.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from api.agents.base import AgentState, registry
from api.agents.orchestrator import Orchestrator
from api.agents.tier2.research import ResearchAgent
from api.agents.tier3.ui_agent import UIAgent
from api.agents.tier4.memory import MemoryAgent
from api.llm.types import Completion, Usage
from api.retrieval.types import RetrievedChunk
from api.stores.doc_store import DocMetadata
from api.stores.in_memory_store import InMemoryMemoryStore


@pytest.fixture(autouse=True)
def clean_registry():
    registry.reset()
    yield
    registry.reset()


# ── Stubs ────────────────────────────────────────────────────────


class _StubLLM:
    def __init__(self, *, text: str) -> None:
        self._text = text

    async def complete(self, messages, *, system=None, tools=None, max_tokens=None, budget=None):
        return Completion(
            text=self._text,
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=20),
            model="stub", provider="stub",
        )


class _StubRetriever:
    def __init__(self, results: list[RetrievedChunk]) -> None:
        self._results = results

    async def retrieve(self, query, *, top_k=10):
        return self._results[:top_k]


class _StubDocStore:
    async def get_metadata(self, doc_id):
        return DocMetadata(
            id=doc_id, title=f"Title {doc_id}", source_uri="/x.pdf",
            content_type="application/pdf", size_bytes=1, created_at=datetime.now(UTC),
        )
    async def put(self, *a, **kw): ...
    async def get_bytes(self, *a, **kw): ...
    async def update_status(self, *a, **kw): ...
    async def list_documents(self): return []
    async def aclose(self): return None


class _StubEmbedder:
    async def embed(self, texts):
        return [[0.0] * 4 for _ in texts]


def _chunk(cid: str) -> RetrievedChunk:
    return RetrievedChunk(
        id=cid, doc_id="d1", text=f"body {cid}", page=1, score=0.9, source="vector"
    )


def _make_orchestrator(*, store: InMemoryMemoryStore, llm_text: str) -> Orchestrator:
    research = ResearchAgent(
        llm_service=_StubLLM(text=llm_text),  # type: ignore[arg-type]
        embedder=_StubEmbedder(),  # type: ignore[arg-type]
        vector_retriever=_StubRetriever([_chunk("ch1")]),
        bm25_retriever=_StubRetriever([]),
        graph_retriever=_StubRetriever([]),
        doc_store=_StubDocStore(),  # type: ignore[arg-type]
    )
    return Orchestrator(
        research=research,
        ui_agent=UIAgent(),
        memory_agent=MemoryAgent(store=store),
        memory_store=store,
    )


# ── The actual continuity tests ──────────────────────────────────


async def test_turn_two_sees_turn_one_history():
    """The slice's headline behaviour: ask, then ask again, and the
    second turn's MemoryAgent loads the first turn's exchange."""
    store = InMemoryMemoryStore()
    orch = _make_orchestrator(
        store=store,
        llm_text="GraphRAG outperforms vector RAG on multi-hop [c1].",
    )

    # Turn 1
    state1 = AgentState(query="what is GraphRAG?", notebook_id="nb_A")
    await orch.run("what is GraphRAG?", state=state1)
    assert len(state1.ui_blocks) == 1
    assert state1.ui_blocks[0].meta.status == "ready"

    # Turn 2 - fresh state, same notebook
    state2 = AgentState(query="how does it compare?", notebook_id="nb_A")
    await orch.run("how does it compare?", state=state2)

    # state2.messages should contain turn-1's user + assistant + turn-2's user.
    msgs = [m.content for m in state2.messages]
    assert "what is GraphRAG?" in msgs
    assert any("GraphRAG outperforms" in m for m in msgs)   # assistant from turn 1
    assert "how does it compare?" in msgs   # current turn's query


async def test_notebook_isolation_across_turns():
    """Notebook A's history does NOT leak into notebook B."""
    store = InMemoryMemoryStore()
    orch = _make_orchestrator(store=store, llm_text="Answer body [c1].")

    state_a = AgentState(query="A's question", notebook_id="nb_A")
    await orch.run("A's question", state=state_a)

    state_b = AgentState(query="B's question", notebook_id="nb_B")
    await orch.run("B's question", state=state_b)

    contents_b = [m.content for m in state_b.messages]
    assert "A's question" not in contents_b
    assert "B's question" in contents_b


async def test_error_blocks_do_not_pollute_memory():
    """When the assistant fails (error block), only the USER query is
    persisted - not the apology string. This prevents next turn's history
    from filling with the model's own apologies."""

    class _BoomLLM:
        async def complete(self, *a, **kw):
            raise RuntimeError("simulated API outage")

    store = InMemoryMemoryStore()
    research = ResearchAgent(
        llm_service=_BoomLLM(),  # type: ignore[arg-type]
        embedder=_StubEmbedder(),  # type: ignore[arg-type]
        vector_retriever=_StubRetriever([_chunk("ch1")]),
        bm25_retriever=_StubRetriever([]),
        graph_retriever=_StubRetriever([]),
        doc_store=_StubDocStore(),  # type: ignore[arg-type]
    )
    orch = Orchestrator(
        research=research,
        ui_agent=UIAgent(),
        memory_agent=MemoryAgent(store=store),
        memory_store=store,
    )

    state = AgentState(query="trigger failure", notebook_id="nb_fail")
    result = await orch.run("trigger failure", state=state)
    assert result.status == "ok"
    assert state.ui_blocks[0].meta.status == "error"

    # Only the user query persisted; the apology summary is NOT in the store.
    stored = await store.get_messages("nb_fail")
    contents = [m.content for m in stored]
    assert "trigger failure" in contents
    assert not any("Sorry" in c for c in contents)


async def test_existing_orchestrator_test_pattern_still_works():
    """Backwards-compat: constructing Orchestrator WITHOUT memory_agent
    (slice-0 ctor signature) still produces a working graph."""
    research = ResearchAgent(
        llm_service=_StubLLM(text="answer [c1]."),  # type: ignore[arg-type]
        embedder=_StubEmbedder(),  # type: ignore[arg-type]
        vector_retriever=_StubRetriever([_chunk("ch1")]),
        bm25_retriever=_StubRetriever([]),
        graph_retriever=_StubRetriever([]),
        doc_store=_StubDocStore(),  # type: ignore[arg-type]
    )
    orch = Orchestrator(research=research, ui_agent=UIAgent())
    state = AgentState(query="q")
    result = await orch.run("q", state=state)
    assert result.status == "ok"
    assert len(state.ui_blocks) == 1
