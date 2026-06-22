"""End-to-end orchestrator path with stubs.

Drives orchestrator → research → ui_agent without any network. Asserts
the invariants the slice exists to prove:
  - #1: Research called hybrid_retrieve before synthesis.
  - #2: The block produced is a typed CitedSummary, not raw markup.
  - #3: Only UIAgent constructed the UIBlock.
  - #6: Even with retrieval / LLM failure, state.ui_blocks has one block.
"""

from __future__ import annotations

from datetime import UTC, datetime

from api.agents.base import AgentState
from api.agents.orchestrator import Orchestrator
from api.agents.tier2.research import ResearchAgent
from api.agents.tier3.ui_agent import UIAgent
from api.genui._generated import CitedSummary
from api.llm.types import Completion, Usage
from api.retrieval.types import RetrievedChunk
from api.stores.doc_store import DocMetadata


class _StubLLM:
    def __init__(self, *, text: str) -> None:
        self._text = text
        self.call_count = 0

    async def complete(self, messages, *, system=None, tools=None, max_tokens=None, budget=None):
        self.call_count += 1
        return Completion(
            text=self._text,
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=20),
            model="stub", provider="stub",
        )


class _StubRetriever:
    def __init__(self, results: list[RetrievedChunk]) -> None:
        self._results = results
        self.call_count = 0

    async def retrieve(self, query, *, top_k=10):
        self.call_count += 1
        return self._results[:top_k]


class _StubDocStore:
    async def get_metadata(self, doc_id):
        return DocMetadata(
            id=doc_id, title=f"Title of {doc_id}", source_uri="/x.pdf",
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


def _chunk(cid: str, doc_id: str, text: str, page: int = 1) -> RetrievedChunk:
    return RetrievedChunk(id=cid, doc_id=doc_id, text=text, page=page, score=0.9, source="vector")


def _build_orchestrator(*, chunks: list[RetrievedChunk], llm_text: str) -> tuple[Orchestrator, _StubRetriever]:
    vec = _StubRetriever(chunks)
    research = ResearchAgent(
        llm_service=_StubLLM(text=llm_text),  # type: ignore[arg-type]
        embedder=_StubEmbedder(),  # type: ignore[arg-type]
        vector_retriever=vec,
        bm25_retriever=_StubRetriever([]),
        graph_retriever=_StubRetriever([]),
        doc_store=_StubDocStore(),  # type: ignore[arg-type]
    )
    ui = UIAgent()
    orch = Orchestrator(research=research, ui_agent=ui)
    return orch, vec


async def test_happy_path_yields_one_cited_summary():
    chunks = [
        _chunk("ch1", "doc_a", "GraphRAG wins on multi-hop.", page=2),
        _chunk("ch2", "doc_a", "Vector RAG wins on single-hop.", page=5),
    ]
    orch, vec = _build_orchestrator(
        chunks=chunks,
        llm_text="GraphRAG wins multi-hop [c1]. Vector wins single-hop [c2].",
    )
    state = AgentState(query="compare them")
    result = await orch.run("compare them", state=state)

    # #1: retrieval ran first
    assert vec.call_count == 1
    # #2 + #3: exactly one typed UIBlock, picked by UIAgent
    assert len(state.ui_blocks) == 1
    block = state.ui_blocks[0]
    assert isinstance(block, CitedSummary)
    assert block.meta.status == "ready"
    # Block carries citations from both chunks.
    assert {c.id for c in block.data.citations} == {"c1", "c2"}
    assert all(c.docTitle.startswith("Title of") for c in block.data.citations)
    assert result.status == "ok"


async def test_retrieval_empty_still_terminates_at_ui_agent():
    """Invariant #6: orchestrator MUST end with a UIBlock even when
    research finds zero evidence."""
    orch, _ = _build_orchestrator(chunks=[], llm_text="(unused)")
    state = AgentState(query="x")
    await orch.run("x", state=state)
    assert len(state.ui_blocks) == 1
    block = state.ui_blocks[0]
    # Research returned "partial" → UIAgent emits a partial-status block.
    assert block.meta.status == "partial"


async def test_llm_failure_still_terminates_at_ui_agent():
    """Invariant #6 even on LLM blow-up."""
    class _BoomLLM(_StubLLM):
        async def complete(self, *a, **kw):
            raise RuntimeError("API outage")

    research = ResearchAgent(
        llm_service=_BoomLLM(text="x"),  # type: ignore[arg-type]
        embedder=_StubEmbedder(),  # type: ignore[arg-type]
        vector_retriever=_StubRetriever([_chunk("ch1", "d1", "body", page=1)]),
        bm25_retriever=_StubRetriever([]),
        graph_retriever=_StubRetriever([]),
        doc_store=_StubDocStore(),  # type: ignore[arg-type]
    )
    orch = Orchestrator(research=research, ui_agent=UIAgent())
    state = AgentState(query="x")
    await orch.run("x", state=state)
    assert len(state.ui_blocks) == 1
    assert state.ui_blocks[0].meta.status == "error"


async def test_astream_run_emits_progress_per_node():
    """FR-AGT-07: astream_run yields a progress event as each node completes
    and writes the final blocks back into the caller's state."""
    chunks = [_chunk("ch1", "doc_a", "GraphRAG wins multi-hop.", page=2)]
    orch, vec = _build_orchestrator(chunks=chunks, llm_text="GraphRAG wins [c1].")
    state = AgentState(query="compare them")

    progress = [p async for p in orch.astream_run("compare them", state=state)]
    agents = [p["agent"] for p in progress]

    # Orchestrator, the research specialist, and the terminal UI agent report.
    assert "orchestrator" in agents
    assert "research" in agents
    assert "ui_agent" in agents
    assert all(p["status"] == "done" for p in progress)
    # Final state written back: one typed block, retrieval ran once.
    assert len(state.ui_blocks) == 1
    assert vec.call_count == 1
